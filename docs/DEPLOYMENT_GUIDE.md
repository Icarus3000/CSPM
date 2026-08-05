# CSPM Deployment Guide

## Overview
This document governs the official release build, compilation, and deployment strategy for CSPM Phase 9 (Installer, Backup, Recovery, and Safe Execution).

## Build-Tool Bootstrap
To compile the installer, you must provision Inno Setup.
Run `scripts/bootstrap_build_tools.ps1` from an **elevated (Administrator) PowerShell** to automatically install the compiler via Winget or Chocolatey. 
*Note: Due to Windows security constraints, this tool requires manual elevation and cannot be run autonomously in an unprivileged shell.*

## One-Command Release Build
To generate a production-ready installer:
```powershell
python scripts/build_release.py --installer --validate
```
This script sequentially:
1. Validates `version.json`
2. Invokes PyInstaller for the main application (`CSPM.exe`)
3. Invokes PyInstaller for the recovery utility (`CSPM_Recovery.exe`)
4. Packages essential schema and template assets.
5. Invokes ISCC (Inno Setup) to compile `dist/CSPM-Setup-<version>.exe`.
*(Currently, step 5 is blocked until manual elevation provisions ISCC.exe).*

## Installation & First-Run
- **Directory**: Installs to `{localappdata}\CSPM` to avoid Requiring Admin to run.
- **Templates**: Installs initial blank/template `CSPM.xlsm` and `Dockets.xlsm` into `{localappdata}\CSPM\data`.
- **First-Run**: On initial launch, if the data is blank, users must set up their firm profile or migrate backups. 
- **Upgrades**: Upgrades cleanly replace binaries (`CSPM.exe` and `CSPM_Recovery.exe`) but use the `onlyifdoesntexist` flag to protect the `data\` and `backups\` folders.

## Backup and Restore Engine
- **Backup Location**: Snapshots reside in `{localappdata}\CSPM\backups\CSPM\snapshots`.
- **Restore Architecture**: The UI generates a `pending_restore.json` payload, then delegates restoration to the independent `CSPM_Recovery.exe`.
- **Recovery Engine**: Safely validates checksums, creates a pre-restore safety copy, and performs the physical overwrite only when Excel locks are cleared.

## Uninstallation
- Removing CSPM deletes binaries, PyInstaller caches, and Start Menu shortcuts.
- By default, uninstallation **preserves** the `data\` and `backups\` directories to ensure user data is never destroyed without explicit consent.

## Disaster Recovery
If CSPM fails to boot (e.g. QML error):
1. Open the Start Menu.
2. Select "CSPM Recovery Utility".
3. Select a known-good backup package.
4. Follow the console prompts to perform a safe restoration.

## Code-Signing Readiness
The current technical installer `CSPM-Setup.exe` is **unsigned**.
For commercial deployment (A+ grade), an official Authenticode / EV certificate must be provisioned. This is currently marked as **Blocked by Required User Decision**.
