from __future__ import annotations

"""Portable, tamper-evident storage for supplier invoice evidence.

The workbook only stores a path relative to the shared data folder.  That is
important: each PC can have a different OneDrive root yet resolve the same
invoice evidence after a normal CSPM cloud checkout.
"""

import hashlib
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse


class SupplierDocumentError(ValueError):
    pass


class SupplierDocumentService:
    FOLDER_NAME = "Supplier_Invoices"
    _SAFE_PART = re.compile(r"[^A-Za-z0-9._ -]+")
    _IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    _OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx"}
    _SUPPORTED_EXTENSIONS = {".pdf"} | _IMAGE_EXTENSIONS | _OFFICE_EXTENSIONS

    def __init__(
        self,
        shared_data_dir: Path | str | None,
        local_data_dir: Path | str,
        *,
        office_pdf_converter: Callable[[Path, Path], None] | None = None,
    ):
        shared = Path(shared_data_dir) if shared_data_dir else None
        self.shared_data_dir = shared
        # Stand-alone/offline CSPM remains usable, but when shared data is
        # configured, source evidence is always placed beside the governed
        # workbook in that shared OneDrive package.
        base = shared if shared else Path(local_data_dir)
        self.root = base / self.FOLDER_NAME
        # Injectable only for deterministic tests. Production uses hidden
        # Microsoft Office automation for Word and Excel documents.
        self._office_pdf_converter = office_pdf_converter

    @staticmethod
    def _source_path(value: Any) -> Path:
        text = str(value or "").strip()
        if not text:
            raise SupplierDocumentError("Choose the supplier invoice file to attach.")
        if text.lower().startswith("file:"):
            parsed = urlparse(text)
            text = unquote(parsed.path or "")
            if text.startswith("/") and len(text) >= 3 and text[2] == ":":
                text = text[1:]
        return Path(text)

    @classmethod
    def _safe_part(cls, value: Any, fallback: str) -> str:
        text = cls._SAFE_PART.sub("-", str(value or "").strip())
        text = re.sub(r"\s+", " ", text).strip(" .-")
        return (text or fallback)[:72]

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def ensure_root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def _copy_verified(self, source: Path, destination: Path, checksum: str) -> None:
        """Copy one evidence file atomically and verify its immutable hash."""
        if destination.exists():
            if self.sha256(destination) != checksum:
                raise SupplierDocumentError(
                    "A supplier document with the same governed name has different contents. "
                    "Choose a distinct invoice number before attaching it."
                )
            return
        temporary = destination.with_suffix(destination.suffix + ".partial")
        try:
            shutil.copy2(source, temporary)
            if self.sha256(temporary) != checksum:
                raise SupplierDocumentError("The copied supplier invoice did not pass SHA-256 verification.")
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _image_to_pdf(source: Path, destination: Path) -> None:
        try:
            from PIL import Image, ImageOps, ImageSequence
            frames = []
            with Image.open(source) as image:
                for raw_frame in ImageSequence.Iterator(image):
                    frame = ImageOps.exif_transpose(raw_frame.copy())
                    if frame.mode == "RGBA":
                        flattened = Image.new("RGB", frame.size, "white")
                        flattened.paste(frame, mask=frame.getchannel("A"))
                        frame = flattened
                    elif frame.mode != "RGB":
                        frame = frame.convert("RGB")
                    frames.append(frame)
            if not frames:
                raise SupplierDocumentError("The selected image contains no pages to convert.")
            first, rest = frames[0], frames[1:]
            first.save(destination, "PDF", resolution=150.0, save_all=True, append_images=rest)
        except SupplierDocumentError:
            raise
        except Exception as exc:
            raise SupplierDocumentError(f"CSPM could not convert the selected image to PDF: {exc}") from exc

    def _office_to_pdf(self, source: Path, destination: Path) -> None:
        if self._office_pdf_converter is not None:
            self._office_pdf_converter(source, destination)
            return
        try:
            import pythoncom
            import win32com.client
        except Exception as exc:
            raise SupplierDocumentError(
                "Microsoft Office automation is required to convert Word and Excel invoice documents to PDF."
            ) from exc

        application = None
        opened_document = None
        pythoncom.CoInitialize()
        try:
            extension = source.suffix.lower()
            if extension in {".doc", ".docx"}:
                application = win32com.client.DispatchEx("Word.Application")
                application.Visible = False
                application.DisplayAlerts = 0
                try:
                    application.AutomationSecurity = 3  # Disable macros.
                except Exception:
                    pass
                opened_document = application.Documents.Open(
                    str(source), ReadOnly=True, AddToRecentFiles=False, Visible=False,
                )
                opened_document.ExportAsFixedFormat(str(destination), 17, False)
            else:
                application = win32com.client.DispatchEx("Excel.Application")
                application.Visible = False
                application.DisplayAlerts = False
                try:
                    application.AutomationSecurity = 3  # Disable macros.
                except Exception:
                    pass
                opened_document = application.Workbooks.Open(
                    str(source), UpdateLinks=0, ReadOnly=True,
                    IgnoreReadOnlyRecommended=True, AddToMru=False,
                )
                opened_document.ExportAsFixedFormat(0, str(destination), 0, True, False)
        except SupplierDocumentError:
            raise
        except Exception as exc:
            raise SupplierDocumentError(
                f"CSPM could not convert {source.name} to PDF through Microsoft Office: {exc}"
            ) from exc
        finally:
            if opened_document is not None:
                try:
                    opened_document.Close(False)
                except Exception:
                    pass
            if application is not None:
                try:
                    application.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

        if not destination.is_file() or destination.stat().st_size <= 0:
            raise SupplierDocumentError("Microsoft Office did not produce a PDF for the selected supplier document.")

    def _convert_to_pdf(self, source: Path, destination: Path) -> None:
        extension = source.suffix.lower()
        if extension in self._IMAGE_EXTENSIONS:
            self._image_to_pdf(source, destination)
            return
        if extension in self._OFFICE_EXTENSIONS:
            self._office_to_pdf(source, destination)
            return
        raise SupplierDocumentError(f"CSPM cannot convert {extension or 'this file type'} to PDF.")

    def attach_invoice(
        self,
        source: Any,
        *,
        vendor: Any,
        invoice_number: Any,
        invoice_date: Any,
    ) -> dict[str, str]:
        source_path = self._source_path(source)
        if not source_path.is_file():
            raise SupplierDocumentError(f"Supplier invoice file was not found: {source_path}")
        if source_path.stat().st_size <= 0:
            raise SupplierDocumentError("The selected supplier invoice file is empty.")

        extension = source_path.suffix.lower()
        if extension not in self._SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(item.lstrip(".").upper() for item in self._SUPPORTED_EXTENSIONS))
            raise SupplierDocumentError(f"Unsupported supplier document type. Choose one of: {supported}.")

        original_checksum = self.sha256(source_path)
        year = str(invoice_date or "")[:4]
        if not year.isdigit():
            year = datetime.now(timezone.utc).strftime("%Y")
        vendor_part = self._safe_part(vendor, "Unknown vendor")
        invoice_part = self._safe_part(invoice_number, "Unnumbered invoice")
        destination_dir = self.ensure_root() / year / vendor_part
        destination_dir.mkdir(parents=True, exist_ok=True)
        if extension == ".pdf":
            destination = destination_dir / f"{invoice_part}--{original_checksum[:12]}.pdf"
            self._copy_verified(source_path, destination, original_checksum)
            original_destination = destination
            document_checksum = original_checksum
            storage_format = "Original PDF"
        else:
            # Preserve the original source alongside its derived PDF.  The PDF
            # is the primary, cross-device evidence document; the source keeps
            # the original native file available for audit or re-conversion.
            original_destination = destination_dir / (
                f"{invoice_part}--{original_checksum[:12]}.source{extension}"
            )
            self._copy_verified(source_path, original_destination, original_checksum)
            with tempfile.TemporaryDirectory(prefix="cspm-supplier-invoice-") as temporary_dir:
                converted = Path(temporary_dir) / "invoice.pdf"
                self._convert_to_pdf(source_path, converted)
                document_checksum = self.sha256(converted)
                destination = destination_dir / f"{invoice_part}--{document_checksum[:12]}.pdf"
                self._copy_verified(converted, destination, document_checksum)
            storage_format = f"PDF converted from {extension.lstrip('.').upper()}"

        return {
            "DocumentPath": destination.relative_to(self.root.parent).as_posix(),
            "DocumentHash": document_checksum,
            "DocumentOriginalName": source_path.name,
            "DocumentOriginalPath": original_destination.relative_to(self.root.parent).as_posix(),
            "DocumentOriginalHash": original_checksum,
            "DocumentStorageFormat": storage_format,
            "DocumentAbsolutePath": str(destination),
        }

    def resolve(self, relative_path: Any) -> Path:
        candidate = Path(str(relative_path or "").replace("/", os.sep))
        if not str(candidate) or candidate.is_absolute() or ".." in candidate.parts:
            raise SupplierDocumentError("The saved supplier document path is not valid.")
        resolved = (self.root.parent / candidate).resolve()
        root = self.root.resolve()
        if root not in resolved.parents and resolved != root:
            raise SupplierDocumentError("The saved supplier document path escapes the shared invoice folder.")
        return resolved
