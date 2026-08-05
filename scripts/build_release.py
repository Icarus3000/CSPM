import os
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def validate_templates(template_dir: Path, manifest_path: Path, allow_candidate: bool = False):
    import zipfile
    import hashlib
    import xml.etree.ElementTree as ET
    
    if not manifest_path.exists():
        print("ERROR: Build blocked. template_approval.json is missing.")
        raise Exception("manifest_missing")
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        approved_manifest = json.load(f)
        
    for item in approved_manifest.get("templates", []):
        status = item.get("human_approval_status", "")
        if status == "APPROVED":
            pass  # OK
        elif status == "CANDIDATE_AWAITING_CORY_APPROVAL" and allow_candidate:
            print(f"WARNING: Template {item.get('approved_filename')} is a CANDIDATE (non-production validation).")
        else:
            print(f"ERROR: Build blocked. Template {item.get('approved_filename')} status is '{status}', requires APPROVED.")
            raise Exception("unapproved")
            
        tmpl_path = template_dir / item["approved_filename"]
        if not tmpl_path.exists():
            print(f"ERROR: Build blocked. Missing approved template: {tmpl_path}")
            raise Exception("template_missing")
            
        if not zipfile.is_zipfile(tmpl_path):
            print(f"ERROR: Build blocked. Not a valid ZIP: {tmpl_path}")
            raise Exception("invalid_zip")
            
        h = hashlib.sha256()
        with open(tmpl_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        template_hash = h.hexdigest().upper()
        expected_hash = item.get("sha256", "")
        if not expected_hash:
            print(f"ERROR: Build blocked. Blank SHA-256 field for {tmpl_path}.")
            raise Exception("blank_hash")
        if template_hash != expected_hash.upper():
            print(f"ERROR: Build blocked. Template hash mismatch for {tmpl_path}.")
            raise Exception("hash_mismatch")
            
        with zipfile.ZipFile(tmpl_path, "r") as zf:
            namelist = zf.namelist()
            vba_policy = item.get("vba_policy", "required_governed")
            has_vba = "xl/vbaProject.bin" in namelist
            expected_vba_hash = item.get("vbaProject_sha256")
            
            if vba_policy == "required_governed":
                if not has_vba:
                    print(f"ERROR: Build blocked. Missing xl/vbaProject.bin in {tmpl_path} (Policy: {vba_policy})")
                    raise Exception("missing_vba")
                if zf.getinfo("xl/vbaProject.bin").file_size == 0:
                    print(f"ERROR: Build blocked. xl/vbaProject.bin is empty in {tmpl_path} (Policy: {vba_policy})")
                    raise Exception("empty_vba")
                if not expected_vba_hash:
                    print(f"ERROR: Build blocked. vbaProject_sha256 missing from manifest for {tmpl_path} (Policy: {vba_policy})")
                    raise Exception("missing_vba_hash")
                vba_hash = hashlib.sha256(zf.read("xl/vbaProject.bin")).hexdigest().upper()
                if vba_hash != expected_vba_hash.upper():
                    print(f"ERROR: Build blocked. Unapproved VBA payload in {tmpl_path} (Policy: {vba_policy})")
                    raise Exception("unapproved_vba")
                    
            elif vba_policy == "optional_governed":
                if has_vba:
                    if zf.getinfo("xl/vbaProject.bin").file_size == 0:
                        print(f"ERROR: Build blocked. xl/vbaProject.bin is empty in {tmpl_path} (Policy: {vba_policy})")
                        raise Exception("empty_vba")
                    if not expected_vba_hash:
                        print(f"ERROR: Build blocked. vbaProject_sha256 missing from manifest for {tmpl_path} with VBA present (Policy: {vba_policy})")
                        raise Exception("missing_vba_hash")
                    vba_hash = hashlib.sha256(zf.read("xl/vbaProject.bin")).hexdigest().upper()
                    if vba_hash != expected_vba_hash.upper():
                        print(f"ERROR: Build blocked. Unapproved VBA payload in {tmpl_path} (Policy: {vba_policy})")
                        raise Exception("unapproved_vba")
                        
            elif vba_policy == "prohibited":
                if has_vba:
                    print(f"ERROR: Build blocked. Prohibited xl/vbaProject.bin found in {tmpl_path} (Policy: {vba_policy})")
                    raise Exception("prohibited_vba")
                    
            if "xl/workbook.xml" not in namelist or "[Content_Types].xml" not in namelist or "xl/_rels/workbook.xml.rels" not in namelist:
                print(f"ERROR: Build blocked. Missing critical workbook parts in {tmpl_path}")
                raise Exception("missing_critical")
                
            ct_data = zf.read("[Content_Types].xml")
            if vba_policy == "required_governed":
                if b"application/vnd.ms-excel.sheet.macroEnabled.main+xml" not in ct_data:
                    print(f"ERROR: Build blocked. Not a macro-enabled content type in {tmpl_path}")
                    raise Exception("not_macro_enabled")
                
            external_links = [n for n in namelist if n.startswith("xl/externalLinks/") and n.endswith(".xml")]
            if external_links:
                print(f"ERROR: Build blocked. Prohibited external links found in {tmpl_path}: {external_links}")
                raise Exception("external_links")
                
            wb_xml = zf.read("xl/workbook.xml")
            wb_root = ET.fromstring(wb_xml)
            ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
            
            sheet_rids = {}
            for sheet in wb_root.findall(".//ns:sheet", ns):
                sheet_name = sheet.get("name")
                r_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                if sheet_name and r_id:
                    sheet_rids[r_id] = sheet_name
                    
            wb_rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            sheet_paths = {}
            for rel in wb_rels.findall(".//pkg:Relationship", {"pkg": "http://schemas.openxmlformats.org/package/2006/relationships"}):
                if rel.get("Id") in sheet_rids:
                    target = rel.get("Target")
                    if target.startswith("/"): target = target[1:]
                    sheet_paths[sheet_rids[rel.get("Id")]] = "xl/" + target if not target.startswith("xl/") else target
                    
            found_sheets = list(sheet_paths.keys())
            for req_sheet in item.get("required_worksheets", []):
                if req_sheet not in found_sheets:
                    print(f"ERROR: Build blocked. Missing required worksheet '{req_sheet}' in {tmpl_path}")
                    raise Exception("missing_worksheet")
                    
            table_to_sheet = {}
            found_tables = {}
            for sname, spath in sheet_paths.items():
                if "/" in spath:
                    parts = spath.split("/")
                    rels_path = "/".join(parts[:-1]) + "/_rels/" + parts[-1] + ".rels"
                else:
                    rels_path = "_rels/" + spath + ".rels"
                    
                if rels_path in namelist:
                    srels = ET.fromstring(zf.read(rels_path))
                    for rel in srels.findall(".//pkg:Relationship", {"pkg": "http://schemas.openxmlformats.org/package/2006/relationships"}):
                        if "relationships/table" in rel.get("Type", ""):
                            t_target = rel.get("Target")
                            owner_dir = rels_path.split("/")[:-2] # xl/worksheets
                            if t_target.startswith("/"):
                                # Absolute path within the ZIP — strip leading /
                                final_target = t_target[1:]
                            elif t_target.startswith("../"):
                                base = owner_dir[:-1] # xl
                                final_target = "/".join(base) + "/" + t_target[3:] if base else t_target[3:]
                            else:
                                final_target = "/".join(owner_dir) + "/" + t_target if owner_dir else t_target
                                
                            if final_target in namelist:
                                tbl_xml = zf.read(final_target)
                                tbl_root = ET.fromstring(tbl_xml)
                                t_name = tbl_root.get("name")
                                if t_name:
                                    cols = [col.get("name") for col in tbl_root.findall(".//ns:tableColumn", ns) if col.get("name")]
                                    found_tables[t_name] = cols
                                    table_to_sheet[t_name] = sname

            req_tables = item.get("required_tables", {})
            if isinstance(req_tables, list):
                req_tables = {t: {} for t in req_tables}
                
            for req_table_name, req_table_def in req_tables.items():
                if req_table_name not in found_tables:
                    print(f"ERROR: Build blocked. Missing required table '{req_table_name}' in {tmpl_path}")
                    raise Exception("missing_table")
                
                req_sheet_for_table = req_table_def.get("worksheet") if isinstance(req_table_def, dict) else None
                if req_sheet_for_table and table_to_sheet.get(req_table_name) != req_sheet_for_table:
                    print(f"ERROR: Build blocked. Table '{req_table_name}' mapped to wrong sheet '{table_to_sheet.get(req_table_name)}', expected '{req_sheet_for_table}' in {tmpl_path}")
                    raise Exception("wrong_table_mapping")
                    
                req_columns = req_table_def.get("required_columns", []) if isinstance(req_table_def, dict) else []
                for req_col in req_columns:
                    if req_col not in found_tables[req_table_name]:
                        print(f"ERROR: Build blocked. Missing required column '{req_col}' in table '{req_table_name}' in {tmpl_path}")
                        raise Exception("missing_column")
                        
    return approved_manifest

def main():
    parser = argparse.ArgumentParser(description="CSPM Release Builder")
    parser.add_argument("--installer", action="store_true", help="Compile Inno Setup installer after PyInstaller builds")
    parser.add_argument("--validate", action="store_true", help="Run post-build validation checks")
    parser.add_argument("--candidate-validation", action="store_true", help="Allow CANDIDATE_AWAITING_CORY_APPROVAL templates for non-production validation builds")
    parser.add_argument("--distpath", help="Override dist output directory")
    parser.add_argument("--workpath", help="Override PyInstaller work directory")
    args = parser.parse_args()

    if args.candidate_validation:
        print("==================================================")
        print("  CSPM CANDIDATE VALIDATION BUILD (NON-PRODUCTION)")
        print("==================================================")
    else:
        print("==================================================")
        print("       CSPM RELEASE BUILDER (PYINSTALLER) ")
        print("==================================================")

    # 1. Read version
    ver_path = ROOT_DIR / "version.json"
    app_version = "Unknown"
    if ver_path.exists():
        with open(ver_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            app_version = data.get("version", "Unknown")
            
    print(f"Target version: {app_version}")
    
    # PRE-FLIGHT GATE: Template Governance
    template_dir = ROOT_DIR / "src" / "templates"
    manifest_path = template_dir / "template_approval.json"
    
    try:
        approved_manifest = validate_templates(template_dir, manifest_path, allow_candidate=args.candidate_validation)
    except Exception as e:
        print(f"Preflight validation failed: {e}")
        sys.exit(1)
    
    # 2. Setup output directories
    target_dist_dir = Path(args.distpath).resolve() if args.distpath else ROOT_DIR / "dist"
    build_dir = Path(args.workpath).resolve() if args.workpath else ROOT_DIR / "build"
    
    staging_dist_dir = target_dist_dir.parent / f"{target_dist_dir.name}_staging_{os.getpid()}"
    
    protected_paths = [
        ROOT_DIR / "data",
        ROOT_DIR / "src",
        Path.home() / "Documents" / "CSPM_Protected_Backups",
        Path(os.environ.get("LOCALAPPDATA", "")) / "CSPM" / "Validation" / "GovernedFixtures"
    ]
    for p in protected_paths:
        try:
            if target_dist_dir == p or p in target_dist_dir.parents:
                print(f"ERROR: dist_dir overlaps with protected path: {p}")
                sys.exit(1)
            if build_dir == p or p in build_dir.parents:
                print(f"ERROR: build_dir overlaps with protected path: {p}")
                sys.exit(1)
        except Exception:
            pass
            
    print(f"Resolved target dist dir: {target_dist_dir}")
    print(f"Resolved staging dist dir: {staging_dist_dir}")
    print(f"Resolved build dir: {build_dir}")

    if target_dist_dir.exists():
        print(f"Warning: target dist dir {target_dist_dir} exists, it will be replaced.")
    if staging_dist_dir.exists():
        shutil.rmtree(staging_dist_dir, ignore_errors=True)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
        
    print("Cleaned build directories.")
    dist_dir = staging_dist_dir
    
    # 3. Build Main Application (CSPM.exe)
    main_script = ROOT_DIR / "src" / "python" / "main.py"
    
    datas = [
        ("src/qml", "src/qml"),
        ("src/templates", "src/templates"),
        ("src/assets", "src/assets"),
        ("schema", "schema"),
        ("docs", "docs"),
        ("version.json", ".")
    ]
    
    cmd_main = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "CSPM",
        "--icon=src/assets/app_icon.ico",
        "--distpath", str(dist_dir),
        "--workpath", str(build_dir),
    ]
    
    for src, dst in datas:
        cmd_main.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        
    cmd_main.append(str(main_script))
    
    print(f"Running PyInstaller for Main App...")
    result_main = subprocess.run(cmd_main, cwd=ROOT_DIR)
    
    if result_main.returncode != 0:
        print("ERROR: PyInstaller build for Main App failed.")
        sys.exit(1)

    # 4. Build Recovery Utility (CSPM_Recovery.exe)
    recovery_script = ROOT_DIR / "scripts" / "cspm_recovery.py"
    
    cmd_rec = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--console",
        "--name", "CSPM_Recovery",
        "--distpath", str(dist_dir / "CSPM"), # Put it inside the main CSPM dist folder
        "--workpath", str(build_dir),
    ]
    cmd_rec.append(str(recovery_script))

    print(f"Running PyInstaller for Recovery Utility...")
    result_rec = subprocess.run(cmd_rec, cwd=ROOT_DIR)

    if result_rec.returncode != 0:
        print("ERROR: PyInstaller build for Recovery Utility failed.")
        sys.exit(1)
        
    print("\n[SUCCESS] PyInstaller bundles created in dist/CSPM/")
    
    # 5. Handle initial templates
    dist_cspm = dist_dir / "CSPM"
    dist_data = dist_cspm / "data"
    dist_data.mkdir(exist_ok=True)
    
    import hashlib as _hl
    template_dir = ROOT_DIR / "src" / "templates"
    
    # Compute live workbook hashes for post-bundle confidentiality check
    live_hashes = set()
    for live_name in ["CSPM.xlsm", "Dockets.xlsm"]:
        live_path = ROOT_DIR / "data" / live_name
        if live_path.exists():
            live_h = _hl.sha256(live_path.read_bytes()).hexdigest().upper()
            live_hashes.add(live_h)
            
    for item in approved_manifest["templates"]:
        wb = item["approved_filename"]
        tmpl_path = template_dir / wb
        if not tmpl_path.exists():
            print(f"ERROR: Build blocked. Template not found in src/templates: {wb}")
            sys.exit(1)
            
        dest_file = dist_data / wb
        shutil.copy2(tmpl_path, dest_file)
        
        # Post-bundle confidentiality check
        bundled_hash = _hl.sha256(dest_file.read_bytes()).hexdigest().upper()
        if bundled_hash in live_hashes:
            print(f"CRITICAL: Bundled {wb} matches a live production workbook hash!")
            print(f"Build aborted for confidentiality violation.")
            sys.exit(1)
            
        print(f"BUNDLED TEMPLATE: {wb}")
        print(f"  Source: {tmpl_path}")
        print(f"  SHA-256: {bundled_hash}")
        print(f"  Live-hash match: NO (safe)")
            
    print("PyInstaller build complete.")
    
    if args.installer:
        print("\nCompiling Inno Setup installer...")
        iss_path = ROOT_DIR / "scripts" / "cspm_installer.iss"
        # Check standard and non-admin paths
        iscc_paths = [
            os.environ.get("LOCALAPPDATA", "") + "\\Programs\\Inno Setup 7\\ISCC.exe",
            os.environ.get("LOCALAPPDATA", "") + "\\Programs\\Inno Setup 6\\ISCC.exe",
            "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
            "C:\\Program Files\\Inno Setup 6\\ISCC.exe",
            "C:\\Program Files (x86)\\Inno Setup 7\\ISCC.exe",
            "C:\\Program Files\\Inno Setup 7\\ISCC.exe"
        ]
        
        iscc_exe = None
        for p in iscc_paths:
            if p and os.path.exists(p):
                iscc_exe = p
                break
                
        if not iscc_exe:
            print("ERROR: ISCC.exe not found. Cannot compile installer.")
            sys.exit(1)
            
        print(f"Using ISCC: {iscc_exe}")
        
        iscc_cmd = [iscc_exe, f"/O{dist_dir}", str(iss_path)]
        print(f"Running ISCC Command: {' '.join(iscc_cmd)}")
        result_iss = subprocess.run(iscc_cmd, cwd=ROOT_DIR)
        
        if result_iss.returncode != 0:
            print(f"ERROR: ISCC compilation failed with exit code {result_iss.returncode}.")
            sys.exit(1)
            
        print("[SUCCESS] Installer compiled in dist/")
        
        if args.validate:
            installer_name = f"CSPM-Setup-{app_version}.exe"
            installer_path = dist_dir / installer_name
            if installer_path.exists():
                print(f"Validation: {installer_name} exists.")
                print(f"Size: {installer_path.stat().st_size} bytes")
            else:
                print(f"ERROR: Expected installer {installer_name} not found in dist/")
                sys.exit(1)
    
    # Finally, promote staging to target dist_dir
    if target_dist_dir.exists():
        shutil.rmtree(target_dist_dir, ignore_errors=True)
    try:
        os.rename(staging_dist_dir, target_dist_dir)
        print(f"Promoted {staging_dist_dir} to {target_dist_dir}")
    except OSError as e:
        print(f"Failed to promote staging dir to {target_dist_dir}: {e}")
        print(f"Build artifacts are available in {staging_dist_dir}")
        sys.exit(1)
    
    print("Build process finished successfully.")

if __name__ == "__main__":
    main()
