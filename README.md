# CSPM

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
