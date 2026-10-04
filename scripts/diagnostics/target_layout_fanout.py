"""Targeted instrumentation/variants applied only to an ignored QML mirror.

Counts helper calls and responsive publications, not every QML binding. Elapsed
helper time excludes propagation after return and has 1 ms clock resolution.
Helper timings are inclusive; nested helper rows must not be added together
as independent elapsed costs, and the counters add diagnostic overhead.
Variants are investigations, never production selectors or qualification.
The value() counters measure expression evaluation, not change notifications.
Historical isolation variants require the pre-repair source shape; they must
not silently become no-ops against the retained repair.
"""
from pathlib import Path
import re
import shutil


CURRENT_VARIANTS = ("counts", "publication-costs", "hidden-font-scalars")
VARIANTS = CURRENT_VARIANTS + ("atomic-metrics", "hidden-controls", "dormant-shadows", "hidden-layout", "hidden-fonts")
TRACE_JS = '''.pragma library
var enabled = false
var stage = "idle"
var rows = ({})
var stack = []
var watched = []
function begin() { rows = ({}); stack = []; stage = "begin"; enabled = true }
function enter(name, visible) {
    if (!enabled) return null
    var token = {key: stage + ":" + name + ":" + (visible ? "visible" : "hidden"),
        at: Date.now(), childMs: 0}
    stack.push(token)
    return token
}
function leave(token) {
    if (!token) return
    var elapsed = Date.now() - token.at
    var row = rows[token.key] || {count: 0, helperMs: 0, exclusiveMs: 0, maximumMs: 0}
    row.count += 1
    row.helperMs += elapsed
    row.exclusiveMs += Math.max(0, elapsed - token.childMs)
    row.maximumMs = Math.max(row.maximumMs, elapsed)
    rows[token.key] = row
    stack.pop()
    if (stack.length) stack[stack.length - 1].childMs += elapsed
}
function value(name, result, visible) {
    leave(enter(name, visible))
    return result
}
function finish() { enabled = false; return rows }
function owner(item) {
    var names = []
    for (var index = 0; item && index < 6; ++index) {
        names.push(String(item).replace(/\\(.*$/, ""))
        item = item.parent
    }
    return names.join("/")
}
function notification(name, item, value) {
    if (!enabled) return
    var key = stage + ":" + name + "/" + String(item) + "/" + owner(item) + ":" + (item.visible ? "visible" : "hidden")
    var row = rows[key] || {count: 0, helperMs: 0, exclusiveMs: 0, maximumMs: 0,
        minimumValue: value, maximumValue: value}
    row.count += 1
    row.minimumValue = Math.min(row.minimumValue, value)
    row.maximumValue = Math.max(row.maximumValue, value)
    rows[key] = row
}
function watchTree(item) {
    if (!item || watched.indexOf(item) >= 0) return
    watched.push(item)
    if (item.fontChanged && item.font && typeof item.font.pixelSize === "number") {
        item.fontChanged.connect(function() { notification("Item.font", item, item.font.pixelSize) })
    }
    if (item.implicitHeightChanged) {
        item.implicitHeightChanged.connect(function() { notification("Item.implicitHeight", item, item.implicitHeight) })
    }
    if (item.implicitWidthChanged) {
        item.implicitWidthChanged.connect(function() { notification("Item.implicitWidth", item, item.implicitWidth) })
    }
    var children = item.children || []
    for (var index = 0; index < children.length; ++index) watchTree(children[index])
}
'''

HIDDEN_SCALAR_JS = '''.pragma library
var held = new WeakMap()
function scalar(owner, key, value, enabled) {
    if (!enabled || !owner || typeof owner.visible !== "boolean") return value
    var values = held.get(owner)
    if (!values) { values = ({}); held.set(owner, values) }
    if (!owner.visible && Object.prototype.hasOwnProperty.call(values, key)) return values[key]
    values[key] = value
    return value
}
'''


