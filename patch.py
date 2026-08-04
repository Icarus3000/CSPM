import os
d = r'c:\Projects\__CSPM\src\templates\invoices'
for f in os.listdir(d):
    if f.endswith('.html') and f != 'Concept_A2.html':
        p = os.path.join(d, f)
        with open(p, 'r', encoding='utf-8') as file:
            c = file.read()
        if '<span>Total Professional Time</span>' not in c and '<span>Total Professional Fees</span>' in c:
            c = c.replace(
                '<span>Total Professional Fees</span>',
                '<span>Total Professional Time</span>\n                                <span class="totals-val">{{ "{:,.1f}".format(total_hours) }} hours</span>\n                            </div>\n                            <div class="totals-row">\n                                <span>Total Professional Fees</span>'
            )
            with open(p, 'w', encoding='utf-8') as file:
                file.write(c)
            print(f'Patched {f}')
