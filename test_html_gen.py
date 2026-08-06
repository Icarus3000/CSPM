import sys
import os
sys.path.insert(0, r"C:\Projects\__CSPM\src\python")
sys.path.insert(0, r"C:\Projects\__CSPM\src\python\backend\controllers")

from backend.controllers.billing_controller import BillingController

# We need a dummy backend context to instantiate BillingController
class DummyApp:
    pass

class DummyRepo:
    def __init__(self):
        pass

try:
    from repositories.excel_repo import ExcelRepo
    repo = ExcelRepo()
    ctrl = BillingController(repo, None)
    
    draft_num = "BORKOWSKYJ-20260805-099E-D"
    print(f"Building payload for {draft_num}...")
    payload = ctrl._build_invoice_payload(draft_num)
    print("Payload built successfully! Keys:", list(payload.keys()))
    
    print("Generating HTML...")
    html = ctrl._generate_preview_impl(draft_num, "Concept_A2")
    if html:
        print("HTML generated successfully! Length:", len(html))
    else:
        print("HTML generation returned empty or None.")
        
except Exception as e:
    import traceback
    traceback.print_exc()
