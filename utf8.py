import codecs
with codecs.open("scratch_ledger.qml", "r", "utf-16") as f:
    c = f.read()
with codecs.open("scratch_ledger.qml", "w", "utf-8") as f:
    f.write(c)
