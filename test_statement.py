import sys
import os
sys.path.append(os.path.abspath(r"c:\Projects\__CSPM\src\python"))
from repositories.excel_repo import ExcelRepo
from backend.settings_manager import SettingsManager

settings = SettingsManager(r"c:\Projects\__CSPM\data\settings.json")
repo = ExcelRepo(settings)
print("Testing AR Aging...")
res1 = repo.ar_aging_report({"excludedInvoices": []})
print("AR Aging OK:", res1.get("ok"), len(res1.get("rows", [])))

print("Testing Statement of Account...")
res2 = repo.statement_of_account_report({"client": "LIHDC Professional Corporation", "client_level": "billing"})
print("Statement OK:", res2.get("ok"), len(res2.get("sections", [])[0].get("rows", [])))
print(res2.get("cards"))
