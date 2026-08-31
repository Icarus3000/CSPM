#!/usr/bin/env python3
"""
CSPM Phase 9 Candidate Approval Tool

Allows Cory to review and approve:
  1. CSPM.xlsm candidate template
  2. Dockets.xlsm candidate template
  3. DummyMacro.xlsm candidate VBA fixture

Usage:
  python scripts/template_governance/approve_phase9_candidates.py             # Interactive approval
  python scripts/template_governance/approve_phase9_candidates.py --review-only  # Review without approving
"""

import json
import hashlib
import sys
import os
import zipfile
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def zip_inventory_hash(path: Path) -> str:
    """Compute hash of ZIP member inventory (name:size pairs)."""
    with zipfile.ZipFile(path) as z:
        inv = "|".join(f"{n}:{z.getinfo(n).file_size}" for n in sorted(z.namelist()))
    return hashlib.sha256(inv.encode("utf-8")).hexdigest().lower()


def structural_summary(path: Path) -> dict:
    """Return structural summary of an .xlsm file."""
    import xml.etree.ElementTree as ET

    summary = {
        "exists": path.exists(),
        "size": 0,
        "sha256": "",
        "is_xlsm": False,
        "has_vba": False,
        "worksheets": [],
        "tables": [],
        "external_links": 0,
    }
    if not path.exists():
        return summary

    summary["size"] = path.stat().st_size
    summary["sha256"] = sha256_file(path)

    if not zipfile.is_zipfile(path):
        return summary

    summary["is_xlsm"] = True
    with zipfile.ZipFile(path) as z:
        nl = z.namelist()
        summary["has_vba"] = "xl/vbaProject.bin" in nl

        # Check content type
        ct = z.read("[Content_Types].xml").decode("utf-8")
        summary["macro_enabled"] = "macroEnabled" in ct

        # Worksheets
        ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        try:
            wb_xml = z.read("xl/workbook.xml")
            root = ET.fromstring(wb_xml)
            summary["worksheets"] = [
                s.get("name") for s in root.findall(".//ns:sheet", ns)
            ]
        except Exception:
            pass

        # Tables
        for n in nl:
            if n.startswith("xl/tables/") and n.endswith(".xml"):
                try:
                    txml = z.read(n)
                    troot = ET.fromstring(txml)
                    tname = troot.get("name", "unknown")
                    summary["tables"].append(tname)
                except Exception:
                    pass

        # External links
        summary["external_links"] = len(
            [n for n in nl if "externalLinks" in n and n.endswith(".xml")]
        )

    return summary


def confidentiality_check(path: Path, live_hashes: set) -> dict:
    """Run a confidentiality scan on a workbook."""
    result = {
        "matches_live": False,
        "external_links": 0,
        "has_comments": False,
        "safe": True,
        "details": [],
    }
    if not path.exists():
        result["safe"] = False
        result["details"].append("File does not exist")
        return result

    file_hash = sha256_file(path)
    if file_hash in live_hashes:
        result["matches_live"] = True
        result["safe"] = False
        result["details"].append("CRITICAL: Matches a live workbook hash!")
        return result

    with zipfile.ZipFile(path) as z:
        nl = z.namelist()
        result["external_links"] = len(
            [n for n in nl if "externalLinks" in n and n.endswith(".xml")]
        )
        if result["external_links"] > 0:
            result["safe"] = False
            result["details"].append(
                f"Contains {result['external_links']} external link(s)"
            )

    result["details"].append("No live-hash match")
    result["details"].append("No external links")
    return result


def validate_cspm_governance(path: Path) -> dict:
    """Verify the generated workbook, spec, manifest, and empty-row policy."""

    from generate_sanitized_templates import inspect_sanitized_workbook

    result = {"ok": False, "details": []}
    try:
        inspection = inspect_sanitized_workbook(path)
        spec_path = ROOT_DIR / "src" / "templates" / "CSPM.template-spec.json"
        manifest_path = ROOT_DIR / "src" / "templates" / "CSPM.template-manifest.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual_tables = {
            name: {
                "worksheet": details["worksheet"],
                "columns": details["columns"],
            }
            for name, details in inspection["tables"].items()
        }
        if spec.get("tables") != actual_tables:
            raise ValueError("CSPM template structure does not match its specification.")
        if manifest.get("expected_worksheets") != inspection["worksheets"]:
            raise ValueError("CSPM manifest worksheet inventory is stale.")
        if manifest.get("expected_tables") != list(inspection["tables"]):
            raise ValueError("CSPM manifest table inventory is stale.")
        if manifest.get("table_columns") != {
            name: details["columns"]
            for name, details in inspection["tables"].items()
        }:
            raise ValueError("CSPM manifest column inventory is stale.")
        if str(manifest.get("template_sha256", "")).upper() != sha256_file(path):
            raise ValueError("CSPM manifest hash does not match the candidate.")
        if inspection["confidentialRows"] != 0:
            raise ValueError("CSPM candidate contains non-header table rows.")
        result["ok"] = True
        result["details"].append("Spec, manifest, package, and empty-row policy agree")
    except Exception as exc:
        result["details"].append(str(exc))
    return result


