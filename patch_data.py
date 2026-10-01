import sys, os

sys.path.insert(0, os.path.join(os.getcwd(), 'src', 'python'))

from services.paths import AppPaths
from repositories.excel_repo import ExcelRepo
from domain import schema_constants as sc

paths = AppPaths()
repo = ExcelRepo(paths)

disbursements = repo._read_table_rows(sc.TBL_DISBURSEMENTS)
changed = False

for r in disbursements:
    # "Truexperiences Tours Inc." is C0064 based on earlier context? Let's check client name.
    # The prompt said Truexperiences Tours Inc.
    client_name = r.get(sc.COL_DISB_CLIENT_NAME) or ""
    sub_client = r.get(sc.COL_DISB_SUB_CLIENT) or ""
    parent_id = r.get(sc.COL_DISB_PARENT_ID) or ""
    client_id = r.get(sc.COL_DISB_CLIENT_ID) or ""

    # If it's Tours Inc, it likely has no ParentID and no ClientName
    if (not parent_id) and client_id:
        # Patch parent id to be client id
        r[sc.COL_DISB_PARENT_ID] = client_id
        changed = True
        print(f"Patched ParentID for {r.get(sc.COL_DISB_ID)}")
    
    if (not client_name) and sub_client:
        # Patch client name to be sub client
        r[sc.COL_DISB_CLIENT_NAME] = sub_client
        changed = True
        print(f"Patched ClientName for {r.get(sc.COL_DISB_ID)}")
        
if changed:
    repo._write_table_rows(sc.TBL_DISBURSEMENTS, disbursements)
    print("Saved changes.")
else:
    print("No changes needed.")
