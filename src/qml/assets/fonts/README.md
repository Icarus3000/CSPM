# Portable CSPM icons

`CSPMSymbols.ttf` contains the Fluent System Icons regular vector outlines used
by CSPM on Linux. Its private-use codepoints match the app's existing Windows
MDL2 model values, so navigation/actions retain the same meaning. Standard
Unicode/emoji aliases provide consistent monochrome tray and calendar controls.
Windows keeps its installed Segoe MDL2/Fluent symbols and original text fonts.

Upstream: [Microsoft Fluent System Icons](https://github.com/microsoft/fluentui-system-icons),
MIT license (included as `LICENSE.txt`). The original proprietary Windows Segoe
fonts are not distributed. The checked-in JSON records the immutable upstream
revision, source hashes, glyph aliases and generated font hash.

To reproduce the bundled font with the optional development package `fonttools`:

```bash
python scripts/build_symbol_font.py --source-dir /tmp/cspm-symbol-upstream
```

The generator downloads only hash-verified inputs pinned to the recorded source
revision. Packaging and ordinary startup use the checked-in font without network
access or `fonttools`. `configure_application_typography()` registers the font
before QML and selects Fedora's Noto Sans when available. The QML typography
module uses that application font for forms, reports, dialogs and the shell.
