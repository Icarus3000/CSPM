import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.abspath('src/python'))
from services.paths import AppPaths
from repositories.excel_repo import ExcelRepo
from services.dockets_import_service import DocketsImportService

paths = AppPaths(Path(os.path.abspath('.')))
repo = ExcelRepo(paths)
service = DocketsImportService(repo)

legacy_file = os.path.abspath('data/Dockets.xlsm')
try:
    results = service.analyze_legacy_workbook(legacy_file)
    cutoff_date = datetime(2026, 6, 13)
    
    adds = [
        row for row in results['rows'] 
        if row['sheet'] == 'Dockets' and row['action'] == 'add'
    ]
    
    old_adds = []
    for row in adds:
        d_val = row['payload'].get('Date')
        if not d_val:
            continue
        try:
            if isinstance(d_val, str):
                d = datetime.strptime(d_val.split(' ')[0], '%Y-%m-%d')
            else:
                d = d_val
            if d < cutoff_date:
                old_adds.append(row)
        except Exception:
            pass

    print(f"Total old dockets (before June 12, 2026) added: {len(old_adds)}")
    
    if old_adds:
        print("First 5 old dockets being added:")
        for row in old_adds[:5]:
            p = row['payload']
            print(f"  {p.get('Date')} | {p.get('Client')} | {p.get('Description')} | Hrs: {p.get('Time (in hrs)')}")
            
except Exception as e:
    import traceback
    traceback.print_exc()

