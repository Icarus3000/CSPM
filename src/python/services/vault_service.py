"""Portable Compliance Vault service for CSPM (`Vault/Matters/...` & `Vault/Clients/...`).

Provides workstation-agnostic path resolution across:
1. `<masterDataDir>/Vault` (`%OneDrive%/CSPM_Shared_Data/Vault`) and `<data_dir>/Vault` (`%LOCALAPPDATA%/CSPM/data/Vault`);
2. Matter Retainer (`Vault/Matters/<matter_number>/Retainer/<filename>`) and Client KYC (`Vault/Clients/<client_id>/KYC/<filename>`) folders;
3. `%OneDrive%` / `%OneDriveCommercial%` working folders (including `Clients (CS)/.../01 - Retainer & Engagement/<filename>`).
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from services.paths import AppPaths

MEGATECH_REORG_MATTER_NUMBERS = ("MEGA-COR-26-0093", "MEGA-CRP-26-0209")
MEGATECH_REORG_DEFAULT_RETAINER_FILENAME = (
    "2026-10-16 Joint Retainer Agreement - Reorganization - Signed.pdf"
)
MEGATECH_REORG_ONEDRIVE_SUBPATHS = (
    Path("Clients (CS)")
    / "Megatech"
    / "2026 - Corporate Reorganization"
    / "01 - Retainer & Engagement"
    / MEGATECH_REORG_DEFAULT_RETAINER_FILENAME,
    Path("Clients (CS)")
    / "Megatech"
    / "01 - Client Intake, Retainer & KYC"
    / MEGATECH_REORG_DEFAULT_RETAINER_FILENAME,
)


class VaultService:
    """Manages portable document ingestion and resolution for CSPM Vault."""

    _SAFE_SEGMENT_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

    def __init__(
        self,
        paths: AppPaths | None = None,
        *,
        shared_vault_dir: Path | str | None = None,
        local_vault_dir: Path | str | None = None,
        onedrive_roots: Iterable[Path | str] | None = None,
    ) -> None:
        self._paths = paths or AppPaths(root=AppPaths.project_root())
        self._explicit_shared_vault = Path(shared_vault_dir) if shared_vault_dir else None
        self._explicit_local_vault = Path(local_vault_dir) if local_vault_dir else None
        self._explicit_onedrive_roots = (
            [Path(p) for p in onedrive_roots] if onedrive_roots is not None else None
        )

    def shared_vault_dir(self) -> Path:
        if self._explicit_shared_vault is not None:
            return self._explicit_shared_vault
        return self._paths.shared_vault_dir()

    def local_vault_dir(self) -> Path:
        if self._explicit_local_vault is not None:
            return self._explicit_local_vault
        return self._paths.local_vault_dir()

    def _vault_roots(self) -> list[Path]:
        """Return ordered candidate Vault roots (shared first, then local)."""
        candidates: list[Path] = [self.shared_vault_dir(), self.local_vault_dir()]
        has_override = bool(
            self._explicit_local_vault is not None
            or self._explicit_shared_vault is not None
            or self._paths.override_data_dir is not None
            or self._paths.override_master_dir is not None
        )
        if not has_override:
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                candidates.append(Path(local_app_data) / "CSPM" / "data" / "Vault")
            for od_root in self.discover_onedrive_roots():
                candidates.append(od_root / "CSPM_Shared_Data" / "Vault")

        unique: list[Path] = []
        seen: set[str] = set()
        for root in candidates:
            norm = str(root).replace("\\", "/").rstrip("/").casefold()
            if norm and norm not in seen:
                seen.add(norm)
                unique.append(root)
        return unique

    def discover_onedrive_roots(self) -> list[Path]:
        """Discover OneDrive roots on the active workstation using env vars and home globs."""
        if self._explicit_onedrive_roots is not None:
            return [p for p in self._explicit_onedrive_roots if p.exists()]

        candidates: list[Path] = []
        shared_vault = self.shared_vault_dir()
        if shared_vault.parent.name.lower() == "cspm_shared_data" and shared_vault.parent.parent.exists():
            candidates.append(shared_vault.parent.parent)

        for env_key in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer"):
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                expanded = Path(os.path.expandvars(env_val)).expanduser()
                if expanded.exists():
                    candidates.append(expanded)

        has_override = bool(
            self._explicit_local_vault is not None
            or self._explicit_shared_vault is not None
            or self._paths.override_data_dir is not None
            or self._paths.override_master_dir is not None
        )
        if not has_override:
            try:
                for match in sorted(Path.home().glob("OneDrive*")):
                    if match.is_dir():
                        candidates.append(match)
            except OSError:
                pass

        unique: list[Path] = []
        seen: set[str] = set()
        for root in candidates:
            try:
                norm = str(root.resolve()).casefold()
            except OSError:
                norm = str(root).casefold()
            if norm not in seen and root.exists():
                seen.add(norm)
                unique.append(root)
        return unique

    @classmethod
    def _clean_segment(cls, value: str, fallback: str) -> str:
        cleaned = cls._SAFE_SEGMENT_RE.sub("-", str(value or "").strip()).strip(" .")
        return cleaned or fallback

    @classmethod
    def _normalize_scope_type(cls, scope_type: str) -> str:
        raw = str(scope_type or "").strip().lower()
        if raw in ("matter", "matters"):
            return "Matters"
        if raw in ("client", "clients"):
            return "Clients"
        return cls._clean_segment(scope_type, "Matters")

    @staticmethod
    def _normalize_input_path(raw_value: str | Path) -> str:
        text = str(raw_value or "").strip()
        if not text:
            return ""
        if text.lower().startswith("file:"):
            parsed = urlparse(text)
            text = unquote(parsed.path or "")
            if parsed.netloc and parsed.netloc.lower() != "localhost":
                text = "//" + parsed.netloc + text
            if text.startswith("/") and len(text) >= 3 and text[2] == ":":
                text = text[1:]
        return os.path.expandvars(text).strip()

    @staticmethod
    def _strip_vault_prefix(rel_text: str) -> str | None:
        norm = rel_text.replace("\\", "/").lstrip("./")
        if norm.lower().startswith("vault/"):
            return norm[6:].lstrip("/")
        parts = [p for p in norm.split("/") if p]
        for idx, part in enumerate(parts):
            if part.lower() == "vault" and idx + 1 < len(parts):
                return "/".join(parts[idx + 1 :])
        return None

    @staticmethod
    def _matter_number_variants(matter_number: str) -> list[str]:
        clean = str(matter_number or "").strip()
        if not clean:
            return []
        variants = [clean]
        if clean.upper() in MEGATECH_REORG_MATTER_NUMBERS:
            for alt in MEGATECH_REORG_MATTER_NUMBERS:
                if alt not in variants:
                    variants.append(alt)
        return variants

    def resolve_document_path(
        self,
        doc_ref: str,
        matter_number: str = "",
        client_id: str = "",
    ) -> Path | None:
        """Resolve a stored document reference across shared/local Vaults and OneDrive working folders."""
        cleaned_ref = self._normalize_input_path(doc_ref)
        vault_roots = self._vault_roots()
        matter_variants = self._matter_number_variants(matter_number)
        clean_client = str(client_id or "").strip()

        # If doc_ref mentions a matter number under Vault/Matters/<num>/..., include it in matter_variants
        if cleaned_ref:
            norm_slash = cleaned_ref.replace("\\", "/")
            m_match = re.search(r"(?:^|/)Matters/([^/]+)/", norm_slash, flags=re.IGNORECASE)
            if m_match:
                extracted_matter = m_match.group(1).strip()
                for v in self._matter_number_variants(extracted_matter):
                    if v not in matter_variants:
                        matter_variants.append(v)
            c_match = re.search(r"(?:^|/)Clients/([^/]+)/", norm_slash, flags=re.IGNORECASE)
            if c_match and not clean_client:
                clean_client = c_match.group(1).strip()

        # 0. Direct absolute path check (if already valid on this workstation)
        if cleaned_ref:
            direct_path = Path(cleaned_ref).expanduser()
            if direct_path.is_absolute() and direct_path.is_file():
                return direct_path.resolve()

        # 1. Check shared_vault_dir() and local_vault_dir() for Vault/... relative paths
        if cleaned_ref:
            vault_subpath = self._strip_vault_prefix(cleaned_ref)
            if vault_subpath:
                for v_root in vault_roots:
                    candidate = v_root / Path(vault_subpath)
                    if candidate.is_file():
                        return candidate.resolve()

            # Also check Matter_Documents/... relative to Vault parent data directories
            norm_rel = cleaned_ref.replace("\\", "/").lstrip("./")
            if norm_rel.lower().startswith("matter_documents/"):
                for v_root in vault_roots:
                    data_parent = v_root.parent
                    candidate = data_parent / Path(norm_rel)
                    if candidate.is_file():
                        return candidate.resolve()

        # Determine target filename(s) to look for in step 2 & step 3
        filenames: list[str] = []
        if cleaned_ref:
            fname = Path(cleaned_ref.replace("\\", "/")).name.strip()
            if fname:
                filenames.append(fname)
                # Strip governed --<12hex> hash suffix if present
                stripped_hash = re.sub(r"--[0-9a-fA-F]{8,64}(\.[A-Za-z0-9]+)$", r"\1", fname)
                if stripped_hash != fname and stripped_hash not in filenames:
                    filenames.append(stripped_hash)

        is_megatech_reorg = (
            any(m.upper().startswith("MEGA-") for m in matter_variants)
            or clean_client.upper() == "MEGA"
            or any("reorganization" in f.lower() for f in filenames)
        )
        if is_megatech_reorg and MEGATECH_REORG_DEFAULT_RETAINER_FILENAME not in filenames:
            filenames.append(MEGATECH_REORG_DEFAULT_RETAINER_FILENAME)

        # 2. Check Vault/Matters/<matter_number>/Retainer/<filename> and Vault/Clients/<client_id>/KYC/<filename>
        for v_root in vault_roots:
            for m_num in matter_variants:
                retainer_dir = v_root / "Matters" / m_num / "Retainer"
                matter_dir = v_root / "Matters" / m_num
                for fname in filenames:
                    for candidate in (retainer_dir / fname, matter_dir / fname):
                        if candidate.is_file():
                            return candidate.resolve()
                # If no specific filename matched (or doc_ref was empty), check any PDF/doc in Retainer/
                if retainer_dir.is_dir():
                    for child in sorted(retainer_dir.iterdir()):
                        if child.is_file() and child.suffix.lower() in (".pdf", ".docx", ".doc"):
                            return child.resolve()

                # Also check sibling Matter_Documents/<m_num>/
                legacy_dir = v_root.parent / "Matter_Documents" / m_num
                if legacy_dir.is_dir():
                    for child in sorted(legacy_dir.iterdir()):
                        if child.is_file() and child.suffix.lower() in (".pdf", ".docx", ".doc"):
                            if not filenames or any(
                                child.name.lower() == fn.lower()
                                or child.name.lower().startswith(Path(fn).stem.lower())
                                for fn in filenames
                            ):
                                return child.resolve()

            if clean_client:
                kyc_dir = v_root / "Clients" / clean_client / "KYC"
                client_dir = v_root / "Clients" / clean_client
                for fname in filenames:
                    for candidate in (kyc_dir / fname, client_dir / fname):
                        if candidate.is_file():
                            return candidate.resolve()

        # 3. Check %OneDrive% / %OneDriveCommercial% relative paths (including Clients (CS)\...\01 - Retainer & Engagement\<filename>)
        od_roots = self.discover_onedrive_roots()
        if cleaned_ref:
            # Rebase absolute OneDrive path from another workstation if applicable
            norm_parts = Path(cleaned_ref.replace("\\", "/")).parts
            rel_candidates: list[Path] = []
            for idx, part in enumerate(norm_parts):
                if part.lower().startswith("onedrive") and idx + 1 < len(norm_parts):
                    rel_candidates.append(Path(*norm_parts[idx + 1 :]))
                elif part.lower() == "clients (cs)":
                    rel_candidates.append(Path(*norm_parts[idx:]))
            if not Path(cleaned_ref).is_absolute():
                rel_candidates.insert(0, Path(cleaned_ref.replace("\\", "/").lstrip("/")))

            for od_root in od_roots:
                for rel_cand in rel_candidates:
                    candidate = od_root / rel_cand
                    if candidate.is_file():
                        return candidate.resolve()

        # Check Megatech reorganization fallback paths and Clients (CS) working folders in OneDrive
        for od_root in od_roots:
            if is_megatech_reorg:
                for fname in filenames:
                    for subpath in (
                        Path("Clients (CS)")
                        / "Megatech"
                        / "2026 - Corporate Reorganization"
                        / "01 - Retainer & Engagement"
                        / fname,
                        Path("Clients (CS)")
                        / "Megatech"
                        / "01 - Client Intake, Retainer & KYC"
                        / fname,
                    ):
                        candidate = od_root / subpath
                        if candidate.is_file():
                            return candidate.resolve()
                for default_subpath in MEGATECH_REORG_ONEDRIVE_SUBPATHS:
                    candidate = od_root / default_subpath
                    if candidate.is_file():
                        return candidate.resolve()

            clients_cs = od_root / "Clients (CS)"
            if clients_cs.is_dir() and filenames:
                for fname in filenames:
                    for pattern in (
                        f"*/*/01 - Retainer & Engagement/{fname}",
                        f"*/01 - Retainer & Engagement/{fname}",
                        f"*/01 - Client Intake, Retainer & KYC/{fname}",
                        f"*/*/01 - Client Intake, Retainer & KYC/{fname}",
                    ):
                        for match in sorted(clients_cs.glob(pattern)):
                            if match.is_file():
                                return match.resolve()

        return None

    def ingest_document(
        self,
        scope_type: str,
        scope_id: str,
        category: str,
        source_path: Path | str,
    ) -> str:
        """Copy source_path into shared and local Vaults and return canonical 'Vault/...' relative path."""
        norm_scope = self._normalize_scope_type(scope_type)
        clean_id = self._clean_segment(scope_id, "Unassigned")
        default_cat = "Retainer" if norm_scope == "Matters" else "KYC"
        clean_cat = self._clean_segment(category, default_cat)

        cleaned_src = self._normalize_input_path(source_path)
        src = Path(cleaned_src).expanduser() if cleaned_src else Path()
        if not src.is_file():
            resolved = self.resolve_document_path(
                str(source_path),
                matter_number=clean_id if norm_scope == "Matters" else "",
                client_id=clean_id if norm_scope == "Clients" else "",
            )
            if resolved is not None and resolved.is_file():
                src = resolved
        if not src.is_file():
            raise FileNotFoundError(f"Source file for Vault ingestion not found: {source_path}")

        filename = src.name
        rel_subpath = Path(norm_scope) / clean_id / clean_cat / filename
        canonical_rel = f"Vault/{rel_subpath.as_posix()}"

        local_target = self.local_vault_dir() / rel_subpath
        local_target.parent.mkdir(parents=True, exist_ok=True)
        if not local_target.exists() or src.resolve() != local_target.resolve():
            shutil.copy2(src, local_target)

        shared_root = self.shared_vault_dir()
        try:
            shared_target = shared_root / rel_subpath
            if shared_target.resolve() != local_target.resolve():
                shared_target.parent.mkdir(parents=True, exist_ok=True)
                if not shared_target.exists() or src.resolve() != shared_target.resolve():
                    shutil.copy2(src, shared_target)
        except OSError:
            # Shared OneDrive Vault may be offline or unmounted; local Vault copy succeeded.
            pass

        return canonical_rel

    def get_matter_vault_folder(self, matter_number: str) -> Path:
        """Ensure and return Vault/Matters/<matter_number> (preferring shared Vault when reachable)."""
        clean_matter = self._clean_segment(matter_number, "Unnumbered_Matter")
        rel = Path("Matters") / clean_matter

        local_folder = self.local_vault_dir() / rel
        local_folder.mkdir(parents=True, exist_ok=True)
        (local_folder / "Retainer").mkdir(parents=True, exist_ok=True)

        shared_root = self.shared_vault_dir()
        try:
            shared_folder = shared_root / rel
            shared_folder.mkdir(parents=True, exist_ok=True)
            (shared_folder / "Retainer").mkdir(parents=True, exist_ok=True)
            return shared_folder
        except OSError:
            return local_folder

    def get_client_kyc_folder(self, client_id: str) -> Path:
        """Ensure and return Vault/Clients/<client_id>/KYC (preferring shared Vault when reachable)."""
        clean_client = self._clean_segment(client_id, "Unassigned_Client")
        rel = Path("Clients") / clean_client / "KYC"

        local_folder = self.local_vault_dir() / rel
        local_folder.mkdir(parents=True, exist_ok=True)

        shared_root = self.shared_vault_dir()
        try:
            shared_folder = shared_root / rel
            shared_folder.mkdir(parents=True, exist_ok=True)
            return shared_folder
        except OSError:
            return local_folder
