# Fedora KDE desktop checkpoint

The user requested latest Git cloud source and unattended Fedora compilation,
portable appearance, Plasma resizing/state animations, preserved opening,
closing and taskbar/tray light effects, Windows logic parity and OneDrive sync.
This overrides historical interactive visual-audit stop rules for this work;
financial repairs are outside its scope.

## Source and build

Cloud `main` was cloned at `d1d6475` into the requested empty folder. The older
dirty checkout was preserved. The machine is Fedora 44 KDE Plasma 6.7.4,
x86_64, Wayland with XWayland and 200% scale. A local Python 3.13.16 environment
runs pinned PySide6 6.10.3 independently of Fedora's system Python/global Qt.

`scripts/build_linux_app.py` and Linux specs build the main application and
console recovery utility, validate approved blank templates, exclude live
datasets, record source/runtime hashes and preserve replaced bundles. The
per-user desktop installation backs up the previous launcher. pywin32 is
Windows-only. README documents reproduction.

## Appearance and motion

Shared QML typography uses Linux desktop fonts and preserves Windows families.
The bundled CSPM Symbols font supplies all 32 private-use glyphs plus utility
aliases from pinned MIT Fluent System Icon outlines; source hashes, license
and rebuild script are included. Rails, headers, forms, report filters and
tray controls share the mapping. Actual outlines and full tray construction
are tested. Stray tray font assignments and existing QML syntax errors were
corrected.

Both Linux styles use Qt native move/resize/maximize/restore requests so
Plasma/KWin owns geometry animation. Existing lifecycle light-effect sequence
and timing remain. The launcher defaults to XWayland because existing flight
surfaces need absolute desktop coordinates. Maximized taskbar/tray state is
retained. Tray targeting uses actual Qt bounds or an explicit panel-edge
estimate when Plasma does not expose the icon rectangle.

Linux initializes WebEngine's shared graphics context before QApplication,
following [Qt's contract](https://doc.qt.io/qt-6/qtwebenginequick.html). An observed
native PySide wrapper-reentrancy crash during Invoice Builder creation was
fixed by filtering established windows instead of all internal application
objects. Windows filters remain unchanged. The corrected desktop audit
reaches Invoice Builder and every current menu workspace without that crash.

## Paths and OneDrive

All settings-load paths honor explicit host-local selectors. File dialogs
preserve POSIX roots, escaped spaces/Unicode/#/% and network paths. Exports
use desktop associations; supplier Office documents use an isolated
LibreOffice profile with macros disabled and external-library paths sanitized.
Linux startup uses a desktop entry; restart waits for the owning process.

Authenticated direct server reads independently verified canonical OneDrive
workbooks, latest archived pair/manifest and native local sync bytes. An old
unknown partial local folder was preserved. Saved selectors point to the
confirmed synced source and a separate fresh local replica. Guarded checkout
seeded that replica and released ownership without publishing a new release;
source workbooks stayed unchanged. Settings/evidence are privately backed up.
Normal use keeps shared Windows single-writer checkout, common-ancestor hash,
paired publication and conflict refusal.

Recovery supports Linux process/advisory/open-file/Office-lock probes, refuses
existing/foreign/unreadable/read-only checkout, and holds an exclusive owned
marker around restore/resume. Only a conclusively dead recovery marker on the
same host/replica can be reclaimed. No production restore or financial record
mutation was performed.

## Validation and limits

The follow-up installed-GUI test exercised Invoice Builder, Zen Preview and
Save Draft PDF using an approved-template synthetic package. Its six-page
Letter export retains accented text, logo, continuation headers, every page
number and the expected fees/disbursements/HST/total; first/last PDF pages were
rendered and inspected. Cory also reported that export worked. No accounting
finalization was requested. A missing initial-state navigation method found
during that test was repaired, with executable state-only QML coverage for
reactive deep links, aliases, loader replay and deliberate refresh. The final
rebuilt installed follow-up is recorded in the private report below.

Sandbox-safe: Python/JavaScript contracts, offscreen Qt glyph/tray rendering,
QUrl roundtrips, template governance, compilation, whole-tree governed Linux
QML lint and whitespace. Full portable suite checkpoint: 707 passes, five
platform skips and 26 failures also reproduced on untouched remote main. An
obsolete motion suite cannot collect on either tree because it imports removed
constants. Baseline failures include unavailable private diagnostic workbooks
and stale source/schema contracts; they are disclosed, not reported as passing.

Outside sandbox: real hardware-rendered XWayland/Plasma source startup,
all 28 current menu routes captured, native maximize/restore, Console style,
tray minimize/restore and animated orderly close pass on disposable read-only
replicas. Five representative screenshots were independently inspected for
glyphs, typography and clipping. Actual LibreOffice DOCX-to-PDF passes. This
does not certify every populated workflow, monitor arrangement or animation
frame. Packaging and installed-runtime results are recorded after this source
checkpoint in private `logs/fedora-validation/final-report.json` and bundled
provenance/runtime manifest. No commit or push was requested.
