import codecs, re
with codecs.open('src/qml/components/ClientLedgerReportPanel.qml', 'r', 'utf-8') as f: c=f.read()
m=re.search(r'MouseArea\s*{\s*id: resizeHandle.*?onCanceled:', c, re.DOTALL)
if m: print(m.group(0))
else: print('not found')
