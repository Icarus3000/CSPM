import codecs, re
with codecs.open('src/qml/components/ARAgingReportPanel.qml', 'r', 'utf-8') as f: c=f.read()
m=re.search(r'function tableSortedRows.*?return out\s*}', c, re.DOTALL)
if m: print(m.group(0))
else: print('not found')
