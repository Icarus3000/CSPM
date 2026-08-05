import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from repositories.excel_repo import ExcelRepo, TBL_TIME
from services.paths import AppPaths
from domain import schema_constants as sc

paths = AppPaths(Path("c:\\Projects\\__CSPM"))
repo = ExcelRepo(paths)
rows = repo._read_table_rows(TBL_TIME)

from collections import defaultdict
grouped = defaultdict(list)
for r in rows:
    date = str(r.get(sc.COL_TIME_DATE) or "")
    client = str(r.get(sc.COL_TIME_CLIENT_ID) or "")
    matter = str(r.get(sc.COL_TIME_MATTER_ID) or "")
    desc = str(r.get(sc.COL_TIME_DESC) or "")
    key = (date, client, matter, desc)
    grouped[key].append(r.get(sc.COL_TIME_ENTRY_ID))

print(f"Total rows: {len(rows)}")
count_dup = 0
for k, v in grouped.items():
    if len(v) > 1:
        print(f"DUPLICATE: {k} -> {v}")
        count_dup += 1
print(f"Total duplicates found: {count_dup}")
