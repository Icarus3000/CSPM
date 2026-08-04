import codecs
with codecs.open('src/qml/components/ClientLedgerReportPanel.qml', 'r', 'utf-8') as f:
    text = f.read()

start = text.find('function setColumnWidth')
print(text[start:start+1500])
