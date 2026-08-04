import sys

with open(r'c:\Projects\__CSPM\src\python\repositories\excel_repo.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = '''                if actual_sig != expected_sig:
                    import logging
                    log = logging.getLogger("app.import")
                    log.error(f"Mismatch in {tref.table}")
                    if len(actual_sig) != len(expected_sig):
                        log.error(f"Length mismatch: {len(actual_sig)} vs {len(expected_sig)}")
                    else:
                        for i, (act, exp) in enumerate(zip(actual_sig, expected_sig)):
                            if act != exp:
                                mismatches.append({"index": i, "expected": exp, "actual": act})
                    for m in mismatches:
                        logger.error(f"Mismatch in {tref.table} Row {m['index']}:\\nExpected: {m['expected']}\\nActual:   {m['actual']}")
                    raise RuntimeError(f"Post-save verification failed for import batch table {tref.table}. Details: {mismatches[0]}")'''

replacement = '''                if actual_sig != expected_sig:
                    import logging
                    log = logging.getLogger("app.import")
                    log.error(f"Mismatch in {tref.table}")
                    mismatches = []
                    if len(actual_sig) != len(expected_sig):
                        log.error(f"Length mismatch: {len(actual_sig)} vs {len(expected_sig)}")
                        mismatches.append({"index": -1, "expected": f"length {len(expected_sig)}", "actual": f"length {len(actual_sig)}"})
                    else:
                        for i, (act, exp) in enumerate(zip(actual_sig, expected_sig)):
                            if act != exp:
                                mismatches.append({"index": i, "expected": exp, "actual": act})
                    for m in mismatches:
                        log.error(f"Mismatch in {tref.table} Row {m['index']}:\\nExpected: {m['expected']}\\nActual:   {m['actual']}")
                    raise RuntimeError(f"Post-save verification failed for import batch table {tref.table}. Details: {mismatches[0] if mismatches else 'Length mismatch'}")'''

new_code = code.replace(target, replacement)
if code == new_code:
    print('Failed to replace string! The target was not found exactly.')
else:
    with open(r'c:\Projects\__CSPM\src\python\repositories\excel_repo.py', 'w', encoding='utf-8') as f:
        f.write(new_code)
    print('Replaced successfully!')
