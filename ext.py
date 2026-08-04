import codecs
with codecs.open('src/qml/components/ClientLedgerReportPanel.qml', 'r', 'utf-8') as f:
    c = f.read()
start = c.find('ListModel')
print(c[start:start+1500])
