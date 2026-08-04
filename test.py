import sys
sys.path.append('src/python')
try:
    from backend.controllers.billing_controller import BillingController
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
