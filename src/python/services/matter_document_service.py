from __future__ import annotations

"""Portable, verified storage for matter engagement documents.

Matter records store a path relative to the configured CSPM shared-data
folder.  The document therefore follows the governed workbook package across
computers without depending on a machine-specific OneDrive root.
"""

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


class MatterDocumentError(ValueError):
    pass


class MatterDocumentService:
    FOLDER_NAME = "Matter_Documents"
    _SAFE_PART = re.compile(r"[^A-Za-z0-9._ -]+")
    _SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".doc",
        ".docx",
        ".rtf",
        ".txt",
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
    }

    def __init__(self, shared_data_dir: Path | str | None, local_data_dir: Path | str):
        shared = Path(shared_data_dir) if shared_data_dir else None
        self.base = shared if shared else Path(local_data_dir)
        self.root = self.base / self.FOLDER_NAME

    @staticmethod
    def _source_path(value: Any) -> Path:
        text = str(value or "").strip()
        if not text:
            raise MatterDocumentError("Choose the retainer or engagement agreement to attach.")
        if text.lower().startswith("file:"):
            parsed = urlparse(text)
            text = unquote(parsed.path or "")
            if parsed.netloc and parsed.netloc.lower() != "localhost":
                text = "//" + parsed.netloc + text
            if text.startswith("/") and len(text) >= 3 and text[2] == ":":
                text = text[1:]
        elif "://" in text:
            raise MatterDocumentError(
                "Choose a local or OneDrive-synced agreement file, rather than a web link."
            )
        return Path(text)

    @classmethod
    def _safe_part(cls, value: Any, fallback: str) -> str:
        text = cls._SAFE_PART.sub("-", str(value or "").strip())
        text = re.sub(r"\s+", " ", text).strip(" .-")
        return (text or fallback)[:64]

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
        if destination.exists():
            if self.sha256(destination) != checksum:
                raise MatterDocumentError(
                    "A matter document with the same governed name has different contents."
                )
            return

        handle, temporary_name = tempfile.mkstemp(
            prefix=".agreement-", suffix=".partial", dir=destination.parent
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            shutil.copy2(source, temporary)
            if self.sha256(temporary) != checksum:
                raise MatterDocumentError(
                    "The copied retainer agreement did not pass SHA-256 verification."
                )
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def attach_agreement(
        self,
        source: Any,
        *,
        matter_number: Any,
        matter_name: Any,
    ) -> dict[str, str]:
        source_path = self._source_path(source)
        if not source_path.is_file():
            raise MatterDocumentError(f"Retainer agreement was not found: {source_path}")
        if source_path.stat().st_size <= 0:
            raise MatterDocumentError("The selected retainer agreement is empty.")

        extension = source_path.suffix.lower()
        if extension not in self._SUPPORTED_EXTENSIONS:
            supported = ", ".join(
                sorted(item.lstrip(".").upper() for item in self._SUPPORTED_EXTENSIONS)
            )
            raise MatterDocumentError(
                f"Unsupported retainer document type. Choose one of: {supported}."
            )

        checksum = self.sha256(source_path)
        matter_part = self._safe_part(
            matter_number or matter_name,
            "Unnumbered Matter",
        )
        name_part = self._safe_part(source_path.stem, "Retainer Agreement")
        destination_dir = self.ensure_root() / matter_part
        destination_dir.mkdir(parents=True, exist_ok=True)
        if not destination_dir.resolve().is_relative_to(self.root.resolve()):
            raise MatterDocumentError("The matter document folder escapes the configured storage root.")
        destination = destination_dir / f"{name_part}--{checksum[:12]}{extension}"
        self._copy_verified(source_path, destination, checksum)

        return {
            "DocumentPath": destination.relative_to(self.base).as_posix(),
            "DocumentHash": checksum,
            "DocumentOriginalName": source_path.name,
            "DocumentAbsolutePath": str(destination),
        }

    def resolve(self, saved_path: Any) -> Path:
        candidate = self._source_path(saved_path)
        # Preserve compatibility with historic records that contain an
        # absolute path. New attachments are always portable relative paths.
        if candidate.is_absolute():
            return candidate
        if candidate.drive or candidate.root or ".." in candidate.parts:
            raise MatterDocumentError("The saved matter document path is not valid.")
        resolved = (self.base / candidate).resolve()
        root = self.root.resolve()
        if root not in resolved.parents and resolved != root:
            raise MatterDocumentError(
                "The saved matter document path escapes the governed document folder."
            )
        return resolved
