# Financial Metrics Logic: Revenue vs Production

**Context:**
When migrating financial tracking from the Excel workbook (raw Dockets + Ledger) to the new Python application, we must fix a mathematical flaw in the old Excel dashboard's logic regarding how Production and Revenue are compared.

### The Old Flaw (Do Not Replicate)
In the old Excel system, "Total Production" was calculated strictly as a raw sum of the Docket values (`Hours × Rate`), while "Revenue" was calculated from the actual Ledger. Because the Excel formula was blind to the Ledger, it failed to account for invoice mark-ups or write-downs. This caused a confusing state where Production could sometimes appear artificially higher than Revenue.

### The New Financial Logic (To Be Implemented)
When calculating these metrics in the new system, the following definitions MUST be used:

1. **Unbilled Production (WIP):** 
   - Calculated normally using the docketed values (`Hours × Rate`).
2. **Billed Production:** 
   - Do NOT use the raw docketed values. Instead, Production for billed items must be adjusted to match the actual collected amount from the Ledger. This correctly absorbs any mark-ups (flat-fees) or write-downs (discounts) into the Production metric itself.
3. **Revenue + WIP:** 
   - Calculated as all collected Revenue (which naturally includes any previous year's WIP that was billed in the current year) PLUS the current year's WIP.

### The Mathematical Outcome
By strictly adhering to this logic, **`Revenue + WIP` must always be strictly greater than or equal to `Production`.** The only mathematical difference between the two should equal the value of any previous year's WIP that was successfully billed in the current year. 
