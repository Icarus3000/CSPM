"""Portable verify -> build standalone .exe -> commit & push pipeline for CSPM.

Uses strictly repository-relative paths (./...) and environment variables.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = ROOT_DIR / "scripts" / "build_release.py"
QMLLINT_PS1 = ROOT_DIR / "scripts" / "qmllint.ps1"
QMLLINT_SH = ROOT_DIR / "scripts" / "qmllint.sh"
DIST_EXE_REL = Path("dist") / "CSPM" / "CSPM.exe"

ALLOWED_STAGE_PREFIXES = (
    "src/",
    "schema/",
    "scripts/",
    "tests/",
    ".agent/",
)
ALLOWED_STAGE_ROOT_FILES = {
    ".gitignore",
    "GEMINI.md",
    "AGENTS.md",
    "README.md",
    "task.md",
    "implementation.md",
    "implementation_plan.md",
    "pytest.ini",
    "requirements.txt",
    "requirements-build.txt",
    "requirements-linux-build.txt",
    "usage-control.json",
}
FORBIDDEN_EXTENSIONS = {".xlsm", ".xlsx", ".xls", ".db", ".sqlite", ".sqlite3", ".lock"}
FORBIDDEN_DIR_PARTS = {
    "build",
    "dist",
    "target",
    "to_delete",
    "data",
    "backups",
    "logs",
    "__pycache__",
    ".pytest_cache",
    ".workspace-usage",
}


def _git_changed_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT_DIR,
        text=True,
    )
    paths: list[str] = []
    for raw_line in out.splitlines():
        if len(raw_line) < 4:
            continue
        entry = raw_line[3:].strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1].strip()
        entry = entry.strip('"').replace("\\", "/")
        if entry:
            paths.append(entry)
    return paths


def _is_safe_to_stage(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").removeprefix("./")
    parts = Path(norm).parts
    if any(part in FORBIDDEN_DIR_PARTS or part.startswith(".venv") for part in parts):
        return False
    ext = Path(norm).suffix.lower()
    if ext in FORBIDDEN_EXTENSIONS:
        return False
    if norm in ALLOWED_STAGE_ROOT_FILES:
        return True
    return any(norm.startswith(prefix) for prefix in ALLOWED_STAGE_PREFIXES)


def verify_changes(changed_files: list[str], extra_tests: list[str]) -> None:
    print("\n=== [1/4] Running Verification Gate (py_compile + qmllint + unit tests) ===")
    py_files = [
        rel
        for rel in changed_files
        if rel.endswith(".py") and (ROOT_DIR / rel).is_file()
    ]
    if py_files:
        print(f"[py_compile] Checking {len(py_files)} Python file(s)...")
        subprocess.run([sys.executable, "-m", "py_compile", *py_files], cwd=ROOT_DIR, check=True)
    else:
        print("[py_compile] No modified Python files detected; checking core controllers...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                "src/python/main.py",
                "src/python/backend/app_controller.py",
            ],
            cwd=ROOT_DIR,
            check=True,
        )

    qml_files = [
        rel
        for rel in changed_files
        if rel.endswith(".qml") and (ROOT_DIR / rel).is_file()
    ]
    if qml_files:
        print(f"[qmllint] Checking {len(qml_files)} QML file(s)...")
        if os.name == "nt" and QMLLINT_PS1.is_file():
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts/qmllint.ps1",
                    *qml_files,
                ],
                cwd=ROOT_DIR,
                check=True,
            )
        elif QMLLINT_SH.is_file():
            subprocess.run(["bash", "scripts/qmllint.sh", *qml_files], cwd=ROOT_DIR, check=True)

    if extra_tests:
        print(f"[pytest] Running {len(extra_tests)} targeted test suite(s)...")
        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        subprocess.run([sys.executable, "-m", "pytest", *extra_tests], cwd=ROOT_DIR, env=env, check=True)


def _is_file_locked(target_exe: Path) -> bool:
    if not target_exe.exists():
        return False
    try:
        with open(target_exe, "a+b"):
            return False
    except OSError:
        return True


def _stop_running_executable(exe_name: str = "CSPM.exe") -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["taskkill", "/IM", exe_name, "/F"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        time.sleep(1.0)
        return True
    return False


def stage_and_commit(message: str | None) -> bool:
    print("\n=== [2/4] Staging Safe Source/Schema/Test/Doc Changes ===")
    changed = _git_changed_files()
    rule_file = ROOT_DIR / ".agent" / "rules" / "post_change_pipeline.md"
    if rule_file.is_file() and ".agent/rules/post_change_pipeline.md" not in changed:
        changed.append(".agent/rules/post_change_pipeline.md")
    stageable = [rel for rel in changed if _is_safe_to_stage(rel) and (ROOT_DIR / rel).exists()]
    if not stageable:
        print("[git] Working tree has no uncommitted stageable source changes.")
        return False

    print(f"[git] Staging {len(stageable)} file(s):")
    for rel in stageable:
        print(f"  + {rel}")
    subprocess.run(["git", "add", "-f", "--", *stageable], cwd=ROOT_DIR, check=True)

    staged_check = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT_DIR,
        text=True,
    ).splitlines()
    if not staged_check:
        print("[git] No staged diffs to commit.")
        return False

    commit_msg = (message or "").strip()
    if not commit_msg:
        summary_files = ", ".join(Path(p).name for p in staged_check[:4])
        if len(staged_check) > 4:
            summary_files += f" (+{len(staged_check) - 4} more)"
        commit_msg = f"chore(sync): update {summary_files}"

    subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT_DIR, check=True)
    return True


def _sha256_upper(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def _sync_governed_writer_deployment_manifest() -> None:
    """Keep %LOCALAPPDATA%/CSPM/writer-deployment.private.json aligned with deployed package."""
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_appdata:
        return
    cfg_path = Path(local_appdata) / "CSPM" / "writer-deployment.private.json"
    if not cfg_path.is_file():
        return
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict) or cfg.get("launchPolicy") != "normal-governed-writer":
            return
        package_dir = Path(cfg.get("package", "")).resolve()
        prov_path = package_dir / "_internal" / "release-provenance.json"
        exe_path = package_dir / "CSPM.exe"
        dll_path = package_dir / "_internal" / "native" / "cspm_native_motion.dll"
        if not (prov_path.is_file() and exe_path.is_file() and dll_path.is_file()):
            return
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        if prov.get("sourceStatus") != "clean" or prov.get("sourceDirty") is not False:
            print(
                "[build] WARNING: Deployed release-provenance.json is not clean; "
                "skipping writer-deployment.private.json update."
            )
            return
        cfg["sourceSha"] = prov["sourceSha"]
        cfg["releaseProvenance"] = prov
        cfg["executableSha256"] = _sha256_upper(exe_path)
        cfg["nativeDllSha256"] = _sha256_upper(dll_path)
        if "runtime" in cfg:
            sys.path.insert(0, str(ROOT_DIR / "scripts"))
            from launch_governed_readonly import runtime_manifest

            cfg["runtime"] = runtime_manifest(package_dir)
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(
            f"[build] Synced governed writer manifest: {cfg_path} "
            f"(sourceSha={cfg['sourceSha'][:8]}, exeSha={cfg['executableSha256'][:12]}...)"
        )
    except Exception as exc:
        print(f"[build] WARNING: Could not sync writer-deployment.private.json: {exc}")


def build_standalone_exe(*, restart_running: bool = False, no_deploy: bool = False) -> Path:
    print("\n=== [3/4] Recompiling Standalone Executable (.exe) ===")
    if not BUILD_SCRIPT.is_file():
        raise FileNotFoundError(f"Build script not found: {BUILD_SCRIPT.relative_to(ROOT_DIR)}")

    dist_exe = ROOT_DIR / DIST_EXE_REL
    was_running = False

    if _is_file_locked(dist_exe):
        if restart_running:
            print(f"[build] Target executable {DIST_EXE_REL} is locked; stopping running CSPM.exe (--restart-running)...")
            was_running = _stop_running_executable("CSPM.exe")
        else:
            raise RuntimeError(
                f"Target executable {DIST_EXE_REL} is currently locked by a running process. "
                "Close CSPM.exe or pass --restart-running."
            )

    cmd = [sys.executable, "scripts/build_release.py"]
    if no_deploy:
        cmd.append("--no-deploy")
    else:
        # Attempt to stop running CSPM.exe if --restart-running is passed before deploy
        if restart_running and os.name == "nt":
            was_running = _stop_running_executable("CSPM.exe") or was_running

    subprocess.run(cmd, cwd=ROOT_DIR, check=True)

    if not dist_exe.is_file():
        raise FileNotFoundError(f"Expected compiled executable missing at ./{DIST_EXE_REL.as_posix()}")

    if not no_deploy:
        _sync_governed_writer_deployment_manifest()

    mtime_iso = datetime.fromtimestamp(dist_exe.stat().st_mtime).astimezone().isoformat()
    print(f"[build] Standalone executable ready: ./{DIST_EXE_REL.as_posix()} ({dist_exe.stat().st_size} bytes, modified {mtime_iso})")

    if was_running and restart_running and os.name == "nt":
        print(f"[build] Relaunching ./{DIST_EXE_REL.as_posix()}...")
        subprocess.Popen([str(dist_exe)], cwd=dist_exe.parent)

    return dist_exe


def push_to_remote() -> str:
    print("\n=== [4/4] Pushing Committed Changes to Git Cloud (origin) ===")
    subprocess.run(["git", "push"], cwd=ROOT_DIR, check=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
    print(f"[git] Successfully pushed HEAD ({sha}) to origin.")
    return sha


CORE_BUILD_PREFIXES = (
    "src/python/",
    "src/qml/",
    "src/templates/",
    "schema/",
)
CORE_BUILD_FILES = {
    "CSPM.spec",
    "scripts/build_release.py",
}


def _has_core_code_changes(changed_files: list[str]) -> bool:
    for rel in changed_files:
        norm = rel.replace("\\", "/").lstrip("./")
        if norm in CORE_BUILD_FILES:
            return True
        if any(norm.startswith(prefix) for prefix in CORE_BUILD_PREFIXES):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify, optionally build standalone .exe on core code changes, and push to Git cloud.")
    parser.add_argument("-m", "--message", help="Commit message for staged source/schema/test/doc changes")
    parser.add_argument("--tests", nargs="*", default=[], help="Targeted pytest files to execute in the verification gate")
    parser.add_argument("--restart-running", action="store_true", help="Stop running CSPM.exe before build/deploy and relaunch afterward")
    parser.add_argument("--no-deploy", action="store_true", help="Build ./dist/CSPM/CSPM.exe without deploying to external program folder")
    parser.add_argument("--skip-build", action="store_true", help="Run verification and git sync without recompiling .exe")
    parser.add_argument("--force-build", action="store_true", help="Force recompiling .exe even when no core application code files changed")
    parser.add_argument("--skip-push", action="store_true", help="Run verification, build, and local commit without git push")
    args = parser.parse_args()

    changed = _git_changed_files()
    core_changed = _has_core_code_changes(changed)
    verify_changes(changed, args.tests)
    stage_and_commit(args.message)

    dist_exe = ROOT_DIR / DIST_EXE_REL
    should_build = args.force_build or (not args.skip_build and core_changed)
    if should_build:
        dist_exe = build_standalone_exe(
            restart_running=args.restart_running,
            no_deploy=args.no_deploy,
        )
    else:
        reason = "--skip-build passed" if args.skip_build else "no core application code changes detected"
        print(f"\n=== [3/4] Skipping Standalone .exe Rebuild ({reason}) ===")

    if not args.skip_push:
        sha = push_to_remote()
    else:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()

    print("\n==================================================")
    print("  POST-CHANGE DELIVERY PIPELINE COMPLETE")
    print(f"  HEAD Commit SHA : {sha}")
    if dist_exe.is_file():
        mtime = datetime.fromtimestamp(dist_exe.stat().st_mtime).astimezone().isoformat()
        print(f"  Executable Path : ./{DIST_EXE_REL.as_posix()}")
        print(f"  Executable Time : {mtime}")
    print("==================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
