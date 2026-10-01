import sys
sys.path.append('src/python')

try:
    from services.paths import PathManager
    from repositories.excel_repo import ExcelRepo, TBL_TIME, TBL_DISBURSEMENTS
    import domain.schema_constants as sc
    
    repo = ExcelRepo(PathManager())
    
    time = repo._read_table_rows(TBL_TIME)
    disb = repo._read_table_rows(TBL_DISBURSEMENTS)
    
    print('Time rows:', len(time))
    print('Disb rows:', len(disb))
    
    for d in disb:
        print('DISB:', d.get(sc.COL_DISB_ID), d.get(sc.COL_DISB_MATTER_ID), d.get(sc.COL_DISB_INVOICE_REF))
except Exception as e:
    import traceback
    traceback.print_exc()
