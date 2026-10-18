# Mandatory Post-Change Delivery Gate (`__CSPM`)

> **Core Code Changes vs. File/Matter Data Entry:**
> - **Core Code / UI / Schema Changes** (creating or modifying files in `./src/python/`, `./src/qml/`, `./schema/`, `./src/templates/`, `CSPM.spec`, or build scripts) $\rightarrow$ **MUST** run `py_compile`/`qmllint`/tests, recompile the standalone `.exe` via `./scripts/build_and_push.py`, and commit/push to Git cloud.
> - **Data-Only / Matter Intake / Document Operations** (onboarding clients or matters into `CSPM.xlsm` or `Dockets.xlsm`, logging dockets/disbursements, copying files into `Vault/`, or generating client `.docx` checklists/drafts) $\rightarrow$ **MUST NOT** recompile `CSPM.exe` unless core repository code was also modified. Use `--skip-build` (or let `./scripts/build_and_push.py` auto-skip the `.exe` build when no core bundled code changed).

## Standard Execution Commands

For core application code changes:
```powershell
python ./scripts/build_and_push.py --restart-running -m "<descriptive commit message>" --tests <targeted_test_files>
```

For data-entry / onboarding / test / doc updates (no `.exe` rebuild):
```powershell
python ./scripts/build_and_push.py --skip-build -m "<descriptive commit message>" --tests <targeted_test_files>
```

## Safety & Portability Invariants
1. **Repository-Relative Paths Only:** Never hardcode drive letters or workstation usernames in scripts, rules, or documentation.
2. **No Data / Build Artifact Pollution in Git:** Never stage `./build/`, `./dist/`, `./to_delete/`, `./data/`, or any `.xlsm` / `.db` / `.sqlite` runtime data files.
3. **Clean Provenance:** Commit source/schema/test/doc updates before or during `./scripts/build_and_push.py` so the compiled standalone `.exe` embeds the committed Git `HEAD` SHA.
