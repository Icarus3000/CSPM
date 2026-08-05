# AP Workbook Schema Proposal

## Authority

APBills is authoritative for supplier obligations. APPayments is authoritative for outgoing payment applications and reversals. Transactions Master remains authoritative for expense and cash-account events. Disbursements remains authoritative for client billing projections.

## APBills columns

- APBillID
- Vendor
- VendorInvoiceNumber
- InvoiceDate
- DueDate
- Subtotal
- TaxAmount
- Total
- AmountPaid
- Balance
- Status
- Currency
- ExpenseTransactionID
- DuplicateKey
- Notes
- CreatedAt
- UpdatedAt

## APPayments columns

- APPaymentID
- APBillID
- PaymentDate
- Amount
- FromAccount
- Method
- Reference
- Status
- ReversalOfPaymentID
- ReversalReason
- Notes
- CreatedAt
- UpdatedAt

## Validation result

The proposed tables were added to a disposable copy of data/CSPM.xlsm and the partial-payment fixture round-tripped exactly. The live workbook was not modified.
