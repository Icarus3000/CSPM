#!/usr/bin/env python3
"""Rebuild the shipped Linux glyph font from pinned MIT Fluent vector outlines.

Requires the optional development dependency fonttools. Normal application
startup and packaging use the checked-in TTF and require no font tooling/network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from fontTools import subset
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "src/qml/assets/fonts"
UPSTREAM_COMMIT = "a347af95478f989038cccbf085978865264c048a"
UPSTREAM_BASE = f"https://raw.githubusercontent.com/microsoft/fluentui-system-icons/{UPSTREAM_COMMIT}"
SOURCE_HASHES = {
    "FluentSystemIcons-Regular.ttf": "f977ae5bfb46661e7ba94b098e0d7720e27af888e57b9b14e239933ac4c0e6f4",
    "FluentSystemIcons-Regular.json": "c6e91d8b156b6d29aff3aeccd8d6b9752c2365c9f9ad02b194d5d791da7abee8",
}

# Retain existing semantic model values and Windows rendering. Only the bundled
# font's cmap changes; the original Fluent outlines remain unmodified.
ICON_MAP = {
    "E70F": "edit", "E713": "settings", "E71B": "link", "E721": "search",
    "E72B": "arrow_left", "E73E": "checkmark", "E740": "full_screen_maximize",
    "E74D": "delete", "E77B": "person", "E787": "calendar", "E7C3": "folder",
    "E80F": "home", "E823": "clock", "E825": "money", "E82D": "document",
    "E840": "pin", "E8A0": "certificate", "E8A5": "receipt", "E8A6": "arrow_download",
    "E8B7": "document_arrow_up", "E8BB": "dismiss", "E8C7": "receipt_money",
    "E8D2": "building_bank", "E90E": "receipt", "E912": "arrow_swap",
    "E921": "subtract", "E922": "square", "E923": "square_multiple",
    "E9D2": "data_pie", "E9D9": "data_bar_vertical", "E9F9": "chart_multiple",
    "EA18": "certificate",
}

UNICODE_ICONS = {
    "2013": "subtract", "2610": "square", "2750": "square_multiple",
    "2715": "dismiss", "2699": "settings", "1F552": "clock", "23F1": "timer",
    "1F554": "clock", "1F4C4": "document", "1F4C8": "data_bar_vertical",
    "23FB": "power", "2295": "add_circle", "1F4C5": "calendar",
    "26F6": "full_screen_maximize", "23F8": "pause", "25B6": "play",
    "2304": "chevron_down",
}


def source_file(name: str, directory: Path) -> Path:
    path = directory / name
    if not path.exists():
        with urlopen(f"{UPSTREAM_BASE}/fonts/{name}", timeout=30) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_HASHES[name]:
        raise ValueError(f"Pinned upstream checksum mismatch: {name}")
    return path


def build(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    font = TTFont(source_file("FluentSystemIcons-Regular.ttf", directory), recalcTimestamp=False)
    source_map = json.loads(source_file("FluentSystemIcons-Regular.json", directory).read_text())
    aliases = ICON_MAP | UNICODE_ICONS
    source_codes = {int(code, 16): source_map[f"ic_fluent_{name}_20_regular"]
                    for code, name in aliases.items()}
    glyph_map = {code: font.getBestCmap()[upstream] for code, upstream in source_codes.items()}
    options = subset.Options()
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 10, 13, 14, 16, 17]
    options.recalc_timestamp = False
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=list(source_codes.values()))
    subsetter.subset(font)
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap = {code: name for code, name in glyph_map.items()
                          if table.format == 12 or code <= 0xFFFF}
    names = {1: "CSPM Symbols", 2: "Regular", 3: "CSPM Symbols 1.0",
             4: "CSPM Symbols", 6: "CSPMSymbols", 16: "CSPM Symbols", 17: "Regular"}
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID].encode(record.getEncoding())
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    output = FONT_DIR / "CSPMSymbols.ttf"
    font.save(output)
    metadata = {
        "family": "CSPM Symbols", "upstream_commit": UPSTREAM_COMMIT,
        "upstream": "https://github.com/microsoft/fluentui-system-icons",
        "license": "MIT", "source_sha256": SOURCE_HASHES,
        "font_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "icons": {code: f"ic_fluent_{name}_20_regular" for code, name in ICON_MAP.items()},
        "unicode_icons": {code: f"ic_fluent_{name}_20_regular" for code, name in UNICODE_ICONS.items()},
    }
    (FONT_DIR / "CSPMSymbols.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="Cache for the two pinned upstream files")
    print(build(parser.parse_args().source_dir))
