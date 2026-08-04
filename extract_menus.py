import sys, os, re

path = r'c:\Projects\__CSPM\src\qml\views\PlaceholderSubmenuView.qml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

labels = re.findall(r'title:\s*"([^"]+)"', content)
print(set(labels))
