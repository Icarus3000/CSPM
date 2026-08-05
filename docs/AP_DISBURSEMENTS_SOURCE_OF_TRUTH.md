# AP and Disbursements Source-of-Truth Contract

## Immediate decision

Transactions Master remains the authoritative current record for an expense entered through the existing AP surface. Disbursements remains the client-billing projection for a client or matter-linked recoverable cost.

An AP bill and every AP payment require immutable stable IDs. Status and balance are derived from bill total and non-reversed payments. Posted records are corrected through reversal, not destructive deletion.

## This pass

This pass adds a pure workbook-independent lifecycle foundation covering Decimal money, Draft/Unpaid/Partially Paid/Paid/Voided/Reversed states, balances, partial payments, reversal exclusion, overpayment prevention, void restrictions, stable payment IDs, and duplicate vendor-invoice keys.

## Not yet included

No workbook schema, controller, QML, WIP, invoice, ledger, receivable, or live data change is made.

## Next pass

Map the rules onto temporary workbook copies and prove exact persistence before connecting the live AP controller or UI.