def print_candidate_summary(name: str, path: Path, summary: dict, conf: dict):
    """Display a candidate summary."""
    print(f"\n{'='*60}")
    print(f"  CANDIDATE: {name}")
    print(f"{'='*60}")
    print(f"  Path:           {path}")
    print(f"  Exists:         {summary['exists']}")
    print(f"  Size:           {summary['size']:,} bytes")
    print(f"  SHA-256:        {summary['sha256']}")
    print(f"  Valid XLSM:     {summary['is_xlsm']}")
    print(f"  Macro-enabled:  {summary.get('macro_enabled', 'N/A')}")
    print(f"  Has VBA:        {summary['has_vba']}")
    print(f"  Worksheets:     {len(summary['worksheets'])}")
    for ws in summary["worksheets"]:
        print(f"    - {ws}")
    print(f"  Tables:         {len(summary['tables'])}")
    for t in summary["tables"]:
        print(f"    - {t}")
    print(f"  External links: {summary['external_links']}")
    print(f"\n  Confidentiality scan:")
    print(f"    Matches live:    {conf['matches_live']}")
    print(f"    Safe:            {conf['safe']}")
    for d in conf["details"]:
        print(f"    - {d}")


def approve_candidate(name: str, review_only: bool) -> tuple:
    """Ask for explicit approval. Returns (approved: bool, approver: str)."""
    if review_only:
        print(f"\n  [REVIEW-ONLY] Skipping approval prompt for {name}.")
        return False, ""

    print(f"\n  Do you approve {name}?")
    response = input("  Type 'APPROVE' to approve, or anything else to skip: ").strip()
    if response == "APPROVE":
        approver = input("  Enter your full name: ").strip()
        if not approver:
            print("  Approver name required. Skipping.")
            return False, ""
        return True, approver
    return False, ""


