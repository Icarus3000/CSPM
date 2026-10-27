# CSPM & Quick Expense Mini-App — Workstation Failover & Disaster Recovery Guide

If **`OFFICENEW`** ever breaks, loses power, or is unavailable, **zero data is lost** and you can switch **`OMNIBOOK`** (or any replacement computer) to be the active host in **under 2 minutes**.

---

## 1. Why Zero Data Is Ever Lost

Every piece of data in CSPM and the Quick Expense Mini-App lives outside of `OFFICENEW`'s local-only storage:

| Data Layer | Canonical Location | Automatic Backup / Sync Mechanism |
| :--- | :--- | :--- |
| **CSPM SQLite Database (`cspm.db`)** | `OneDrive - LPN\CSPM_Shared_Data\cspm.db` | Continuously synced to Microsoft OneDrive Cloud & `OMNIBOOK` |
| **CSPM Master Workbook (`CSPM.xlsm`)** | `OneDrive - LPN\CSPM_Shared_Data\CSPM.xlsm` | Continuously synced to Microsoft OneDrive Cloud & `OMNIBOOK` |
| **Quick Expense Instant Sync Queue (`inbox.json`)** | `OneDrive - LPN\CSPM_Shared_Data\QuickExpense_Sync\inbox.json` | Every phone/Chromebook expense, income, transfer, and receipt metadata entry is written here in `<25ms` and synced by OneDrive |
| **Tax-Ready Receipt Photos & PDFs (`Receipts/`)** | `OneDrive - LPN\CSPM_Shared_Data\Receipts\<Year>\...` | Every receipt photo/PDF snapped on Cory's or Deborah's phone is filed into organized tax folders in OneDrive |
| **Legacy Dockets & Invoices (`Dockets.xlsm` & PDFs)** | `OneDrive - LPN\__Invoices (1)\Dockets.xlsm` | Continuously synced to Microsoft OneDrive Cloud & `OMNIBOOK` |
| **All Application Code, Tax Engine & Scripts** | GitHub (`__CSPM` repository) + `OneDrive - LPN\__Admin\Antigravity_Customizations\` | Pushed to GitHub cloud and mirrored on `OMNIBOOK` |

---

## 2. Scenario A: Instant Failover to `OMNIBOOK` (Takes ~60 Seconds)

If `OFFICENEW` goes down and you want `OMNIBOOK` to take over immediately:

1. Open **PowerShell** or **Terminal** on `OMNIBOOK` in the `__CSPM` folder and run:
   ```powershell
   git pull
   python scripts/setup_workstation_failover.py --activate
   ```
2. That single command automatically:
   - Verifies that `cspm.db`, `CSPM.xlsm`, `Dockets.xlsm`, `Receipts/`, and `QuickExpense_Sync/inbox.json` are present in `OneDrive - LPN`.
   - Installs the 100% headless Windows Startup launcher and 5-minute background watchdog (`pythonw.exe` — zero console popups).
   - Starts the Quick Expense Server on port `24820`.
   - Runs `tailscale serve --bg 24820` and prints your active Tailscale HTTPS link (e.g. `https://omnibook.tail38e9b9.ts.net`).
3. **Optional — Keep the Exact Same Phone Bookmark (`https://officenew.tail38e9b9.ts.net`):**
   - If you don't even want to change the bookmark on Deborah's or Cory's phone, open the [Tailscale Admin Console (Machines)](https://login.tailscale.com/admin/machines), click the `...` menu next to `omnibook`, and rename the machine to `officenew` (or open the `https://omnibook.tail38e9b9.ts.net` link once).

---

## 3. Scenario B: Setting Up a Brand-New Replacement Computer From Scratch

If `OFFICENEW` is permanently replaced by a brand-new Windows PC:

1. **Sign into OneDrive (`OneDrive - LPN`):**
   - Sign into Windows OneDrive with your LPN account so `C:\Users\<username>\OneDrive - LPN\CSPM_Shared_Data` and `C:\Users\<username>\OneDrive - LPN\__Invoices (1)` sync down.
   - Right-click `CSPM_Shared_Data` and `__Invoices (1)` in File Explorer and select **"Always keep on this device"** so the files are always available locally without cloud-fetch delay.
2. **Install Python 3.11+, Git, and Tailscale:**
   - Install Tailscale and sign into your tailnet (`tail38e9b9.ts.net`). In the Tailscale Admin Console, name the computer `officenew` so all existing phone/Chromebook home-screen icons (`https://officenew.tail38e9b9.ts.net`) work immediately with zero changes.
3. **Clone the Repository & Run the 1-Command Failover Script:**
   ```powershell
   git clone <your-github-repo-url> C:\Projects\__CSPM
   cd C:\Projects\__CSPM
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   .\.venv\Scripts\python.exe scripts/setup_workstation_failover.py --activate
   ```
4. **Restore Antigravity Global Skills & Rules (1 Command):**
   ```powershell
   python "$HOME\OneDrive - LPN\__Admin\Antigravity_Customizations\install.py"
   ```
5. Everything—desktop CSPM, mobile Quick Expense, Receipt OCR, Voice Commands, Docketing, Mobile Invoicing, and Tax/HST/Shareholder Loan tracking—is now 100% live on the new machine.
