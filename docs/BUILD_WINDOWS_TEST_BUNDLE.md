# Windows Test Bundle Build

This project can be packaged as a portable Windows test bundle without installing extra build tools.

The build script:

- Copies a private Python runtime into the bundle.
- Copies app source/assets/schema/data/docs into the bundle.
- Compiles a tiny `CSPM.exe` launcher (C#) that starts `src/python/main.py` with the private runtime.
- Produces a zip archive for distribution.

## Command

From the repo root:

```powershell
.\scripts\build_windows_test_bundle.ps1
```

## Output

- Folder: `dist/CSPM-TestBundle`
- Zip: `dist/CSPM-TestBundle.zip`

## Notes

- This is a test distributable (portable folder + launcher `.exe`), not a single-file native compile.
- No Python installation is required on the target machine because the runtime is bundled.
- First launch can be slower due to runtime initialization and QML/plugin loading.
- Use `run_debug_console.cmd` in the bundle folder to run with a console for troubleshooting.
