# Transactions Master UI Behavior Spec (Draft V1)

## UX Direction
Use one adaptive master form with conditional sections.

- Keep one data model (`tblTransactionsMaster`).
- Change visible/required fields by `Class` and `Type`.
- Keep user workflow fast by presets and smart defaults.

## Form Sections
1. Core: `TxnDate`, `Class`, `BusinessUnit`, `Type`, `FromAccount`, `ToAccount`, `Payee`, `Category`, `Member`.
2. Financial: `Amount`, `TaxAmount`, `TaxFlag`, `HSTExempt`, `Status`, `Shadow`.
3. Billable Context: `GeneralOfficeExpense`, `Parent`, `Client`, `Matter`, `BillClaimPct`, `TotalClaimAmount`.
4. References: `InvoiceRef`, `ExpenseDetails`, `Notes`.

## Visibility and Requirement Matrix
| Field | Income | Expense | Debt Repayment | Transfer |
|---|---|---|---|---|
| `FromAccount` | Required | Required | Required | Required |
| `ToAccount` | Hidden/Optional | Hidden/Optional | Required | Required |
| `Payee` | Required | Required | Required | Optional |
| `GeneralOfficeExpense` | Hidden | Visible | Hidden | Hidden |
| `Parent/Client/Matter` | Optional | Conditional | Hidden | Hidden |
| `BillClaimPct` | Hidden | Conditional | Hidden | Hidden |
| `TotalClaimAmount` | Hidden | Conditional | Hidden | Hidden |
| `TaxFlag`, `HSTExempt` | Visible | Visible | Visible | Visible |

## Conditional Rules
- `BusinessUnit` required when `Class=Business`.
- `ToAccount` required when `Type in (Transfer, Debt Repayment)`.
- `FromAccount` must not equal `ToAccount` when `ToAccount` is required.
- `HSTExempt=true` sets `TaxAmount=0.00` unless user explicitly overrides.
- If `GeneralOfficeExpense=true`, clear and disable `Parent`, `Client`, `Matter`, `BillClaimPct`, `TotalClaimAmount`.
- If any of `Parent`, `Client`, `Matter` is set on an `Expense`, enable billable controls.
- `TotalClaimAmount = round((Amount + TaxAmount) * (BillClaimPct / 100), 2)`.
- `Status=Void` requires `VoidReason` and locks financial fields.
- `Status=Cleared` auto-populates `ClearedAt` if blank.
- `Status=Reconciled` auto-populates `ClearedAt` and `ReconciledAt` if blank.

## On-Change Event Behavior
| Event | Action |
|---|---|
| `Class` changed | Toggle `BusinessUnit` required state. |
| `Type` changed | Recompute field visibility and required flags. |
| `GeneralOfficeExpense` changed | Toggle billable context block and clear incompatible values. |
| `HSTExempt` changed | Set `TaxAmount=0.00` when checked. |
| `Amount` / `TaxAmount` / `BillClaimPct` changed | Recalculate `TotalClaimAmount`. |
| `Status` changed | Apply date and lock rules for `Void/Cleared/Reconciled`. |
| `FromAccount` / `ToAccount` changed | Validate account pairing rules. |

## Preset Buttons (Recommended)
1. `Family Expense`: `Class=Family`, `Type=Expense`, `Member=Joint`, `TaxFlag=None`.
2. `Business Expense`: `Class=Business`, `Type=Expense`, `TaxFlag=HST - Biz`.
3. `Client Disbursement`: `Class=Business`, `Type=Expense`, `GeneralOfficeExpense=false`, `BillClaimPct=100`.
4. `Income Receipt`: `Type=Income`, `TaxFlag=None`.
5. `Transfer`: `Type=Transfer`, show account-to-account layout.
6. `Debt Payment`: `Type=Debt Repayment`, enforce debt destination account.

## Data Quality Guardrails
- Autocomplete for `Payee`, `Parent`, `Client`, `Matter`.
- Categories filtered by `Type` and optionally `Class`.
- Hard warning on `Amount <= 0`.
- Soft warning when `Status=Reconciled` without `InvoiceRef` on business expense.
- Soft warning when business entries lack `BusinessUnit`.

## Explicit Exclusions
- No `Harvest Dockets` action in this form.
- No `Sub-Client` field.
