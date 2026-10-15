# CSPM

## Fedora KDE desktop

Use a local Python 3.13 environment with the same pinned Qt/backend as Windows:

```bash
python3 -m venv .venv-bootstrap
.venv-bootstrap/bin/pip install uv
.venv-bootstrap/bin/uv python install 3.13
.venv-bootstrap/bin/uv venv --python 3.13 .venv-fedora
.venv-bootstrap/bin/uv pip install --python .venv-fedora/bin/python -r requirements-linux-build.txt -r requirements-dev.txt
.venv-fedora/bin/python scripts/build_linux_app.py
.venv-fedora/bin/python scripts/build_linux_app.py --install-only
./launch.sh
```

The KDE launcher starts `dist/CSPM/CSPM`. On Wayland, `launch.sh` defaults to
XWayland to preserve the desktop light-burst flight effects; Plasma owns move,
resize and maximize/restore. `QT_QPA_PLATFORM` remains overridable. Linux text
uses Noto Sans/the desktop fallback and portable bundled vector glyphs.

Configure a native OneDrive synced `masterDataDir` and a separate local
`localDataDir` in Data Folder Setup. Launchers may set absolute
`CSPM_MASTER_DATA_DIR` and `CSPM_LOCAL_DATA_DIR`. The shared Windows checkout,
common-ancestor hashes and conflict protections remain; concurrent editing is
unsupported. `./launch.sh --verify-data-read-only` disables checkout and writes.

LibreOffice supplies Linux Word/Excel supplier-document conversion. Recovery
is `dist/CSPM/CSPM_Recovery/CSPM_Recovery`; `--status` inspects configuration and
locks without writes. Linux QML lint uses `bash scripts/qmllint.sh`.

Build and validation scope:
[Fedora checkpoint](docs/FEDORA_DESKTOP_BUILD_2026-10-14.md).


## Bootstrap

Use one command path for local setup on any machine:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_dev_env.ps1
```

That script will:

1. resolve or rebuild the machine-local virtual environment
2. install runtime and dev requirements
3. patch the Qt for Python qmllint popup issue in the selected environment
4. verify `pytest`, `pyright`, and `PySide6` imports

## Quality Gates

Run the full local gate suite with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_gates.ps1
```

The gate suite now enforces:

1. repo hygiene
2. Python compilation with pycache redirected outside source trees
3. active workbook integrity checks
4. qmllint no-new-warnings policy (normalized by file/message/category so line-number churn does not create false positives)
5. pyright no-new-issues policy using the active machine-local venv
6. pytest

## Support Diagnostics

Create a local support bundle with workbook health and Git context:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_support_diagnostics.ps1
```

The bundle is written under `logs/support_diagnostics/`.

## Notes

1. GUI and WebEngine smoke tests still need a real desktop session outside this shell sandbox.
2. Generated caches and test temp files are routed into `outputs/`.
