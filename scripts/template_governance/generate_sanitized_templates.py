import os
import shutil
import zipfile
import hashlib
from tempfile import NamedTemporaryFile
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter

def neutralize_props(wb):
    wb.properties.creator = "System"
    wb.properties.lastModifiedBy = "System"
    wb.properties.title = ""
    wb.properties.subject = ""

def convert_to_xlsm(xlsx_path, xlsm_path):
    with NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name

    with zipfile.ZipFile(xlsx_path, 'r') as zin:
        with zipfile.ZipFile(temp_path, 'w') as zout:
            for item in zin.infolist():
                content = zin.read(item.filename)
                if item.filename == '[Content_Types].xml':
                    content = content.replace(
                        b'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
                        b'application/vnd.ms-excel.sheet.macroEnabled.main+xml'
                    )
                zout.writestr(item, content)

    shutil.move(temp_path, xlsm_path)
    os.remove(xlsx_path)

def create_cspm_workbook(path):
    wb = Workbook()
    wb.remove(wb.active) # Remove default sheet
    neutralize_props(wb)

    tables_spec = [
        ("Parents", "tblParents", ["ParentID", "ParentName", "DefaultSharePct", "DefaultClientRate", "Active", "Notes"]),
        ("Clients", "tblClients", ["ClientID", "ClientName", "Email", "Phone", "Status", "Active", "Notes"]),
        ("ClientProfiles", "tblClientProfiles", ["ClientID", "LegalName", "DisplayName", "FirstName", "MiddleName", "LastName", "EntityType", "PrincipalName", "PrincipalPosition", "PrimaryEmail", "PrimaryPhone", "SecondaryContactName", "SecondaryContactPosition", "SecondaryContactEmail", "SecondaryContactPhone", "AddressLine1", "AddressLine2", "City", "StateProvince", "PostalCode", "Country", "FullAddress", "ParentClientID", "ParentClientName", "Website", "TaxID", "Industry", "BillingEmail", "KYCStatus", "OnboardingStatus", "RetainerRequired", "RetainerAmount", "EngagementStartDate", "DateClientAdded", "Birthday", "ReferralFrom", "ConflictNotes", "Notes", "CreatedAt", "UpdatedAt"]),
        ("Matters", "tblMatters", ["MatterID", "MatterNumber", "MatterName", "DisplayName", "ClientID", "ClientName", "ParentID", "ParentName", "MatterType", "PracticeArea", "Status", "ResponsibleLawyer", "BillingArrangement", "BillingContact", "BillingEmail", "DefaultRate", "DefaultSharePct", "RateHistory", "DateOfEngagement", "DateOpened", "DateClosed", "CourtFileNumber", "OpposingParty", "ReferralFrom", "Description", "Notes", "CreatedAt", "UpdatedAt"]),
        ("TimeEntries", "tblTimeEntries", ["EntryID", "Date", "ClientID", "MatterID", "ParentID", "Description", "Hours", "ClientRate", "SharePct", "GrossToClient", "AmountToYou", "HST", "TotalInclHST", "RawSeconds", "Status", "InvoiceRef", "InvoiceStatus", "PaymentStatus", "InvoiceTotal", "InvoiceAmountPaid", "InvoiceBalanceDue", "InvoiceDate", "LockAudit", "CreatedAt"]),
        ("Trademarks", "tblTrademarks", ["TrademarkID", "Jurisdiction", "JurisdictionOther", "ClientName", "MatterNumber", "InternalNotesNextStrategy", "TrademarkText", "MarkType", "DesignRepresentation", "DesignImagePaste", "ColorClaimed", "ColorDescription", "NiceClasses", "GoodsServicesDescription", "ForeignPriorityClaim", "RegistryLink", "ApplicationNumber", "RegistrationNumber", "CurrentStatus", "ApplicantNameAddress", "FilingDate", "RegistrationDate", "RenewalDeadline", "CIPOStatus", "TM5Status", "ExaminersReportDate", "OfficeActionResponseDeadline", "ApprovalDate", "AdvertisementDate", "AdvertisementVolIssue", "OppositionDeadline", "AllowanceDate", "RegisterType", "USPTOStatusIndicator", "OwnerNameAddress", "AttorneyOfRecord", "PublicationDate", "NoticeOfAllowanceDate", "SOUDeadline", "SOUExtensionTracking", "Section8Deadline", "Section15Deadline", "Section9Deadline", "LocalForeignAssociate", "ApplicationReferenceNumber", "PublicationAdvertisementDate", "OppositionPeriodEndDate", "UpcomingLocalDeadlineOfficeActionDate", "CreatedAt", "UpdatedAt"]),
        ("Transactions", "tblTransactionsMaster", ["TransactionID", "TxnDate", "Class", "BusinessUnit", "Type", "FromAccount", "ToAccount", "Payee", "Parent", "Client", "Matter", "CategoryCode", "CategoryName", "Member", "Amount", "TaxAmount", "TaxFlag", "HSTExempt", "GeneralOfficeExpense", "Shadow", "InvoiceRef", "BillClaimPct", "TotalClaimAmount", "ExpenseDetails", "Notes", "Status", "Currency", "VoidReason", "ClearedAt", "ReconciledAt", "CreatedAt", "UpdatedAt"]),
        ("TransactionAccounts", "tblTransactionAccounts", ["AccountCode", "AccountName", "AccountKind", "Owner", "Active", "AliasList"]),
        ("TransactionCategories", "tblTransactionCategories", ["CategoryCode", "CategoryName", "Type", "ClassScope", "TaxFlagDefault", "BillableAllowed", "MedicalEligible", "DeductibleEligible", "BusinessDeductibleEligible", "Active", "SortOrder", "Notes"]),
        ("TransactionBusinessUnits", "tblTransactionBusinessUnits", ["BusinessUnit", "Owner", "Active"]),
        ("TransactionPayees", "tblTransactionPayees", ["PayeeName", "DefaultCategoryCode", "Active"]),
        ("Disbursements", "tblDisbursements", ["DisbursementID", "Date", "ClientName", "SubClient", "ClientID", "ParentID", "MatterID", "Description", "Amount", "TaxExempt", "BillPct", "InvoiceRef", "PaymentStatus", "InvoiceTotal", "InvoiceAmountPaid", "InvoiceBalanceDue", "CreatedAt"]),
        ("Ledger", "tblLedger", ["LedgerID", "Date", "ClientVendor", "Description", "Category", "Reference", "BillingsExclHST", "HSTCollected", "ExpensesExclHST", "HSTPaid", "Collected", "WriteOff", "Receivable", "TrxID", "ExternalRefID", "OriginalAmount", "WorkClient", "CreatedAt"]),
        ("Receivables", "tblReceivables", ["InvoiceNum", "Date", "Client", "TotalInvoiced", "AmountPaid", "CreditsAdj", "BalanceDue", "Status", "WorkClient"]),
        ("InvoiceLog", "tblInvoiceLog", ["InvoiceNum", "ClientName", "SubClient", "InvoiceDate", "TotalFees", "TotalDisbursements", "TotalTax", "AggregateBilled", "BillToClient", "FilePath"]),
        ("HSTLog", "tblHSTLog", ["PeriodID", "PeriodStart", "PeriodEnd", "FiledDate", "ConfNum", "NetTax", "PaidDate", "PaymentRef"]),
        ("DraftInvoices", "tblDraftInvoices", ["DraftID", "InvoiceNum", "ClientID", "ClientName", "Date", "DiscountType", "DiscountValue", "TotalFees", "TotalDisbursements", "TotalTax", "TotalDue", "GroupingPref", "CreatedAt", "UpdatedAt"]),
        ("CorpEntities", "tblCorpEntities", ["EntityID", "ClientID", "LegalName", "Jurisdiction", "IncorporationDate", "IncorporationNumber", "FiscalYearEnd", "Status", "Notes", "CreatedAt"]),
        ("CorpRelationships", "tblCorpRelationships", ["RelationshipID", "SourceEntityID", "TargetEntityID", "RelationshipType", "Title", "ShareClass", "SharesHeld", "OwnershipPercentage", "StartDate", "EndDate", "Active"]),
        ("CorpTransactions", "tblCorpTransactions", ["TransactionID", "EntityID", "Date", "TransactionType", "FromEntityID", "ToEntityID", "ShareClass", "NumberOfShares", "PricePerShare", "TotalValue", "DocumentReference", "Notes", "CreatedAt"])
    ]

    for sheet_name, table_name, columns in tables_spec:
        ws = wb.create_sheet(title=sheet_name)
        ws.append(columns)
        # Empty row for table
        ws.append([None] * len(columns))

        tab = Table(displayName=table_name, ref=f"A1:{get_column_letter(len(columns))}2")
        style = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False,
                               showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        tab.tableStyleInfo = style
        ws.add_table(tab)

    xlsx_path = path.replace('.xlsm', '.xlsx')
    wb.save(xlsx_path)
    convert_to_xlsm(xlsx_path, path)

