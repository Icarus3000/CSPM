import sys

with open(r'c:\Projects\__CSPM\src\python\repositories\excel_repo.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = '''        if isinstance(value, (int, float)):
            number = float(value)
            if math.isnan(number) or math.isinf(number):
                return str(number)
            return format(Decimal(str(value)).normalize(), "f")'''

replacement = '''        if isinstance(value, (int, float)):
            number = float(value)
            if math.isnan(number) or math.isinf(number):
                return str(number)
            if number == 0.0:
                value = 0.0
            return format(Decimal(str(value)).normalize(), "f")'''

new_code = code.replace(target, replacement)
if code == new_code:
    print('Failed to replace string! The target was not found exactly.')
else:
    with open(r'c:\Projects\__CSPM\src\python\repositories\excel_repo.py', 'w', encoding='utf-8') as f:
        f.write(new_code)
    print('Replaced successfully!')
