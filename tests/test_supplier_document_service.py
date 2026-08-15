from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    # Append rather than prepend: this avoids shadowing Python's stdlib
    # ``platform`` module with CSPM's own compatibility package.
    sys.path.append(str(SOURCE_ROOT))

from services.supplier_document_service import SupplierDocumentError, SupplierDocumentService


def test_attached_supplier_document_is_portable_and_hash_verified(tmp_path: Path) -> None:
    source = tmp_path / "supplier.pdf"
    source.write_bytes(b"supplier invoice evidence")
    shared_data = tmp_path / "CSPM_Shared_Data"
    service = SupplierDocumentService(shared_data, tmp_path / "local")

    saved = service.attach_invoice(
        source,
        vendor="Spencer Fane LLP",
        invoice_number="1557960",
        invoice_date="2026-07-17",
    )

    assert saved["DocumentPath"].startswith("Supplier_Invoices/2026/Spencer Fane LLP/")
    resolved = service.resolve(saved["DocumentPath"])
    assert resolved.is_file()
    assert service.sha256(resolved) == saved["DocumentHash"]
    assert saved["DocumentOriginalName"] == "supplier.pdf"
    assert saved["DocumentOriginalPath"] == saved["DocumentPath"]
    assert saved["DocumentStorageFormat"] == "Original PDF"


def test_image_supplier_document_preserves_source_and_saves_verified_pdf(tmp_path: Path) -> None:
    source = tmp_path / "supplier.png"
    Image.new("RGBA", (20, 10), (38, 112, 168, 120)).save(source)
    service = SupplierDocumentService(tmp_path / "CSPM_Shared_Data", tmp_path / "local")

    saved = service.attach_invoice(
        source,
        vendor="Spencer Fane LLP",
        invoice_number="1557960",
        invoice_date="2026-07-17",
    )

    rendered_pdf = service.resolve(saved["DocumentPath"])
    original = service.resolve(saved["DocumentOriginalPath"])
    assert rendered_pdf.suffix.lower() == ".pdf"
    assert rendered_pdf.read_bytes().startswith(b"%PDF")
    assert original.suffix.lower() == ".png"
    assert original.name.endswith(".source.png")
    assert service.sha256(original) == saved["DocumentOriginalHash"]
    assert saved["DocumentStorageFormat"] == "PDF converted from PNG"


def test_word_or_excel_document_uses_hidden_converter_and_preserves_source(tmp_path: Path) -> None:
    source = tmp_path / "supplier.docx"
    source.write_bytes(b"example Office document")
    calls: list[tuple[Path, Path]] = []

    def fake_converter(source_path: Path, pdf_path: Path) -> None:
        calls.append((source_path, pdf_path))
        pdf_path.write_bytes(b"%PDF-1.4\nconverted evidence")

    service = SupplierDocumentService(
        tmp_path / "CSPM_Shared_Data",
        tmp_path / "local",
        office_pdf_converter=fake_converter,
    )
    saved = service.attach_invoice(
        source,
        vendor="Spencer Fane LLP",
        invoice_number="1557960",
        invoice_date="2026-07-17",
    )

    assert len(calls) == 1
    assert calls[0][0] == source
    assert calls[0][1].name == "invoice.pdf"
    assert service.resolve(saved["DocumentPath"]).read_bytes().startswith(b"%PDF")
    assert service.resolve(saved["DocumentOriginalPath"]).name.endswith(".source.docx")
    assert saved["DocumentStorageFormat"] == "PDF converted from DOCX"


def test_supplier_document_rejects_unsupported_types(tmp_path: Path) -> None:
    source = tmp_path / "supplier.txt"
    source.write_text("not an invoice", encoding="utf-8")
    service = SupplierDocumentService(tmp_path / "CSPM_Shared_Data", tmp_path / "local")

    with pytest.raises(SupplierDocumentError, match="Unsupported supplier document type"):
        service.attach_invoice(
            source,
            vendor="Spencer Fane LLP",
            invoice_number="1557960",
            invoice_date="2026-07-17",
        )
