"""Read-only, bounded provenance and privacy audit of an ordinary CSPM package.

Compare compiled project code with immutable HEAD, ignoring only co_filename.
Inspect approved empty templates and committed runtime assets; never inspect
user profiles, workbooks outside the supplied package, or application logs.
The report is private evidence and must be new and outside the repository/package.
No application, native window, GPU transaction, or WebEngine is started.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from functools import lru_cache
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
import zipfile


ACCEPTED_NATIVE_SHA256 = "D60D55E3E72F2E8D928C363EE7AE15FD1DB5D448B81E31B5FB168A7303EF6578"
CODE_FIELDS = (
    "co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals",
    "co_stacksize", "co_flags", "co_code", "co_consts", "co_names",
    "co_varnames", "co_name", "co_qualname", "co_firstlineno", "co_linetable",
    "co_exceptiontable", "co_freevars", "co_cellvars",
)
TEXT_SUFFIXES = frozenset((".py", ".qml", ".js", ".md", ".json", ".yaml", ".yml", ".svg", ".txt", ".html", ".css", ".csv", ".frag", ".vert"))
PRIVATE_DIRS = frozenset(("logs", "backups", "backup", "private", "disposable_profile", "local_profile", "dumps", "captures", "attachments"))
PRIVATE_SUFFIXES = frozenset((".log", ".csv", ".db", ".db3", ".sqlite", ".sqlite3", ".har", ".pcap", ".dmp", ".pdb", ".obj", ".pem", ".key", ".p12", ".pfx"))
REQUIRED_MODULES = frozenset(("backend.app_controller", "backend.controllers.tray_controller", "repositories.excel_repo", "repositories.ap_workbook_repository", "services.sync_service"))


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def validate_public_trust_bundle(relative: str, path: Path, requirements: bytes,
                                 *, distribution_lookup=None) -> dict:
    """Permit only the exact public certifi bundle from the immutable release pin.

    A .pem suffix is otherwise a confidential artifact. Installed dependency
    metadata identifies its canonical bundle; the package must match every byte
    and contain certificate blocks without a private-key marker. No application,
    token cache or user certificate store is opened by this check.
    """
    result = dict(path=relative, allowed=False, pinnedVersion=None,
                  installedVersion=None, sha256=None, canonicalSha256=None,
                  certificateCount=0, reason="Not the supported public trust bundle path")
    if relative != "_internal/certifi/cacert.pem":
        return result
    try:
        pins = re.findall(r"^certifi==([^\s;#]+)\s*$", requirements.decode("utf-8-sig"), re.MULTILINE)
    except (UnicodeError, AttributeError):
        pins = []
    if len(pins) != 1:
        result["reason"] = "No exact immutable certifi dependency pin"
        return result
    result["pinnedVersion"] = pins[0]
    try:
        if distribution_lookup is None:
            from importlib.metadata import distribution
            distribution_lookup = distribution
        dependency = distribution_lookup("certifi")
        result["installedVersion"] = dependency.version
        if dependency.version != pins[0]:
            result["reason"] = "Installed certifi version differs from the immutable pin"
            return result
        canonical_path = Path(dependency.locate_file("certifi/cacert.pem"))
        canonical_bytes = canonical_path.read_bytes()
        packaged_bytes = path.read_bytes()
    except Exception:
        result["reason"] = "The pinned certifi public bundle is unavailable"
        return result
    result["sha256"] = hashlib.sha256(packaged_bytes).hexdigest().upper()
    result["canonicalSha256"] = hashlib.sha256(canonical_bytes).hexdigest().upper()
    if packaged_bytes != canonical_bytes:
        result["reason"] = "Public trust bundle bytes differ from the pinned dependency"
        return result
    kinds = re.findall(rb"-----BEGIN ([A-Z0-9 ]+)-----", packaged_bytes)
    result["certificateCount"] = kinds.count(b"CERTIFICATE")
    if (not kinds or set(kinds) != {b"CERTIFICATE"}
            or re.search(rb"PRIVATE[\s_-]*KEY", packaged_bytes, re.IGNORECASE)
            or packaged_bytes.count(b"-----END CERTIFICATE-----") != result["certificateCount"]):
        result["reason"] = "Trust bundle does not contain only public certificate blocks"
        return result
    result.update(allowed=True, reason="Exact pinned certifi public CA certificates")
    return result


def code_differences(left, right, location="module") -> list[str]:
    """Compare every serialized code field except checkout filenames."""
    if type(left) is not type(right):
        return [location + ":type"]
    if isinstance(left, types.CodeType):
        return [difference for field in CODE_FIELDS
                for difference in code_differences(getattr(left, field), getattr(right, field), location + "." + field)]
    if isinstance(left, tuple):
        if len(left) != len(right):
            return [location + ":length"]
        return [difference for index, (first, second) in enumerate(zip(left, right))
                for difference in code_differences(first, second, location + "[" + str(index) + "]")]
    return [] if left == right else [location]


def load_tool(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ValueError("Repository audit dependency unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def git_binary() -> str:
    installed = shutil.which("git")
    if installed:
        return installed
    candidate = Path(os.environ.get("ProgramFiles", "")) / "Git" / "cmd" / "git.exe"
    if candidate.is_file():
        return str(candidate)
    raise FileNotFoundError("Git is required for immutable source comparison")


def audit(repo: Path, package: Path, source_sha: str | None = None) -> dict:
    from PyInstaller.archive.readers import CArchiveReader

    executable = package / "CSPM.exe"
    internal = package / "_internal"
    git = git_binary()

    def git_output(*arguments: str) -> bytes:
        return subprocess.check_output([git, "-C", str(repo), *arguments], stderr=subprocess.PIPE)

    initial_head = git_output("rev-parse", "HEAD").decode().strip()
    head = git_output("rev-parse", "--verify", (source_sha or initial_head) + "^{commit}").decode().strip()
    if source_sha is not None and head.lower() != source_sha.lower():
        raise ValueError("Requested immutable source pin differs from resolved commit")

    @lru_cache(maxsize=None)
    def source(relative: str) -> bytes:
        return git_output("show", head + ":" + relative)

    def tracked(directory: str) -> list[str]:
        return git_output("ls-tree", "-r", "--name-only", head, "--", directory).decode().splitlines()

    result = dict(schemaVersion=1, verifiedAtUtc=datetime.now(UTC).isoformat(),
                  sourceSha=head, repositoryHeadAtStart=initial_head,
                  explicitSourcePin=source_sha is not None, package=str(package), pythonVersion=sys.version,
                  applicationLaunched=False, dataWritten=False, failures=[])
    failures = result["failures"]
    deployment = load_tool("lifecycle_package_deployment", repo / "scripts/deploy_native_motion_release.py")
    privacy = load_tool("lifecycle_package_privacy", repo / "scripts/diagnostics/scan_cleanroom_staged.py")
    packaged_approval = (internal / "src/templates/template_approval.json").read_bytes().replace(b"\r\n", b"\n")
    if packaged_approval != source("src/templates/template_approval.json").replace(b"\r\n", b"\n"):
        raise ValueError("Template approval does not match immutable source")
    # Reject private/candidate sidecars and unapproved datasets before content reads.
    manifest = deployment.validate_package(package)
    result["runtimeManifest"] = {key: value for key, value in manifest.items() if key != "files"}
    # The deployment runtime manifest intentionally omits seed data/. Include
    # those already validated templates in the package confidentiality audit.
    files = {relative.as_posix(): path for path, relative in deployment._files(package)}
    result["executableSha256"] = sha(executable)

    native_file = internal / "native/cspm_native_motion.dll"
    native_hash = sha(native_file)
    result["nativeDllSha256"] = native_hash
    if native_hash != ACCEPTED_NATIVE_SHA256:
        failures.append("Native DLL differs from accepted lifecycle baseline")
    provenance = json.loads((internal / "release-provenance.json").read_text(encoding="utf-8"))
    result["releaseProvenance"] = provenance
    if (provenance.get("sourceSha") != head or provenance.get("defaultMotionEngine") != "native"
            or provenance.get("candidateProfileRequired") is not False
            or provenance.get("nativeDllSha256") != native_hash):
        failures.append("Ordinary release provenance policy or immutable source identity differs")

    archive = CArchiveReader(str(executable))
    pyz_names = [name for name, row in archive.toc.items() if row[-1] == "z"]
    if len(pyz_names) != 1:
        raise ValueError("Expected one embedded project archive")
    pyz = archive.open_embedded_archive(pyz_names[0])
    module_map = {}
    for relative in tracked("src/python"):
        if not relative.endswith(".py"):
            continue
        module = relative[len("src/python/"):]
        module = module[:-len("/__init__.py")] if module.endswith("/__init__.py") else module[:-3]
        module_map[module.replace("/", ".")] = relative
    project_roots = {name.split(".")[0] for name in module_map}
    own_modules = sorted(name for name in pyz.toc if name.split(".")[0] in project_roots)
    unknown = [name for name in own_modules if name not in module_map]
    if unknown:
        failures.append("Archived project module has no committed source mapping")
    required_modules = set(REQUIRED_MODULES)
    if "backend.data_verification" in module_map:
        required_modules.add("backend.data_verification")
    if not required_modules.issubset(own_modules):
        failures.append("Required runtime project modules are absent")
    module_checks = []
    source_scan = []
    for name in own_modules:
        if name not in module_map:
            continue
        relative = module_map[name]
        raw = source(relative)
        expected = compile(raw, relative, "exec", dont_inherit=True, optimize=0)
        differences = code_differences(expected, pyz.extract(name))
        module_checks.append(dict(module=name, sourcePath=relative, matches=not differences,
                                  differences=differences[:12]))
        if differences:
            failures.append("Archived Python source differs: " + name)
        source_scan.append(raw)
    main_raw = source("src/python/main.py")
    main_code = marshal.loads(archive.extract("main"))
    main_diff = code_differences(compile(main_raw, "src/python/main.py", "exec", dont_inherit=True, optimize=0), main_code)
    if main_diff:
        failures.append("Archived main entry point differs")
    source_scan.append(main_raw)
    result["pythonArchive"] = dict(projectModules=len(module_checks), unmappedModules=unknown,
                                    checks=module_checks, mainMatches=not main_diff,
                                    mainDifferences=main_diff[:12], ignoredField="co_filename only")

    expected_assets = set()
    for directory in ("src/qml", "src/assets", "src/templates", "assets", "schema", "docs/spec"):
        expected_assets.update(tracked(directory))
    expected_assets.update(("docs/BIBLE.md", "docs/ROADMAP.md", "docs/CHANGELOG.md", "version.json"))
    # Older immutable pins predate the installable launcher; audit their exact
    # source asset set as well as new packages, without assuming current HEAD.
    expected_assets.update(tracked("scripts/launch_governed_readonly.py"))
    own_prefixes = ("_internal/src/", "_internal/assets/", "_internal/schema/", "_internal/docs/", "_internal/scripts/")
    actual_assets = {relative[len("_internal/"):] for relative in files
                     if relative.startswith(own_prefixes) or relative == "_internal/version.json"}
    if actual_assets != expected_assets:
        failures.append("Project runtime asset set differs from committed source")
    asset_differences = []
    for relative in sorted(actual_assets & expected_assets):
        actual = files["_internal/" + relative].read_bytes()
        expected = source(relative)
        if Path(relative).suffix.lower() in TEXT_SUFFIXES or Path(relative).name == "qmldir":
            actual, expected = actual.replace(b"\r\n", b"\n"), expected.replace(b"\r\n", b"\n")
        if actual != expected:
            asset_differences.append(relative)
    if asset_differences:
        failures.append("Project runtime asset bytes differ beyond text line endings")
    qml = [path for path in expected_assets if path.startswith("src/qml/")]
    result["runtimeAssets"] = dict(sourceFiles=len(expected_assets), packagedFiles=len(actual_assets),
                                  qmlTreeFiles=len(qml), qmlFiles=sum(path.endswith(".qml") for path in qml),
                                  missing=sorted(expected_assets - actual_assets),
                                  unexpected=sorted(actual_assets - expected_assets), differences=asset_differences)

    approved = json.loads(source("src/templates/template_approval.json"))
    approved_hashes = {row["approved_filename"]: row["sha256"].upper()
                       for row in approved.get("templates", []) if row.get("human_approval_status") == "APPROVED"}
    expected_workbooks = {location + name for location in ("data/", "_internal/src/templates/") for name in approved_hashes}
    actual_workbooks = {relative for relative, path in files.items() if path.suffix.lower() in deployment.DATA_SUFFIXES}
    if actual_workbooks != expected_workbooks:
        failures.append("Approved template workbook set differs")
    template_checks = []
    for relative in sorted(actual_workbooks & expected_workbooks):
        path = files[relative]
        verified = sha(path) == approved_hashes[path.name]
        if not verified:
            failures.append("Approved template hash differs")
        with zipfile.ZipFile(path) as template:
            if template.testzip() is not None:
                failures.append("Approved template ZIP invalid")
        template_checks.append(dict(path=relative, sha256=sha(path), approved=verified))
    public_trust_bundles = []
    public_trust_paths = set()
    if "_internal/certifi/cacert.pem" in files:
        try:
            immutable_requirements = source("requirements-release-windows.lock.txt")
        except Exception:
            immutable_requirements = b""
        trust_check = validate_public_trust_bundle(
            "_internal/certifi/cacert.pem", files["_internal/certifi/cacert.pem"], immutable_requirements,
        )
        public_trust_bundles.append(trust_check)
        if trust_check["allowed"]:
            public_trust_paths.add(trust_check["path"])
    result["publicTrustBundles"] = public_trust_bundles
    forbidden_artifacts = []
    for relative, path in files.items():
        parts = tuple(part.lower() for part in Path(relative).parts)
        own = relative.startswith(own_prefixes) or not relative.startswith("_internal/")
        committed_csv = path.suffix.lower() == ".csv" and relative.startswith("_internal/") and relative[len("_internal/"):] in expected_assets
        if ((path.suffix.lower() in PRIVATE_SUFFIXES and not committed_csv and relative not in public_trust_paths) or ".private." in path.name.lower()
                or (own and any(part in PRIVATE_DIRS for part in parts[:-1]))):
            forbidden_artifacts.append(relative)
    if forbidden_artifacts:
        failures.append("Private runtime or diagnostic artifact present")
    result["dataBoundary"] = dict(governedValidationPassed=True, templateChecks=template_checks,
                                   privateArtifacts=forbidden_artifacts, candidateProfileAbsent=True)

    credential_findings = []
    own_files = [path for relative, path in files.items() if relative.startswith(own_prefixes)
                 and relative[len("_internal/"):] in expected_assets
                 or relative in ("_internal/release-provenance.json", "_internal/version.json")]
    for index, path in enumerate(own_files, 1):
        if path.suffix.lower() in (".xlsm", ".xlsx", ".docx"):
            with zipfile.ZipFile(path) as container:
                payloads = (container.read(member) for member in container.namelist())
                for raw in payloads:
                    credential_findings.extend(dict(item=index, rule=label)
                                               for label, pattern in privacy.SECRET_PATTERNS if pattern.search(raw))
        else:
            raw = path.read_bytes()
            if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                raw = raw.decode("utf-16", errors="replace").encode("utf-8")
            credential_findings.extend(dict(item=index, rule=label)
                                       for label, pattern in privacy.SECRET_PATTERNS if pattern.search(raw))
    for index, raw in enumerate(source_scan, len(own_files) + 1):
        credential_findings.extend(dict(item=index, rule=label)
                                   for label, pattern in privacy.SECRET_PATTERNS if pattern.search(raw))
    if credential_findings:
        failures.append("Recognized credential pattern in project payload")
    result["privacyScan"] = dict(projectAssetFiles=len(own_files), archivedSourceFiles=len(source_scan),
                                 findings=credential_findings,
                                 limits="Recognized credential patterns and bounded package provenance; no exhaustive semantic secret claim")
    result["nativeAbiLoadPassed"] = False
    if native_hash == ACCEPTED_NATIVE_SHA256:
        sys.path.insert(0, str(repo / "src/python"))
        from backend.native_motion import NativeBridge
        NativeBridge(native_file)  # ABI/export load only; no HWND or GPU created.
        result["nativeAbiLoadPassed"] = True
    result["repositoryHeadAtEnd"] = git_output("rev-parse", "HEAD").decode().strip()
    if source_sha is None and result["repositoryHeadAtEnd"] != initial_head:
        failures.append("Repository HEAD changed during audit")
    result["passed"] = not failures
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-sha", help="Full immutable build commit; default HEAD (permits later documentation commits)")
    arguments = parser.parse_args()
    repo, package, report = arguments.repo.resolve(), arguments.package.resolve(), arguments.report.resolve()
    if arguments.source_sha is not None and re.fullmatch(r"[0-9a-fA-F]{40}", arguments.source_sha) is None:
        parser.error("--source-sha requires a full 40-character commit identifier")
    if (report.exists() or report.suffix.lower() != ".json" or report.is_relative_to(repo)
            or report.is_relative_to(package)):
        parser.error("Choose a new JSON report outside the repository and package")
    sys.dont_write_bytecode = True
    try:
        result = audit(repo, package, arguments.source_sha)
    except Exception as exc:
        result = dict(schemaVersion=1, verifiedAtUtc=datetime.now(UTC).isoformat(), passed=False,
                      applicationLaunched=False, dataWritten=False,
                      failures=["Package audit could not complete: " + type(exc).__name__],
                      privateFailureDetail=str(exc))
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(passed=result["passed"], failures=result["failures"],
                          projectModules=result.get("pythonArchive", {}).get("projectModules"),
                          qmlTreeFiles=result.get("runtimeAssets", {}).get("qmlTreeFiles"),
                          nativeAbiLoadPassed=result.get("nativeAbiLoadPassed", False))))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
