"""Qt dialog URL roundtrips for Linux, Windows, UNC and literal filenames."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def paths_js():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QJSEngine

    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QJSEngine()
    source = (ROOT / "src/qml/standards/FilePaths.js").read_text().replace(".pragma library", "")
    result = engine.evaluate(source)
    assert not result.isError(), result.toString()
    yield app, engine


def call(paths_js, function, *arguments):
    _, engine = paths_js
    result = engine.evaluate(function + "(" + ",".join(json.dumps(value) for value in arguments) + ")")
    assert not result.isError(), result.toString()
    return result.toString()


@pytest.mark.parametrize("url,path", [
    ("file:///home/cory/Documents/Invoice%20%231.pdf", "/home/cory/Documents/Invoice #1.pdf"),
    ("file:///home/cory/OneDrive/Legal%20%26%20Tax/%C3%A9tude.pdf", "/home/cory/OneDrive/Legal & Tax/étude.pdf"),
    ("file:///C:/Users/Cory/Documents/Invoice%20%231.pdf", "C:/Users/Cory/Documents/Invoice #1.pdf"),
    ("file://server/Practice%20Data/Invoice.pdf", "//server/Practice Data/Invoice.pdf"),
    ("file://localhost/home/cory/Invoice.pdf", "/home/cory/Invoice.pdf"),
    ("file:/home/cory/Invoice.pdf", "/home/cory/Invoice.pdf"),
    ("/home/cory/100% complete.pdf", "/home/cory/100% complete.pdf"),
])
def test_selected_dialog_urls_preserve_absolute_paths(paths_js, url, path):
    assert call(paths_js, "localPath", url) == path


@pytest.mark.parametrize("path", [
    "/home/cory/Documents/Invoice #1.pdf",
    "/home/cory/OneDrive/Café & Tax/100% complete.pdf",
    "C:/Users/Cory/Documents/Invoice #1.pdf",
    "//server/Practice Data/Invoice #1.pdf",
])
def test_open_urls_roundtrip_through_actual_qt_without_fragment_loss(paths_js, path):
    from PySide6.QtCore import QUrl

    url = call(paths_js, "fileUrl", path)
    assert QUrl(url).isLocalFile()
    assert QUrl(url).fragment() == ""
    assert call(paths_js, "localPath", url) == path
    actual = QUrl(url).toLocalFile()
    assert actual == ("/" + path if path[1:3] == ":/" and os.name != "nt" else path)


def test_save_dialog_suggests_name_inside_its_current_folder(paths_js):
    suggested = call(paths_js, "suggestedFile", "file:///home/cory/Documents/", "Invoice #1%.pdf")
    assert suggested == "file:///home/cory/Documents/Invoice%20%231%25.pdf"
    assert call(paths_js, "localPath", suggested) == "/home/cory/Documents/Invoice #1%.pdf"
