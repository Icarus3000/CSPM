import openpyxl
wb = openpyxl.load_workbook('c:/Projects/__CSPM/data/CSPM.xlsm', data_only=True)
ws_time = wb['TimeEntries']
headers_t = [c.value for c in ws_time[1]]
time_entries = [dict(zip(headers_t, [c.value for c in row])) for row in ws_time.iter_rows(min_row=2)]
a2b_time = [t for t in time_entries if 'A2B' in str(t.get('ClientName', '')) or 'ABDI' in str(t.get('ClientID', ''))]
for t in a2b_time:
    print(t.get('EntryID'), t.get('ClientID'), t.get('ParentID'))
