import re

path = r"c:\Projects\__CSPM\src\templates\invoices\Concept_A.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add @page rule to <style>
if "@page {" not in content:
    content = content.replace("<style>", "<style>\n    @page {\n        size: Letter portrait;\n        margin: 0;\n    }\n")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Concept_A patched successfully.")
