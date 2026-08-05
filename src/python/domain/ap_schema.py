from __future__ import annotations

# CSPM_AP_GOVERNED_SCHEMA_V1
AP_BILLS_SHEET = "APBills"
AP_BILLS_TABLE = "tblAPBills"
AP_BILLS_HEADERS = ("APBillID", "Vendor", "VendorInvoiceNumber", "InvoiceDate", "DueDate", "Subtotal", "TaxAmount", "Total", "AmountPaid", "Balance", "Status", "Currency", "ExpenseTransactionID", "DuplicateKey", "Notes", "CreatedAt", "UpdatedAt", "ExpenseTreatment", "CategoryCode", "CategoryName", "SourceAccount")
AP_PAYMENTS_SHEET = "APPayments"
AP_PAYMENTS_TABLE = "tblAPPayments"
AP_PAYMENTS_HEADERS = ("APPaymentID", "APBillID", "PaymentDate", "Amount", "FromAccount", "Method", "Reference", "Status", "ReversalOfPaymentID", "ReversalReason", "Notes", "CreatedAt", "UpdatedAt")
AP_REQUIRED_TABLES = {
    AP_BILLS_TABLE: {"sheet": AP_BILLS_SHEET, "headers": AP_BILLS_HEADERS, "authority": "supplier_obligation"},
    AP_PAYMENTS_TABLE: {"sheet": AP_PAYMENTS_SHEET, "headers": AP_PAYMENTS_HEADERS, "authority": "outgoing_payment_application"},
}
