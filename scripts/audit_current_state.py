import os
import re

REPO_DIR = r"C:\Projects\__CSPM"
PYTHON_DIR = os.path.join(REPO_DIR, "src", "python")
QML_DIR = os.path.join(REPO_DIR, "src", "qml")
DOCS_DIR = os.path.join(REPO_DIR, "docs")

CONCEPTS = {
    "Transaction Class": r"(?i)\bclass\b.*\b(transaction|expense|income)\b",
    "BusinessUnit": r"(?i)\bbusiness_?unit\b|\bbusiness unit\b",
    "Owner or family-member attribution": r"(?i)\bowner\b|\bfamily_?member\b|\bhousehold_?member\b",
    "Households": r"(?i)\bhousehold\b|\bfamily\b",
    "Accounts": r"(?i)\baccount(s|id|_id)?\b",
    "Categories": r"(?i)\bcategor(y|ies)\b",
    "Payees and vendors": r"(?i)\bpayee(s)?\b|\bvendor(s)?\b",
    "Tax flags": r"(?i)\btax_?(flag|status|exempt|code|rate)\b",
    "Tax rates": r"(?i)\btax_?rate\b|\bhst_?rate\b|\b13%\b|\b0\.13\b",
    "Tax Exempt controls": r"(?i)\b(tax)?_?exempt\b",
    "Supply tax status": r"(?i)\bsupply_?(tax)?_?status\b|\b(taxable|zero-rated|exempt|out-of-scope)\b",
    "HST collected": r"(?i)\bhst_?collected\b",
    "Vendor HST paid": r"(?i)\bvendor_?hst\b|\btax_?paid\b",
    "ITC eligibility": r"(?i)\bitc_?(eligible|eligibility|percentage|amount)\b",
    "ITC amounts claimed": r"(?i)\bitc_?claimed\b",
    "General office expense treatment": r"(?i)\bgeneral_?office_?expense\b",
    "Personal expense treatment": r"(?i)\bpersonal_?expense\b|\bpersonal_?use\b",
    "Client-matter expense treatment": r"(?i)\bclient_?matter_?expense\b|\bdisbursement\b",
    "Budget records and screens": r"(?i)\bbudget\b",
    "Financial dashboards": r"(?i)\bfinancial_?dashboard\b|\bdashboard_?financial\b",
    "Transaction reports": r"(?i)\btransaction_?report\b|\breport_?transaction\b",
    "Income and expense reports": r"(?i)\bincome_?(and)?_?expense_?report\b",
    "Quarterly or period-based HST reports": r"(?i)\b(quarterly|period)_?hst_?report\b|\bhst_?return\b",
    "Excel and CSV exports": r"(?i)\bexport_?(excel|csv)\b",
    "Governed business-unit settings": r"(?i)\bgoverned_?setting(s)?\b|\bdefault_?account\b",
    "Existing Deborah-specific records": r"(?i)\bdeborah\b|\bot\s?-\s?private\b|\bot\s?-\s?vha\b",
    "Existing family-spending records": r"(?i)\bfamily_?spending\b",
    "Existing tax reconciliation logic": r"(?i)\btax_?reconciliation\b",
    "Existing account and category filtering": r"(?i)\baccount_?filter\b|\bcategory_?filter\b",
    "Existing result drill-down": r"(?i)\bdrill[-_]?down\b"
}

def scan_directory(directory):
    results = {k: 0 for k in CONCEPTS}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".py", ".qml", ".md", ".sql")):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        for concept, pattern in CONCEPTS.items():
                            matches = len(re.findall(pattern, content))
                            if matches > 0:
                                results[concept] += matches
                except:
                    pass
    return results

def main():
    print("=== AUDIT RESULTS ===")
    print("Scanning Python...")
    py_res = scan_directory(PYTHON_DIR)
    print("Scanning QML...")
    qml_res = scan_directory(QML_DIR)
    print("Scanning Docs...")
    docs_res = scan_directory(DOCS_DIR)
    
    print("\n--- Summary ---")
    for concept in CONCEPTS:
        total = py_res[concept] + qml_res[concept] + docs_res[concept]
        status = "absent"
        if total > 50: status = "complete/widespread"
        elif total > 10: status = "partial"
        elif total > 0: status = "placeholder/sparse"
        
        print(f"{concept}: {total} mentions ({status})")
        
if __name__ == "__main__":
    main()
