import re
with open('scratch_ar_report.qml', 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r'function _ensureTableState.*?function _tableColumnIndexByKey', content, re.DOTALL)
if m:
    print(m.group(0))
else:
    print('Not found')
