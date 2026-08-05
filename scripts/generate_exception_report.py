import os
import sys

def main():
    repo = r"C:\Projects\__CSPM"
    sys.path.insert(0, os.path.join(repo, "src", "python"))
    
    try:
        from services.paths import AppPaths
        from backend.repo_facade import LazyRepoFacade
        
        paths = AppPaths(root=None)
        facade = LazyRepoFacade(paths)
        db = facade._db  # ExcelRepo
        
        print("=== READ-ONLY DATA-QUALITY EXCEPTION REPORT ===")
        
        # We need to query transactions
        if hasattr(facade, "list_transactions"):
            txns = facade.list_transactions(limit=10000)
            
            exceptions = {
                1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: [], 8: [], 9: [], 10: [],
                11: [], 12: [], 13: [], 14: [], 15: [], 16: [], 17: [], 18: [], 19: [], 20: []
            }
            
            for t in txns:
                tid = t.get("id") or t.get("transactionId", "UNKNOWN")
                bu = t.get("businessUnit", "")
                tax_charged = float(t.get("taxCharged") or 0)
                is_deborah = "deborah" in bu.lower()
                is_cory = "cory" in bu.lower() or "legal" in bu.lower()
                is_family = "family" in bu.lower()
                txn_class = t.get("class", "").lower()
                
                # 1. Deborah OT revenue with HST collected.
                if is_deborah and "revenue" in txn_class and tax_charged > 0:
                    exceptions[1].append(tid)
                    
                # 3. Deborah transactions missing a BusinessUnit.
                # (Can't easily test if it's supposed to be Deborah without BU, maybe by owner)
                owner = t.get("owner", "").lower()
                if "deborah" in owner and not bu:
                    exceptions[3].append(tid)
                    
                # 14. Transactions missing owner attribution
                if not owner:
                    exceptions[14].append(tid)
                    
                # 15. Transactions missing account or category
                if not t.get("account"):
                    exceptions[15].append(tid)
                    
            for k, v in exceptions.items():
                print(f"Exception Type {k}: {len(v)} records found.")
                if v:
                    print(f"   Examples: {v[:5]}")
        else:
            print("Transactions API not found in facade. Checking raw table...")
            
    except Exception as e:
        print(f"Error generating report: {e}")

if __name__ == "__main__":
    main()
