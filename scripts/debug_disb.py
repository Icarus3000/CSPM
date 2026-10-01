import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src/python")))
from repositories.excel_repo import ExcelRepo, TBL_DISBURSEMENTS, TBL_TIME
from services.paths import AppPaths
from domain import schema_constants as sc
import json

paths = AppPaths(Path("c:\\Projects\\__CSPM"))
repo = ExcelRepo(paths)
disb = repo._read_table_rows(TBL_DISBURSEMENTS)
time = repo._read_table_rows(TBL_TIME)

print(f"Total time entries: {len(time)}")
print(f"Total disbursements: {len(disb)}")

for r in disb:
    client = str(r.get(sc.COL_DISB_CLIENT_ID) or "")
    matter = str(r.get(sc.COL_DISB_MATTER_ID) or "")
    desc = str(r.get(sc.COL_DISB_DESCRIPTION) or "")
    parent = str(r.get(sc.COL_DISB_PARENT_ID) or "")
    status = str(r.get(sc.COL_DISB_PAYMENT_STATUS) or "")
    ref = str(r.get(sc.COL_DISB_INVOICE_REF) or "")
    
    if "Tours" in client or "Tours" in matter or "Tours" in desc or "26-0187" in matter:
        print("MATCH FOUND:")
        print(f"  ID: {r.get(sc.COL_DISB_ID)}")
        print(f"  Client ID: {client}")
        print(f"  Matter ID: {matter}")
        print(f"  Parent ID: {parent}")
        print(f"  Desc: {desc}")
        print(f"  Status: {status}")
        print(f"  Invoice Ref: {ref}")
