"""Launch a privately configured governed read-only CSPM installation.

Deployment verifies all runtime resources. Ordinary launch checks executable,
native bridge and provenance identity, plus every governed/local workbook hash.
Use --check-only --audit-runtime for a fresh complete resource audit.
Install this script beside private deployment.private.json; no paths or data
selectors are embedded in source.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import re
import time
import uuid

ROOT = Path(__file__).resolve().parent
USER_DIRECTORIES = frozenset(("data", "backups", "logs"))
USER_FILENAMES = frozenset(("user_settings.json", "machine_id.json", "candidate-machine.json",
    "candidate-profile.json", "prefs.json", "motion.json", "sync_state.json", "cloud_checkout_machine.json",
    "session_draft_snapshot.json", "runtime_session_state.json"))
PAIR_NAMES = ("CSPM.xlsm", "Dockets.xlsm")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def private(relative: Path) -> bool:
    return (relative.parts[0].lower() in USER_DIRECTORIES or relative.name.lower() in USER_FILENAMES
            or relative.name.lower().startswith("session_draft_snapshot"))


def runtime_manifest(package: Path) -> dict:
    if not package.is_dir() or package.is_symlink() or package.is_junction():
        raise ValueError("A real package directory is required.")
    rows = []
    for directory, names, files in os.walk(package, followlinks=False):
        base = Path(directory)
        for name in names + files:
            item = base / name
            if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                raise ValueError("Runtime package contains a link or junction.")
        for name in files:
            item = base / name
            relative = item.relative_to(package)
            if not private(relative):
                rows.append(dict(path=relative.as_posix(), bytes=item.stat().st_size, sha256=sha(item)))
    rows.sort(key=lambda row: row["path"].casefold())
    identity = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()
    if not any(row["path"] == "CSPM.exe" for row in rows):
        raise ValueError("Runtime package is missing CSPM.exe.")
    return dict(schemaVersion=1, files=rows, fileCount=len(rows), bytes=sum(row["bytes"] for row in rows), manifestSha256=identity)


def kernel_api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


@contextmanager
def protected_read(path: Path):
    kernel = kernel_api()
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def exclusive_launcher():
    kernel = kernel_api()
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, "Local\\CSPMGovernedNormalMainReadOnly")
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    try:
        if error == 183:
            raise RuntimeError("A normal CSPM launcher is already active.")
        yield
    finally:
        kernel.CloseHandle(handle)


def active_cspm_sessions() -> list[dict]:
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
            ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
            ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
            ("exe", wintypes.WCHAR * 260)]
    kernel = kernel_api()
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    sessions = []
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            if entry.exe.casefold() in {"cspm.exe", "cspm_recovery.exe"}:
                sessions.append(dict(processId=int(entry.pid), name=entry.exe))
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return sessions


def verified_configuration(configuration: Path, *, audit_runtime: bool = False,
                           timings: dict | None = None):
    started = time.perf_counter()
    deployment = json.loads(configuration.read_text(encoding="utf-8"))
    if deployment.get("schemaVersion") != 1 or deployment.get("readOnlyVerification") is not True:
        raise ValueError("The normal read-only deployment configuration is invalid.")
    configured_package = Path(deployment["package"])
    if configured_package.is_symlink() or configured_package.is_junction():
        raise ValueError("The installed runtime directory must not be a link.")
    package = configured_package.resolve()
    profile = Path(deployment["profile"]).resolve()
    if package == profile or package in profile.parents or profile in package.parents:
        raise ValueError("The persistent profile must be separate from the installed runtime.")
    for relative in ("CSPM.exe", "_internal", "_internal/native", "_internal/native/cspm_native_motion.dll", "_internal/release-provenance.json"):
        path = package / relative
        if path.is_symlink() or path.is_junction():
            raise ValueError("Launch identity files must not be links.")
    release = json.loads((package / "_internal/release-provenance.json").read_text(encoding="utf-8"))
    if (release != deployment["releaseProvenance"] or release.get("sourceSha") != deployment["sourceSha"]
            or not isinstance(deployment["sourceSha"], str)
            or re.fullmatch(r"[0-9a-fA-F]{40}", deployment["sourceSha"]) is None
            or release.get("sourceStatus") != "clean" or release.get("sourceDirty") is not False
            or release.get("candidateProfileRequired") is not False
            or release.get("defaultMotionEngine") != "native"
            or release.get("nativeDllSha256") != deployment["nativeDllSha256"]):
        raise ValueError("Installed release provenance differs from the verified canonical main.")
    if sha(package / "CSPM.exe") != deployment["executableSha256"]:
        raise ValueError("The installed executable changed.")
    if sha(package / "_internal/native/cspm_native_motion.dll") != deployment["nativeDllSha256"]:
        raise ValueError("The accepted native bridge changed.")
    if timings is not None:
        timings["runtimeIdentitySeconds"] = round(time.perf_counter() - started, 6)
    if audit_runtime:
        audit_started = time.perf_counter()
        if runtime_manifest(package) != deployment["runtime"]:
            raise ValueError("The installed runtime resources differ from the verified main package.")
        if timings is not None:
            timings["runtimeAuditSeconds"] = round(time.perf_counter() - audit_started, 6)
    data_started = time.perf_counter()
    settings = json.loads((profile / "user_settings.json").read_text(encoding="utf-8"))
    local = Path(settings["localDataDir"]).resolve()
    master = Path(settings["masterDataDir"]).resolve()
    if settings.get("readOnlyVerification") is not True:
        raise ValueError("The normal profile no longer enables read-only verification.")
    if local != Path(deployment["localReplica"]).resolve() or master != Path(deployment["governedSource"]).resolve():
        raise ValueError("The normal profile selectors changed; data identity requires review.")
    if local == master or local in master.parents or master in local.parents:
        raise ValueError("The local replica must be separate from the governed source.")
    expected = deployment["pairHashes"]
    if set(expected) != set(PAIR_NAMES):
        raise ValueError("Expected governed pair is incomplete.")
    identity = hashlib.sha256("|".join(expected[name] for name in PAIR_NAMES).encode("ascii")).hexdigest()[:12].upper()
    if identity != deployment["datasetIdentity"]:
        raise ValueError("The configured dataset identity is invalid.")
    manifest_path = Path(deployment["releaseManifest"]).resolve()
    if not manifest_path.is_relative_to(master / ".cspm_releases"):
        raise ValueError("The governed manifest is outside its configured release archive.")
    # Release shared handles before the normal user session, allowing OneDrive refresh.
    with ExitStack() as guard:
        for path in [manifest_path] + [folder / name for folder in (local, master) for name in PAIR_NAMES]:
            guard.enter_context(protected_read(path))
        if sha(manifest_path) != deployment["releaseManifestSha256"]:
            raise ValueError("The accepted locally governed release manifest changed.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("releaseId") != deployment["releaseId"] or manifest.get("files") != expected:
            raise ValueError("The locally governed release identity changed.")
        local_hashes = {name: sha(local / name) for name in PAIR_NAMES}
        master_hashes = {name: sha(master / name) for name in PAIR_NAMES}
        if local_hashes != expected or master_hashes != expected:
            raise ValueError("The local or shared pair changed; no automatic refresh or overwrite is permitted.")
        if (master / ".cspm_checkout.json").exists() or list(master.glob(".cspm_checkout_recovering_*")):
            raise ValueError("A governed checkout requires review before this read-only launch.")
        if any((master / ("~$" + name)).exists() for name in PAIR_NAMES):
            raise ValueError("An Excel writer may be active against the governed pair.")
    if timings is not None:
        timings["governedDataSeconds"] = round(time.perf_counter() - data_started, 6)
        timings["configurationVerificationSeconds"] = round(time.perf_counter() - started, 6)
    return deployment, package, profile, local, master


def normal_environment(profile: Path) -> dict:
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith(("CSPM_", "QT_", "QSG_", "QML_", "QTWEBENGINE")) or key in {
                "PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX"}:
            environment.pop(key)
    environment.update(CSPM_RUNTIME_DIR=str(profile), CSPM_DATA_DIR=str(profile),
        CSPM_EXECUTABLE_ROOT=str(profile), CSPM_LOG_DIR=str(profile / "logs"),
        CSPM_EXPORT_DIR=str(profile / "exports"), CSPM_VERIFY_DATA_READ_ONLY="1",
        PYTHONDONTWRITEBYTECODE="1")
    # Keep ordinary Windows AppData/motion preference and the existing machine identity.
    return environment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--audit-runtime", action="store_true", help="Also hash all installed runtime resources; intended for deployment or an explicit integrity audit")
    parser.add_argument("--configuration", type=Path, default=ROOT / "deployment.private.json")
    args = parser.parse_args()
    started = time.perf_counter()
    report = dict(createdAtUtc=datetime.now(UTC).isoformat(), readOnlyVerification=True,
        workbookWritesAllowed=False, checkoutAllowed=False, publicationAllowed=False,
        serverFreshnessVerified=False, automaticUiActions=False, keepAwake=False, forcedTermination=False,
        runtimeVerification="complete-runtime-audit" if args.audit_runtime else "executable-native-provenance",
        completeRuntimeAuditRequested=args.audit_runtime, timings={})
    reports = args.configuration.resolve().parent / "launch-reports"
    reports.mkdir(parents=True, exist_ok=True)
    report_path = reports / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".private.json")
    process = None
    try:
        with exclusive_launcher(), ExitStack() as local_guard:
            sessions = active_cspm_sessions()
            if sessions:
                raise RuntimeError("Close the existing CSPM session before launching main.")
            deployment, package, profile, local, master = verified_configuration(
                args.configuration, audit_runtime=args.audit_runtime, timings=report["timings"])
            report.update(sourceSha=deployment["sourceSha"], datasetIdentity=deployment["datasetIdentity"],
                executableSha256=deployment["executableSha256"], sharedHandlesReleasedBeforeLaunch=True)
            report["timings"]["preflightSeconds"] = round(time.perf_counter() - started, 6)
            if args.check_only:
                report.update(ok=True, launched=False)
            else:
                replica_started = time.perf_counter()
                for name in PAIR_NAMES:
                    local_guard.enter_context(protected_read(local / name))
                if {name: sha(local / name) for name in PAIR_NAMES} != deployment["pairHashes"]:
                    raise ValueError("The local replica changed immediately before launch.")
                report["timings"]["prelaunchReplicaSeconds"] = round(time.perf_counter() - replica_started, 6)
                spawn_started = time.perf_counter()
                process = subprocess.Popen([str(package / "CSPM.exe"), "--verify-data-read-only"],
                    cwd=package, env=normal_environment(profile), creationflags=subprocess.CREATE_NO_WINDOW)
                report.update(launched=True, processId=process.pid, localReplicaProtectionHeld=True)
                report["processCreatedAtUtc"] = datetime.now(UTC).isoformat()
                report["timings"]["processSpawnSeconds"] = round(time.perf_counter() - spawn_started, 6)
                report["timings"]["launchDelaySeconds"] = round(time.perf_counter() - started, 6)
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                process.wait()
                after_local = {name: sha(local / name) for name in PAIR_NAMES}
                after_master = {name: sha(master / name) for name in PAIR_NAMES}
                report.update(ok=process.returncode == 0 and after_local == deployment["pairHashes"],
                    processExitCode=process.returncode, localHashes=after_local, governedHashes=after_master,
                    localWorkbooksUnchanged=after_local == deployment["pairHashes"],
                    governedPairStillMatches=after_master == deployment["pairHashes"],
                    localReplicaProtectionHeld=False, completedAtUtc=datetime.now(UTC).isoformat())
            report["timings"]["totalSeconds"] = round(time.perf_counter() - started, 6)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            if args.check_only:
                print(json.dumps(dict(ok=True, launched=False, datasetIdentity=report["datasetIdentity"],
                                      runtimeVerification=report["runtimeVerification"], timings=report["timings"], report=str(report_path))))
            return 0 if report["ok"] else 1
    except Exception as error:
        report.update(ok=False, error=repr(error), processPreserved=bool(process is not None and process.poll() is None))
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.check_only:
            print(json.dumps(dict(ok=False, launched=False, error=repr(error), report=str(report_path))))
        elif process is None:
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
            user.MessageBoxW(None, "CSPM could not start with its verified read-only configuration.\n"
                "Review the private launch report before retrying.\n\n" + str(report_path), "CSPM", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