def main():
    review_only = "--review-only" in sys.argv

    if review_only:
        print("\n" + "=" * 60)
        print("  CSPM PHASE 9 CANDIDATE REVIEW (READ-ONLY)")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("  CSPM PHASE 9 CANDIDATE APPROVAL TOOL")
        print("=" * 60)

    # Compute live workbook hashes
    live_hashes = set()
    for wb_name in ["CSPM.xlsm", "Dockets.xlsm"]:
        wb_path = ROOT_DIR / "data" / wb_name
        if wb_path.exists():
            live_hashes.add(sha256_file(wb_path))

    print(f"\n  Live workbook hashes loaded: {len(live_hashes)}")

    # ── CSPM Template ──
    cspm_path = ROOT_DIR / "src" / "templates" / "CSPM.xlsm"
    cspm_summary = structural_summary(cspm_path)
    cspm_conf = confidentiality_check(cspm_path, live_hashes)
    cspm_governance = validate_cspm_governance(cspm_path)
    if not cspm_governance["ok"]:
        cspm_conf["safe"] = False
    cspm_conf["details"].extend(cspm_governance["details"])
    print_candidate_summary("CSPM.xlsm Template", cspm_path, cspm_summary, cspm_conf)

    # ── Dockets Template ──
    dock_path = ROOT_DIR / "src" / "templates" / "Dockets.xlsm"
    dock_summary = structural_summary(dock_path)
    dock_conf = confidentiality_check(dock_path, live_hashes)
    print_candidate_summary(
        "Dockets.xlsm Template", dock_path, dock_summary, dock_conf
    )

    # ── DummyMacro Fixture ──
    dummy_path = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "CSPM"
        / "Validation"
        / "GovernedFixtures"
        / "DummyMacro.xlsm"
    )
    dummy_manifest_path = (
        ROOT_DIR / "tests" / "fixtures" / "manifests" / "DummyMacro.manifest.json"
    )
    dummy_summary = structural_summary(dummy_path)
    dummy_conf = confidentiality_check(dummy_path, live_hashes)
    print_candidate_summary("DummyMacro.xlsm Fixture", dummy_path, dummy_summary, dummy_conf)

    if review_only:
        print("\n" + "=" * 60)
        print("  REVIEW COMPLETE — No changes made.")
        print("=" * 60)
        return

    # ── Approval phase ──
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    approval_record = {"timestamp": timestamp, "approvals": []}

    # Template approval JSON
    approval_json_path = ROOT_DIR / "src" / "templates" / "template_approval.json"
    with open(approval_json_path, "r", encoding="utf-8") as f:
        approval_data = json.load(f)

    # CSPM approval
    cspm_approved, cspm_approver = approve_candidate("CSPM.xlsm Template", review_only)
    if cspm_approved:
        # Revalidate hash before recording
        current_hash = sha256_file(cspm_path)
        if current_hash != cspm_summary["sha256"]:
            print("  ERROR: CSPM hash changed since scan! Refusing approval.")
            cspm_approved = False
        elif not cspm_conf["safe"]:
            print("  ERROR: CSPM failed confidentiality scan! Refusing approval.")
            cspm_approved = False
        else:
            for tmpl in approval_data["templates"]:
                if tmpl["approved_filename"] == "CSPM.xlsm":
                    tmpl["human_approval_status"] = "APPROVED"
                    tmpl["sha256"] = current_hash
            cspm_manifest_path = ROOT_DIR / "src" / "templates" / "CSPM.template-manifest.json"
            cspm_manifest = json.loads(cspm_manifest_path.read_text(encoding="utf-8"))
            cspm_manifest["approval_status"] = "APPROVED"
            cspm_manifest["approver"] = cspm_approver
            cspm_manifest["approval_date"] = timestamp
            cspm_manifest["approval_note"] = "Approved via approve_phase9_candidates.py"
            cspm_manifest_path.write_text(
                json.dumps(cspm_manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            approval_record["approvals"].append(
                {
                    "file": "CSPM.xlsm",
                    "status": "APPROVED",
                    "approver": cspm_approver,
                    "hash": current_hash,
                }
            )
            print(f"  ✓ CSPM.xlsm approved by {cspm_approver}")

    # Dockets approval
    dock_approved, dock_approver = approve_candidate(
        "Dockets.xlsm Template", review_only
    )
    if dock_approved:
        current_hash = sha256_file(dock_path)
        if current_hash != dock_summary["sha256"]:
            print("  ERROR: Dockets hash changed since scan! Refusing approval.")
            dock_approved = False
        elif not dock_conf["safe"]:
            print("  ERROR: Dockets failed confidentiality scan! Refusing approval.")
            dock_approved = False
        else:
            for tmpl in approval_data["templates"]:
                if tmpl["approved_filename"] == "Dockets.xlsm":
                    tmpl["human_approval_status"] = "APPROVED"
                    tmpl["sha256"] = current_hash
            approval_record["approvals"].append(
                {
                    "file": "Dockets.xlsm",
                    "status": "APPROVED",
                    "approver": dock_approver,
                    "hash": current_hash,
                }
            )
            print(f"  ✓ Dockets.xlsm approved by {dock_approver}")

    # DummyMacro approval
    dummy_approved, dummy_approver = approve_candidate(
        "DummyMacro.xlsm Fixture", review_only
    )
    if dummy_approved and dummy_manifest_path.exists():
        current_hash = sha256_file(dummy_path)
        if current_hash != dummy_summary["sha256"]:
            print("  ERROR: DummyMacro hash changed since scan! Refusing approval.")
            dummy_approved = False
        elif not dummy_conf["safe"]:
            print("  ERROR: DummyMacro failed confidentiality scan! Refusing approval.")
            dummy_approved = False
        else:
            dm_data = json.loads(dummy_manifest_path.read_text("utf-8"))
            dm_data["approval_status"] = "APPROVED"
            dm_data["approver"] = dummy_approver
            dm_data["approval_date"] = timestamp
            dm_data["approval_note"] = "Approved via approve_phase9_candidates.py"
            dummy_manifest_path.write_text(
                json.dumps(dm_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            approval_record["approvals"].append(
                {
                    "file": "DummyMacro.xlsm",
                    "status": "APPROVED",
                    "approver": dummy_approver,
                    "hash": current_hash,
                }
            )
            print(f"  ✓ DummyMacro.xlsm approved by {dummy_approver}")

    # Write approval JSON
    if cspm_approved or dock_approved:
        with open(approval_json_path, "w", encoding="utf-8") as f:
            json.dump(approval_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    # Write timestamped approval record
    record_dir = ROOT_DIR / "src" / "templates" / "approval_records"
    record_dir.mkdir(exist_ok=True)
    record_name = f"approval_{now.strftime('%Y%m%d_%H%M%S')}.json"
    record_path = record_dir / record_name
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(approval_record, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n  Approval record saved: {record_path}")
    print()

    # Summary
    if cspm_approved and dock_approved and dummy_approved:
        print("  All three candidates approved.")
        print("  To build the production release, run:")
        print("    python scripts/build_release.py")
    elif cspm_approved or dock_approved or dummy_approved:
        print("  Partial approval recorded. Review remaining items.")
    else:
        print("  No candidates approved in this session.")


if __name__ == "__main__":
    main()
