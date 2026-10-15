#!/usr/bin/env python3
"""Build the governed Fedora bundle and install its per-user desktop launcher."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def source_hash() -> str:
    digest = hashlib.sha256()
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    for name in sorted(set(names.decode().split("\0")) - {""}):
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def desktop_text(launcher: Path, icon: Path) -> str:
    def quote(value: Path) -> str:
        # Desktop Exec quoting is not shell quoting.
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    return (
        "[Desktop Entry]\nType=Application\nName=CSPM\n"
        "GenericName=Practice Management\nComment=Practice management console\n"
        f"Exec={quote(launcher)}\nIcon={icon}\nTerminal=false\n"
        "Categories=Office;Finance;\nStartupNotify=true\nStartupWMClass=CSPM\n"
    )


def install_launcher() -> Path:
    applications = Path.home() / ".local/share/applications"
    applications.mkdir(parents=True, exist_ok=True)
    target = applications / "cspm.desktop"
    if target.exists():
        backup = ROOT / "logs/installation"
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup / f"cspm-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.desktop")
    target.write_text(desktop_text(ROOT / "launch.sh", ROOT / "dist/CSPM/_internal/src/assets/app_icon_preview.png"), encoding="utf-8")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(applications)], check=True)
    if shutil.which("kbuildsycoca6"):
        subprocess.run(["kbuildsycoca6", "--noincremental"], check=True, stdout=subprocess.DEVNULL)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--install-only", action="store_true", help="Install an already verified bundle launcher")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("This builder targets Linux. Use build_release.py on Windows.")
    if args.install_only:
        if not (ROOT / "dist/CSPM/CSPM").is_file():
            parser.error("Build a bundle before installing its launcher.")
        print(f"Installed: {install_launcher()}")
        return
    from build_release import validate_templates
    templates = ROOT / "src/templates"
    validate_templates(templates, templates / "template_approval.json")
    before_hash = source_hash()
    work = ROOT / "build/linux"
    work.mkdir(parents=True, exist_ok=True)
    provenance = {
        "schemaVersion": 2, "repository": "https://github.com/Icarus3000/CSPM.git",
        "sourceSha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "sourceStatus": "modified" if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip() else "clean",
        "sourceTreeSha256": before_hash,
        "buildTimestampUtc": datetime.now(timezone.utc).isoformat(),
        "platform": "linux-x86_64", "defaultMotionEngine": "plasma",
        **json.loads((ROOT / "version.json").read_text(encoding="utf-8")),
    }
    (work / "release-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    staging = ROOT / f"dist_staging_linux_{os.getpid()}"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(staging), "--workpath", str(work),
                    str(ROOT / "packaging/cspm_linux.spec")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(staging / "CSPM/CSPM_Recovery"),
                    "--workpath", str(work / "recovery"),
                    str(ROOT / "packaging/cspm_recovery_linux.spec")], cwd=ROOT, check=True)
    if source_hash() != before_hash:
        raise RuntimeError("Source changed during packaging; the staged bundle is retained for inspection.")
    bundle = staging / "CSPM"
    for path in ("src/qml/DetachedShellWindow.qml", "src/templates/CSPM.xlsm", "src/templates/Dockets.xlsm", "src/assets/app_icon.ico"):
        if not (bundle / "_internal" / path).is_file():
            raise RuntimeError(f"Bundle missing required asset: {path}")
    manifest = []
    for path in sorted(bundle.rglob("*")):
        if path.is_file():
            manifest.append({"path": path.relative_to(bundle).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size})
    (bundle / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    destination = ROOT / "dist"
    if destination.exists():
        archive = ROOT / "to_delete" / f"dist__before_linux_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(archive))
    staging.rename(destination)
    (ROOT / "launch.sh").chmod(0o755)
    print(f"Fedora bundle: {destination / 'CSPM/CSPM'}")
    if args.install:
        print(f"Installed: {install_launcher()}")


if __name__ == "__main__":
    main()
