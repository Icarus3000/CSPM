import codecs
with codecs.open('src/qml/components/ARAgingReportPanel.qml', 'r', 'utf-8') as f:
    text = f.read()

start = text.find('function setTableColumnWidth')
print(text[start:start+1500])