def create_dockets_workbook(path):
    wb = Workbook()
    wb.remove(wb.active)
    neutralize_props(wb)

    sheets = ["Clients", "Matters", "Dockets", "Disbursements", "Ledger", "Receivables", "Invoice Log"]

    for sheet_name in sheets:
        ws = wb.create_sheet(title=sheet_name)
        # Just generic header for each sheet
        ws.append([f"{sheet_name}Header1", f"{sheet_name}Header2"])

    xlsx_path = path.replace('.xlsm', '.xlsx')
    wb.save(xlsx_path)
    convert_to_xlsm(xlsx_path, path)

if __name__ == "__main__":
    os.makedirs(r"C:\Projects\__CSPM\src\templates", exist_ok=True)
    cspm_path = r"C:\Projects\__CSPM\src\templates\CSPM.xlsm"
    dockets_path = r"C:\Projects\__CSPM\src\templates\Dockets.xlsm"

    create_cspm_workbook(cspm_path)
    create_dockets_workbook(dockets_path)

    def get_hash(path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    cspm_hash = get_hash(cspm_path)
    dockets_hash = get_hash(dockets_path)
    
    cspm_size = os.path.getsize(cspm_path)
    dockets_size = os.path.getsize(dockets_path)

    print("Verification Summary:")
    print(f"CSPM.xlsm created: {cspm_path}")
    print(f"  Size: {cspm_size} bytes")
    print(f"  SHA-256: {cspm_hash}")
    
    print(f"Dockets.xlsm created: {dockets_path}")
    print(f"  Size: {dockets_size} bytes")
    print(f"  SHA-256: {dockets_hash}")
