with open('src/python/services/ap_orchestration_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        if returned_transaction_id.casefold() != transaction_id.casefold():
            raise APValidationError("The expense gateway returned an unexpected TransactionID during bill update.")
        updated_bill = self.ap_repository.update_bill(payload)'''

replacement = '''        if returned_transaction_id.casefold() != transaction_id.casefold():
            raise APValidationError("The expense gateway returned an unexpected TransactionID during bill update.")
            
        try:
            bill_pct_raw = normalized_bill.get("BillClaimPct")
            try:
                bill_pct = float(bill_pct_raw) if bill_pct_raw not in (None, "") else 0.0
            except (ValueError, TypeError):
                bill_pct = 0.0
            
            matter_id = clean_text(normalized_bill.get("MatterID") or normalized_bill.get("Matter"))
            claim_amount = (Decimal(str(normalized_bill.get("BaseTotal") or 0)) * Decimal(str(bill_pct)) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            disbursement_result = dict(self.expense_gateway.sync_supplier_disbursement({
                "APBillID": bill_id,
                "MatterID": matter_id,
                "Date": normalized_bill.get("InvoiceDate"),
                "Amount": float(claim_amount),
                "BillPct": bill_pct,
                "ClientTaxExempt": normalized_bill.get("ClientTaxExempt"),
                "Description": normalized_bill.get("DisbursementDescription") or normalized_bill.get("Vendor"),
                "Vendor": normalized_bill.get("Vendor"),
                "SupplierInvoiceRef": normalized_bill.get("VendorInvoiceNumber"),
                "SourceTransactionID": returned_transaction_id,
                "OriginalCurrency": normalized_bill.get("OriginalCurrency"),
                "OriginalAmount": normalized_bill.get("OriginalTotal"),
                "FXRate": normalized_bill.get("FXRate"),
                "BaseSubtotal": normalized_bill.get("BaseSubtotal"),
                "BaseTaxAmount": normalized_bill.get("BaseTaxAmount"),
                "CategoryName": normalized_bill.get("CategoryName"),
                "DocumentPath": normalized_bill.get("DocumentPath"),
            }) or {})
            
            if disbursement_result.get("action") == "deleted":
                payload["DisbursementID"] = ""
            elif disbursement_result.get("action") in ("created", "updated") and disbursement_result.get("disbursementId"):
                payload["DisbursementID"] = clean_text(disbursement_result.get("disbursementId"))

        except Exception as exc:
            raise APValidationError(f"The supplier bill was updated, but syncing its client disbursement failed: {exc}") from exc

        updated_bill = self.ap_repository.update_bill(payload)'''

if target in content:
    with open('src/python/services/ap_orchestration_service.py', 'w', encoding='utf-8') as f:
        f.write(content.replace(target, replacement))
    print('Replaced successfully')
else:
    print('Target not found')