def _hold_metric_fonts(source: str) -> tuple[str, int]:
    """Wrap complete font expressions; leave constants and unrelated fields intact."""
    edits = []
    for match in re.finditer(r"font\.pixelSize:\s*", source):
        start = match.end()
        end, depth, quote = start, 0, None
        while end < len(source):
            char = source[end]
            if quote:
                if char == "\\":
                    end += 1
                elif char == quote:
                    quote = None
            elif char in ("'", '"', "`"):
                quote = char
            elif char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            elif depth == 0 and char in ";}":
                break
            elif depth == 0 and char == "\n":
                rest = source[end + 1:]
                following = re.match(r"\s*(?:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*:|[{}]|(?:readonly )?property\b)", rest)
                if following:
                    break
            end += 1
        expression = source[start:end].rstrip()
        if "root." not in expression:
            continue
        if not expression or "//" in expression or "{" in expression:
            raise ValueError("Unsupported hidden-font scalar expression")
        replacement = 'HiddenScalars.scalar(this, "font.pixelSize", (' + expression + '), root.layoutRepairEnabled)'
        edits.append((start, start + len(expression), replacement))
    for start, end, replacement in reversed(edits):
        source = source[:start] + replacement + source[end:]
    return source, len(edits)


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"Unavailable or ambiguous fanout target: {label}")
    return source.replace(old, new, 1)


def _validate_mirror(mirror: Path) -> Path:
    resolved = mirror.resolve()
    if "logs" not in resolved.parts or resolved.name != "tree":
        raise ValueError("Fanout instrumentation is restricted to logs/<audit>/tree")
    if not (resolved / "src/qml/DetachedShellWindow.qml").is_file():
        raise ValueError("A populated disposable mirror is required")
    return resolved


def _body_bounds(source: str, component: str, name: str) -> tuple[int, int]:
    matches = list(re.finditer(r"function " + re.escape(name) + r"\([^)]*\)\s*\{", source))
    if len(matches) != 1:
        raise ValueError(f"Unavailable or ambiguous targeted helper {component}.{name}")
    start = matches[0].end()
    end, depth, quote, comment = start, 1, None, None
    # The selected helpers have no regex literals containing braces. Quoted
    # strings and comments may contain braces and are explicitly skipped.
    while end < len(source):
        char = source[end]
        following = source[end:end + 2]
        if comment == "line":
            if char == "\n":
                comment = None
        elif comment == "block":
            if following == "*/":
                comment = None
                end += 1
        elif quote:
            if char == "\\":
                end += 1
            elif char == quote:
                quote = None
        elif following in ("//", "/*"):
            comment = "line" if following == "//" else "block"
            end += 1
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if not depth:
                return start, end
        end += 1
    raise ValueError(f"Unterminated targeted helper {component}.{name}")


def _wrap_helpers(source: str, component: str, names: tuple[str, ...]) -> str:
    for name in names:
        start, end = _body_bounds(source, component, name)
        body = source[start:end]
        visible = "true" if component == "DetachedShellWindow" else "visible"
        wrapped = ('\n        var probeToken = FanoutTrace.enter("' + component + "." + name
                   + '", ' + visible + ');\n        try {' + body
                   + '\n        } finally { FanoutTrace.leave(probeToken); }\n    ')
        source = source[:start] + wrapped + source[end:]
    return source


