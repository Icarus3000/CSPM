from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src" / "python"))

from services.matter_document_service import (
    MatterDocumentError,
    MatterDocumentService,
)


def test_retainer_agreement_is_copied_to_shared_governed_folder(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    local = tmp_path / "local"
    source = tmp_path / "Signed Retainer.pdf"
    source.write_bytes(b"%PDF-1.7\nretainer")
    service = MatterDocumentService(shared, local)

    saved = service.attach_agreement(
        source.as_uri(),
        matter_number="M-2026-0042",
        matter_name="Example Matter",
    )

    assert saved["DocumentPath"].startswith(
        "Matter_Documents/M-2026-0042/Signed Retainer--"
    )
    destination = service.resolve(saved["DocumentPath"])
    assert destination.read_bytes() == source.read_bytes()
    assert destination.is_relative_to(shared / "Matter_Documents")
    assert saved["DocumentHash"] == service.sha256(destination)


def test_repeated_attachment_is_idempotent_and_uses_local_fallback(tmp_path: Path) -> None:
    local = tmp_path / "local"
    source = tmp_path / "agreement.docx"
    source.write_bytes(b"test docx payload")
    service = MatterDocumentService(None, local)

    first = service.attach_agreement(
        source,
        matter_number="",
        matter_name="Ordinary Retainer",
    )
    second = service.attach_agreement(
        source,
        matter_number="",
        matter_name="Ordinary Retainer",
    )

    assert first == second
    assert service.resolve(first["DocumentPath"]).is_relative_to(
        local / "Matter_Documents"
    )


def test_unsupported_or_missing_agreement_is_rejected(tmp_path: Path) -> None:
    service = MatterDocumentService(tmp_path / "shared", tmp_path / "local")
    unsupported = tmp_path / "agreement.exe"
    unsupported.write_bytes(b"not a document")

    with pytest.raises(MatterDocumentError, match="Unsupported retainer document type"):
        service.attach_agreement(
            unsupported,
            matter_number="M-1",
            matter_name="Matter",
        )

    with pytest.raises(MatterDocumentError, match="was not found"):
        service.attach_agreement(
            tmp_path / "missing.pdf",
            matter_number="M-1",
            matter_name="Matter",
        )


def test_historic_absolute_document_path_remains_openable(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy-retainer.pdf"
    legacy.write_bytes(b"legacy")
    service = MatterDocumentService(tmp_path / "shared", tmp_path / "local")

    assert service.resolve(str(legacy)) == legacy


def test_different_revisions_are_preserved_and_corrupt_copy_is_not_overwritten(tmp_path: Path) -> None:
    service = MatterDocumentService(None, tmp_path / "storage")
    source = tmp_path / "retainer.pdf"
    source.write_bytes(b"signed first revision")
    first = service.attach_agreement(source, matter_number="M-1", matter_name="Matter")
    source.write_bytes(b"signed second revision")
    second = service.attach_agreement(source, matter_number="M-1", matter_name="Matter")
    assert first["DocumentPath"] != second["DocumentPath"]
    assert service.resolve(first["DocumentPath"]).read_bytes() == b"signed first revision"
    assert service.resolve(second["DocumentPath"]).read_bytes() == b"signed second revision"

    service.resolve(second["DocumentPath"]).write_bytes(b"unexpected content")
    with pytest.raises(MatterDocumentError, match="different contents"):
        service.attach_agreement(source, matter_number="M-1", matter_name="Matter")
    assert source.read_bytes() == b"signed second revision"


@pytest.mark.parametrize("path", ["../outside.pdf", "Other_Folder/agreement.pdf", "https://example.test/retainer.pdf", ""])
def test_document_resolution_rejects_invalid_paths(tmp_path: Path, path: str) -> None:
    service = MatterDocumentService(None, tmp_path)
    with pytest.raises(MatterDocumentError):
        service.resolve(path)