def instrument_mirror(mirror: Path, variant: str, collect_counts: bool = True) -> dict[str, str]:
    """Return changed paths for provenance; refuse any non-diagnostic mirror."""
    if variant not in VARIANTS:
        raise ValueError("A supported fanout variant is required")
    mirror = _validate_mirror(mirror)
    qml = mirror / "src/qml"
    if variant == "hidden-font-scalars" and "function fontPixelSize(" in (
            qml / "views/PlaceholderSubmenuView.qml").read_text(encoding="utf-8"):
        raise ValueError("Hidden-font scalar isolation requires source without the retained font metrics repair")
    if (qml / "FanoutTrace.js").exists():
        raise ValueError("Fanout instrumentation requires a fresh disposable mirror")
    changed = {"src/qml/FanoutTrace.js": TRACE_JS}
    targets = {
        "DetachedShellWindow.qml": ("ratioToPixels", "metricFloorPx"),
        "views/PlaceholderSubmenuView.qml": ("contentW", "contentH", "areaUnit", "ratioPx", "ratioPxW", "ratioPxH", "metricFloor"),
        "components/ModernTextField.qml": ("ratioPx", "metricFloor"),
        "components/ModernComboBox.qml": ("ratioPx", "metricFloor"),
        "components/PillButton.qml": ("ratioPx", "metricFloor"),
    }
    for relative, names in targets.items():
        path = qml / relative
        if not path.resolve().is_relative_to(mirror):
            raise ValueError("A fanout target resolves outside the disposable mirror")
        source = path.read_text(encoding="utf-8")
        if variant not in CURRENT_VARIANTS and ("layoutMetricsSnapshot" in source or "layoutMetricsGate" in source):
            raise ValueError(f"Historical isolation variant {variant} requires the pre-repair source: {relative}")
        prefix = "../" if "/" in relative else ""
        source = _replace_once(source, "import QtQuick\n", 'import QtQuick\nimport "' + prefix + 'FanoutTrace.js" as FanoutTrace\n', relative + ".import")
        component = path.stem
        if collect_counts and variant not in ("publication-costs", "hidden-font-scalars"):
            source = _wrap_helpers(source, component, names)
        if relative == "DetachedShellWindow.qml":
            if collect_counts:
                if "function computeUiMetrics() {" in source:
                    source = _replace_once(source, "function computeUiMetrics() {",
                        'function computeUiMetrics() {\n        FanoutTrace.value("Shell.uiMetricsCompute", 0, true);', "Shell.uiMetricsCompute")
                else:
                    source = _replace_once(source, "property var uiMetrics: (function() {",
                        'property var uiMetrics: (function() {\n        FanoutTrace.value("Shell.uiMetricsPublication", 0, true);', "Shell.uiMetricsPublication")
            if collect_counts:
                source = _replace_once(source, 'if (!cleanRoomNativeProfileEnabled) return;',
                                        'if (!cleanRoomNativeProfileEnabled) return;\n        FanoutTrace.stage = name;', "Shell.profileStage")
            source = _replace_once(source, "    id: mainWin\n", "    id: mainWin\n"
                "    function cleanRoomFanoutBegin() { "
                + ("FanoutTrace.begin(); " if collect_counts else "")
                + ("FanoutTrace.watchTree(mainWin.contentItem); " if collect_counts and variant in ("publication-costs", "hidden-font-scalars") else "")
                + "}\n"
                "    function cleanRoomFanoutFinish() { return "
                + ("FanoutTrace.finish()" if collect_counts else "({})")
                + "; }\n", "Shell.root")
            if collect_counts and variant in ("publication-costs", "hidden-font-scalars"):
                source = _wrap_helpers(source, component, ("computeUiMetrics",))
            if variant == "atomic-metrics":
                source = _replace_once(source, "property var uiMetrics: (function() {",
                    "property bool cleanRoomMetricsSuspended: false\n"
                    "    property var cleanRoomMetricsSnapshot: null\n"
                    "    property var uiMetrics: cleanRoomMetricsSuspended ? cleanRoomMetricsSnapshot : (function() {", "atomic-metrics.uiMetrics")
                source = _replace_once(source, 'cleanRoomNativeProfileMark("before:finalW");',
                    'cleanRoomMetricsSnapshot = uiMetrics;\n        cleanRoomMetricsSuspended = true;\n        cleanRoomNativeProfileMark("before:finalW");', "atomic-metrics.hold")
                source = _replace_once(source, 'cleanRoomNativeProfileMark("after:finalH");',
                    'cleanRoomNativeProfileMark("after:finalH");\n'
                    '        cleanRoomNativeProfileMark("before:metricsPublication");\n'
                    '        cleanRoomMetricsSuspended = false;\n'
                    '        cleanRoomNativeProfileMark("after:metricsPublication");', "atomic-metrics.publication")
        elif variant in ("hidden-controls", "hidden-layout") and relative.startswith("components/"):
            # Effective visibility includes invisible ancestors. The controls
            # remain instantiated; data, models and editing state stay alive.
            source = _replace_once(source, "property var metrics\n", "property var metrics\n"
                "    readonly property var probeActiveMetrics: visible ? metrics : null\n", relative + ".metrics")
            # Arithmetic helpers only: disconnect hidden font/padding/shadow
            # geometry from metrics without modifying visible calculations.
            for name in names:
                start, end = _body_bounds(source, component, name)
                section = source[start:end]
                if variant == "hidden-layout":
                    statement = "\n            if (!visible) return Math.max(1, " + (
                        "minPx || 1" if name == "ratioPx" else "fallbackPx || 1") + ");"
                    if collect_counts:
                        section = _replace_once(section, "try {", "try {" + statement, relative + "." + name + ".guard")
                    else:
                        section = statement + section
                source = source[:start] + re.sub(r"\bmetrics\b", "probeActiveMetrics", section) + source[end:]
        elif variant == "dormant-shadows" and relative.startswith("components/"):
            # No effect is visible in Professional mode. Keep original Console
            # calculations, but avoid rebuilding unused blur kernels on resize.
            source, replacements = re.subn(r"(            (?:radius|samples): )(control\.ratioPx[^\n]+)",
                            r"\1control.isProMode ? 0 : \2", source)
            if not replacements:
                raise ValueError(f"Unavailable dormant-shadows target: {relative}")
        changed["src/qml/" + relative] = source
    if collect_counts and variant in ("publication-costs", "hidden-font-scalars"):
        # Time the synchronous property publication, including downstream
        # control text/implicit-size propagation. Identity and scalar copying
        # remain the retained implementation; ownership exists only here.
        relative = "components/LayoutMetricsGate.qml"
        source = (qml / relative).read_text(encoding="utf-8")
        source = _replace_once(source, "import QtQml\n", 'import QtQml\nimport "../FanoutTrace.js" as FanoutTrace\n', relative + ".import")
        source = _replace_once(source, "    id: gate\n", "    id: gate\n    property var diagnosticOwner: null\n", relative + ".owner")
        source = _replace_once(source, "        snapshot = next\n", "        var publicationToken = FanoutTrace.enter(\"Gate.snapshotPublication/\" + FanoutTrace.owner(diagnosticOwner), active)\n"
            "        try { snapshot = next } finally { FanoutTrace.leave(publicationToken) }\n", relative + ".publication")
        start, end = _body_bounds(source, "LayoutMetricsGate", "publish")
        source = source[:start] + "\n        var gateToken = FanoutTrace.enter(\"Gate.publish/\" + FanoutTrace.owner(diagnosticOwner), active)\n        try {" + source[start:end] + "\n        } finally { FanoutTrace.leave(gateToken) }\n    " + source[end:]
        changed["src/qml/" + relative] = source
        for component in ("ModernTextField", "ModernComboBox", "PillButton"):
            relative = "src/qml/components/" + component + ".qml"
            changed[relative] = _replace_once(changed[relative], "        id: layoutMetricsGate\n",
                "        id: layoutMetricsGate\n        diagnosticOwner: control\n", component + ".gateOwner")
    if variant == "hidden-font-scalars":
        changed["src/qml/HiddenScalars.js"] = HIDDEN_SCALAR_JS
        paths = [qml / "views/PlaceholderSubmenuView.qml", *sorted((qml / "views/placeholder").glob("*.qml"))]
        wrapped = 0
        for path in paths:
            relative = str(path.relative_to(mirror)).replace("\\", "/")
            source = changed.get(relative, path.read_text(encoding="utf-8"))
            patched, count = _hold_metric_fonts(source)
            if not count:
                continue
            prefix = "../" if path.parent.name == "views" else "../../"
            patched = _replace_once(patched, "import QtQuick\n", 'import QtQuick\nimport "' + prefix + 'HiddenScalars.js" as HiddenScalars\n', relative + ".hiddenScalars")
            if path.name == "PlaceholderSubmenuView.qml":
                patched = _replace_once(patched, "    property var metrics\n", "    property var metrics\n    readonly property bool layoutRepairEnabled: typeof transitionExperiment !== \"undefined\" && transitionExperiment.layoutRepair\n", "Placeholder.layoutRepair")
            changed[relative] = patched
            wrapped += count
        if not wrapped:
            raise ValueError("No responsive font scalar bindings are available")
    if collect_counts:
        path = qml / "views/PlaceholderSubmenuView.qml"
        source = changed["src/qml/views/PlaceholderSubmenuView.qml"]
        source = _replace_once(source, "property var responsiveMetrics: ({",
            'property var responsiveMetrics: FanoutTrace.value("Placeholder.responsiveMetricsPublication", ({', "Placeholder.responsiveMetrics.start")
        source = _replace_once(source, '"fontFloorLabelPx": areaFloorPx(0.0098, 8)\n    })',
            '"fontFloorLabelPx": areaFloorPx(0.0098, 8)\n    }), visible)', "Placeholder.responsiveMetrics.end")
        changed["src/qml/views/PlaceholderSubmenuView.qml"] = source
        path = qml / "components/ProductivityReportPanel.qml"
        if not path.resolve().is_relative_to(mirror):
            raise ValueError("A fanout target resolves outside the disposable mirror")
        source = _replace_once(path.read_text(encoding="utf-8"), "import QtQuick\n",
            'import QtQuick\nimport "../FanoutTrace.js" as FanoutTrace\n', "Report.import")
        source = _replace_once(source, "readonly property bool shortCanvas: root.height < 650",
            'readonly property bool shortCanvas: FanoutTrace.value("Report.shortCanvasEvaluation", root.height < 650, visible)', "Report.shortCanvas")
        changed["src/qml/components/ProductivityReportPanel.qml"] = source
    if variant in ("hidden-layout", "hidden-fonts"):
        # Isolate invisible text shaping; data/text values remain untouched.
        for relative in ("views/PlaceholderSubmenuView.qml", "components/ModernTextField.qml",
                         "components/ModernComboBox.qml", "components/PillButton.qml"):
            path = qml / relative
            source = changed["src/qml/" + relative]
            guarded = 0
            def guarded_font(match):
                nonlocal guarded
                expression = match[2]
                if expression.count("(") != expression.count(")") or any(
                        token in expression for token in ("//", ";", "}", "{")):
                    return match[0]
                guarded += 1
                return match[1] + "visible ? (" + expression + ") : 12"
            source = re.sub(r"^(\s*font.pixelSize: )([^\n{]+)$", guarded_font, source, flags=re.M)
            if not guarded:
                raise ValueError(f"Unavailable hidden-fonts target: {relative}")
            changed["src/qml/" + relative] = source
    # Transform the complete set first. A missing/changed target must not leave
    # half-instrumented files that could be mistaken for a successful variant.
    for relative, source in changed.items():
        (mirror / relative).write_text(source, encoding="utf-8")
    return changed


def instrument_qt_blur(mirror: Path) -> dict[str, str]:
    """Copy the installed module; never patch the venv or distribute Qt code."""
    from PySide6.QtCore import QLibraryInfo
    mirror = _validate_mirror(mirror)
    trace_path = mirror / "src/qml/FanoutTrace.js"
    if not trace_path.is_file() or trace_path.read_text(encoding="utf-8") != TRACE_JS:
        raise ValueError("Qt blur instrumentation requires the matching mirror trace")
    imports = Path(QLibraryInfo.path(QLibraryInfo.QmlImportsPath))
    original = imports / "Qt5Compat/GraphicalEffects"
    destination = mirror / "imports/Qt5Compat/GraphicalEffects"
    if destination.exists():
        raise ValueError("Qt blur instrumentation requires a fresh imports destination")
    changes = {}
    for path in original.rglob("qmldir"):
        # The installed module prefers embedded qrc QML. Remove that preference
        # only in this ignored copy so our measured rebuild function is used.
        source = path.read_text(encoding="utf-8")
        patched = re.sub(r"^prefer .*\n", "", source, flags=re.M)
        if patched != source:
            changes[str((destination / path.relative_to(original)).relative_to(mirror)).replace("\\", "/")] = patched
    path = original / "GaussianBlur.qml"
    source = path.read_text(encoding="utf-8")
    source = _replace_once(source, "import QtQuick\n",
        'import QtQuick\nimport "../../../src/qml/FanoutTrace.js" as FanoutTrace\n', "QtGaussianBlur.import")
    source = _wrap_helpers(source, "QtGaussianBlur", ("_rebuildShaders",))
    source = _replace_once(source, '"QtGaussianBlur._rebuildShaders", visible',
        '"QtGaussianBlur._rebuildShaders/" + FanoutTrace.owner(root.source), visible', "QtGaussianBlur.owner")
    changes["imports/Qt5Compat/GraphicalEffects/GaussianBlur.qml"] = source
    shutil.copytree(original, destination)
    for relative, patched in changes.items():
        (mirror / relative).write_text(patched, encoding="utf-8")
    return changes
