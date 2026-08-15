from typing import Dict, List

# =============================================================================
# TABLE & SHEET NAMES
# =============================================================================
TBL_PARENTS = "tblParents"
TBL_CLIENTS = "tblClients"
TBL_CLIENT_PROFILES = "tblClientProfiles"
TBL_MATTERS = "tblMatters"
TBL_MATTER_PARTIES = "tblMatterParties"
TBL_TIME = "tblTimeEntries"
TBL_TRADEMARKS = "tblTrademarks"
TBL_TRANSACTIONS_MASTER = "tblTransactionsMaster"
TBL_TRANSACTION_ACCOUNTS = "tblTransactionAccounts"
TBL_TRANSACTION_CATEGORIES = "tblTransactionCategories"
TBL_TRANSACTION_BUSINESS_UNITS = "tblTransactionBusinessUnits"
TBL_TRANSACTION_PAYEES = "tblTransactionPayees"
TBL_DISBURSEMENTS = "tblDisbursements"
TBL_LEDGER = "tblLedger"
TBL_RECEIVABLES = "tblReceivables"
TBL_INVOICE_LOG = "tblInvoiceLog"
TBL_HST_LOG = "tblHSTLog"
TBL_DRAFT_INVOICES = "tblDraftInvoices"

# Corporate Entities
TBL_CORP_ENTITIES = "tblCorpEntities"
TBL_CORP_RELATIONSHIPS = "tblCorpRelationships"
TBL_CORP_TRANSACTIONS = "tblCorpTransactions"

SHEET_PARENTS = "Parents"
SHEET_CLIENTS = "Clients"
SHEET_CLIENT_PROFILES = "ClientProfiles"
SHEET_MATTERS = "Matters"
SHEET_MATTER_PARTIES = "MatterParties"
SHEET_TIME = "TimeEntries"
SHEET_TRADEMARKS = "Trademarks"
SHEET_TRANSACTIONS = "Transactions"
SHEET_TRANSACTION_ACCOUNTS = "TransactionAccounts"
SHEET_TRANSACTION_CATEGORIES = "TransactionCategories"
SHEET_TRANSACTION_BUSINESS_UNITS = "TransactionBusinessUnits"
SHEET_TRANSACTION_PAYEES = "TransactionPayees"
# Legacy pre-refactor shared lookup sheet (kept for migration support).
SHEET_TRANSACTION_LOOKUPS = "TransactionLookups"
SHEET_DISBURSEMENTS = "Disbursements"
SHEET_LEDGER = "Ledger"
SHEET_RECEIVABLES = "Receivables"
SHEET_INVOICE_LOG = "InvoiceLog"
SHEET_HST_LOG = "HSTLog"
SHEET_DRAFT_INVOICES = "DraftInvoices"
SHEET_CORP_ENTITIES = "CorpEntities"
SHEET_CORP_RELATIONSHIPS = "CorpRelationships"
SHEET_CORP_TRANSACTIONS = "CorpTransactions"

# =============================================================================
# COLUMN HEADERS
# =============================================================================

# Parents
COL_PARENT_ID = "ParentID"
COL_PARENT_NAME = "ParentName"
COL_PARENT_DEF_SHARE = "DefaultSharePct"
COL_PARENT_DEF_RATE = "DefaultClientRate"
COL_PARENT_ACTIVE = "Active"
COL_PARENT_NOTES = "Notes"

# Clients
COL_CLIENT_ID = "ClientID"
COL_CLIENT_NAME = "ClientName"
COL_CLIENT_EMAIL = "Email"
COL_CLIENT_PHONE = "Phone"
COL_CLIENT_STATUS = "Status"
COL_CLIENT_ACTIVE = "Active"
COL_CLIENT_NOTES = "Notes"

# Client Profiles
COL_PROFILE_CLIENT_ID = "ClientID"
COL_PROFILE_LEGAL_NAME = "LegalName"
COL_PROFILE_DISPLAY_NAME = "DisplayName"
COL_PROFILE_FIRST_NAME = "FirstName"
COL_PROFILE_MIDDLE_NAME = "MiddleName"
COL_PROFILE_LAST_NAME = "LastName"
COL_PROFILE_ENTITY_TYPE = "EntityType"
COL_PROFILE_PRINCIPAL_NAME = "PrincipalName"
COL_PROFILE_PRINCIPAL_POSITION = "PrincipalPosition"
COL_PROFILE_PRIMARY_EMAIL = "PrimaryEmail"
COL_PROFILE_PRIMARY_PHONE = "PrimaryPhone"
COL_PROFILE_SECONDARY_CONTACT = "SecondaryContactName"
COL_PROFILE_SECONDARY_POSITION = "SecondaryContactPosition"
COL_PROFILE_SECONDARY_EMAIL = "SecondaryContactEmail"
COL_PROFILE_SECONDARY_PHONE = "SecondaryContactPhone"
COL_PROFILE_ADDR1 = "AddressLine1"
COL_PROFILE_ADDR2 = "AddressLine2"
COL_PROFILE_CITY = "City"
COL_PROFILE_STATE = "StateProvince"
COL_PROFILE_POSTAL = "PostalCode"
COL_PROFILE_COUNTRY = "Country"
COL_PROFILE_FULL_ADDRESS = "FullAddress"
COL_PROFILE_PARENT_ID = "ParentClientID"
COL_PROFILE_PARENT_NAME = "ParentClientName"
COL_PROFILE_WEBSITE = "Website"
COL_PROFILE_TAX_ID = "TaxID"
COL_PROFILE_INDUSTRY = "Industry"
COL_PROFILE_BILLING_EMAIL = "BillingEmail"
COL_PROFILE_KYC_STATUS = "KYCStatus"
COL_PROFILE_ONBOARDING_STATUS = "OnboardingStatus"
COL_PROFILE_RETAINER_REQUIRED = "RetainerRequired"
COL_PROFILE_RETAINER_AMOUNT = "RetainerAmount"
COL_PROFILE_ENGAGEMENT_START = "EngagementStartDate"
COL_PROFILE_DATE_CLIENT_ADDED = "DateClientAdded"
COL_PROFILE_BIRTHDAY = "Birthday"
COL_PROFILE_REFERRAL_FROM = "ReferralFrom"
COL_PROFILE_CONFLICT_NOTES = "ConflictNotes"
COL_PROFILE_NOTES = "Notes"
COL_PROFILE_CREATED = "CreatedAt"
COL_PROFILE_UPDATED = "UpdatedAt"

# Matters
COL_MATTER_ID = "MatterID"
COL_MATTER_NUMBER = "MatterNumber"
COL_MATTER_CLIENT_ID = "ClientID"
COL_MATTER_NAME = "MatterName"
COL_MATTER_DISPLAY_NAME = "DisplayName"
COL_MATTER_CLIENT_NAME = "ClientName"
COL_MATTER_PARENT_ID = "ParentID"
COL_MATTER_PARENT_NAME = "ParentName"
COL_MATTER_TYPE = "MatterType"
COL_MATTER_PRACTICE_AREA = "PracticeArea"
COL_MATTER_DEF_RATE = "DefaultRate"
COL_MATTER_DEF_SHARE = "DefaultSharePct"
COL_MATTER_RATE_HISTORY = "RateHistory"
COL_MATTER_RESPONSIBLE_LAWYER = "ResponsibleLawyer"
COL_MATTER_BILLING_ARRANGEMENT = "BillingArrangement"
COL_MATTER_BILLING_CONTACT = "BillingContact"
COL_MATTER_BILLING_EMAIL = "BillingEmail"
COL_MATTER_ENGAGEMENT_DATE = "DateOfEngagement"
COL_MATTER_OPEN_DATE = "DateOpened"
COL_MATTER_CLOSE_DATE = "DateClosed"
COL_MATTER_COURT_FILE_NO = "CourtFileNumber"
COL_MATTER_OPPOSING_PARTY = "OpposingParty"
COL_MATTER_REFERRAL_FROM = "ReferralFrom"
COL_MATTER_DESCRIPTION = "Description"
COL_MATTER_STATUS = "Status"
COL_MATTER_NOTES = "Notes"
COL_MATTER_CREATED = "CreatedAt"
COL_MATTER_UPDATED = "UpdatedAt"
COL_MATTER_REPRESENTATION_MODE = "RepresentationMode"
COL_MATTER_JOINT_NO_CONFIDENTIALITY_CONFIRMED = "JointNoConfidentialityConfirmed"
COL_MATTER_JOINT_INSTRUCTIONS_REQUIRE_ALL = "JointInstructionsRequireAll"
COL_MATTER_JOINT_ENGAGEMENT_DOCUMENT = "JointEngagementDocument"

# Matter Parties
# A matter retains its legacy ClientID as its file anchor for historical time
# and billing workflows.  Every represented client is recorded here instead
# of creating artificial parent-client or household links.
COL_MATTER_PARTY_ID = "MatterPartyID"
COL_MATTER_PARTY_MATTER_ID = "MatterID"
COL_MATTER_PARTY_CLIENT_ID = "ClientID"
COL_MATTER_PARTY_CLIENT_NAME = "ClientName"
COL_MATTER_PARTY_ROLE = "Role"
COL_MATTER_PARTY_IS_FILE_ANCHOR = "IsFileAnchor"
COL_MATTER_PARTY_IS_BILLING_RECIPIENT = "IsBillingRecipient"
COL_MATTER_PARTY_SORT_ORDER = "SortOrder"
COL_MATTER_PARTY_NOTES = "Notes"
COL_MATTER_PARTY_CREATED = "CreatedAt"
COL_MATTER_PARTY_UPDATED = "UpdatedAt"

# Time Entries
COL_TIME_ENTRY_ID = "EntryID"
COL_TIME_DATE = "Date"
COL_TIME_CLIENT_ID = "ClientID"
COL_TIME_MATTER_ID = "MatterID"
COL_TIME_PARENT_ID = "ParentID"
COL_TIME_DESC = "Description"
COL_TIME_HOURS = "Hours"
COL_TIME_RATE = "ClientRate"
COL_TIME_SHARE_PCT = "SharePct"
COL_TIME_GROSS = "GrossToClient"
COL_TIME_NET = "AmountToYou"
COL_TIME_HST = "HST"
COL_TIME_TOTAL = "TotalInclHST"
COL_TIME_SECONDS = "RawSeconds"
COL_TIME_STATUS = "Status"
COL_TIME_INVOICE_REF = "InvoiceRef"
COL_TIME_INVOICE_STATUS = "InvoiceStatus"
COL_TIME_PAYMENT_STATUS = "PaymentStatus"
COL_TIME_INVOICE_TOTAL = "InvoiceTotal"
COL_TIME_INVOICE_AMOUNT_PAID = "InvoiceAmountPaid"
COL_TIME_INVOICE_BALANCE_DUE = "InvoiceBalanceDue"
COL_TIME_INVOICE_DATE = "InvoiceDate"
# A hidden operational reservation used only while an erroneous unpaid invoice
# is being corrected and reissued with its original number.
COL_TIME_REISSUE_INVOICE_NUM = "ReissueInvoiceNum"
COL_TIME_LOCK_AUDIT = "LockAudit"
COL_TIME_CREATED = "CreatedAt"

# Trademarks
COL_TM_ID = "TrademarkID"
COL_TM_JURISDICTION = "Jurisdiction"
COL_TM_JURISDICTION_OTHER = "JurisdictionOther"
COL_TM_CLIENT_NAME = "ClientName"
COL_TM_MATTER_NUMBER = "MatterNumber"
COL_TM_INTERNAL_NOTES = "InternalNotesNextStrategy"
COL_TM_TRADEMARK_TEXT = "TrademarkText"
COL_TM_MARK_TYPE = "MarkType"
COL_TM_DESIGN_REPRESENTATION = "DesignRepresentation"
COL_TM_DESIGN_IMAGE_PASTE = "DesignImagePaste"
COL_TM_COLOR_CLAIMED = "ColorClaimed"
COL_TM_COLOR_DESCRIPTION = "ColorDescription"
COL_TM_NICE_CLASSES = "NiceClasses"
COL_TM_GOODS_SERVICES = "GoodsServicesDescription"
COL_TM_FOREIGN_PRIORITY = "ForeignPriorityClaim"
COL_TM_REGISTRY_LINK = "RegistryLink"
COL_TM_APPLICATION_NO = "ApplicationNumber"
COL_TM_REGISTRATION_NO = "RegistrationNumber"
COL_TM_CURRENT_STATUS = "CurrentStatus"
COL_TM_APPLICANT_NAME_ADDRESS = "ApplicantNameAddress"
COL_TM_FILING_DATE = "FilingDate"
COL_TM_REGISTRATION_DATE = "RegistrationDate"
COL_TM_RENEWAL_DEADLINE = "RenewalDeadline"
COL_TM_CIPO_STATUS = "CIPOStatus"
COL_TM_TM5_STATUS = "TM5Status"
COL_TM_EXAMINERS_REPORT_DATE = "ExaminersReportDate"
COL_TM_OFFICE_ACTION_RESPONSE_DEADLINE = "OfficeActionResponseDeadline"
COL_TM_APPROVAL_DATE = "ApprovalDate"
COL_TM_ADVERTISEMENT_DATE = "AdvertisementDate"
COL_TM_ADVERTISEMENT_VOL_ISSUE = "AdvertisementVolIssue"
COL_TM_OPPOSITION_DEADLINE = "OppositionDeadline"
COL_TM_ALLOWANCE_DATE = "AllowanceDate"
COL_TM_REGISTER_TYPE = "RegisterType"
COL_TM_USPTO_STATUS_INDICATOR = "USPTOStatusIndicator"
COL_TM_OWNER_NAME_ADDRESS = "OwnerNameAddress"
COL_TM_ATTORNEY_OF_RECORD = "AttorneyOfRecord"
COL_TM_PUBLICATION_DATE = "PublicationDate"
COL_TM_NOTICE_OF_ALLOWANCE_DATE = "NoticeOfAllowanceDate"
COL_TM_SOU_DEADLINE = "SOUDeadline"
COL_TM_SOU_EXTENSION_TRACKING = "SOUExtensionTracking"
COL_TM_SECTION8_DEADLINE = "Section8Deadline"
COL_TM_SECTION15_DEADLINE = "Section15Deadline"
COL_TM_SECTION9_DEADLINE = "Section9Deadline"
COL_TM_LOCAL_FOREIGN_ASSOCIATE = "LocalForeignAssociate"
COL_TM_APPLICATION_REFERENCE_NO = "ApplicationReferenceNumber"
COL_TM_PUBLICATION_ADVERTISEMENT_DATE = "PublicationAdvertisementDate"
COL_TM_OPPOSITION_PERIOD_END_DATE = "OppositionPeriodEndDate"
COL_TM_UPCOMING_LOCAL_DEADLINE = "UpcomingLocalDeadlineOfficeActionDate"
COL_TM_CREATED_AT = "CreatedAt"
COL_TM_UPDATED_AT = "UpdatedAt"

# Transactions Master
COL_TXN_ID = "TransactionID"
COL_TXN_DATE = "TxnDate"
COL_TXN_CLASS = "Class"
COL_TXN_BUSINESS_UNIT = "BusinessUnit"
COL_TXN_TYPE = "Type"
COL_TXN_FROM_ACCOUNT = "FromAccount"
COL_TXN_TO_ACCOUNT = "ToAccount"
COL_TXN_PAYEE = "Payee"
COL_TXN_PARENT = "Parent"
COL_TXN_CLIENT = "Client"
COL_TXN_MATTER = "Matter"
COL_TXN_CATEGORY_CODE = "CategoryCode"
COL_TXN_CATEGORY_NAME = "CategoryName"
COL_TXN_MEMBER = "Member"
COL_TXN_AMOUNT = "Amount"
COL_TXN_TAX_AMOUNT = "TaxAmount"
COL_TXN_TAX_FLAG = "TaxFlag"
COL_TXN_HST_EXEMPT = "HSTExempt"
COL_TXN_GENERAL_OFFICE_EXPENSE = "GeneralOfficeExpense"
COL_TXN_SHADOW = "Shadow"
COL_TXN_INVOICE_REF = "InvoiceRef"
COL_TXN_BILL_CLAIM_PCT = "BillClaimPct"
COL_TXN_TOTAL_CLAIM_AMOUNT = "TotalClaimAmount"
COL_TXN_EXPENSE_DETAILS = "ExpenseDetails"
COL_TXN_NOTES = "Notes"
COL_TXN_STATUS = "Status"
COL_TXN_CURRENCY = "Currency"
COL_TXN_VOID_REASON = "VoidReason"
COL_TXN_CLEARED_AT = "ClearedAt"
COL_TXN_RECONCILED_AT = "ReconciledAt"
COL_TXN_CREATED_AT = "CreatedAt"
COL_TXN_UPDATED_AT = "UpdatedAt"

# Transaction Lookup: Accounts
COL_TXN_ACCOUNT_CODE = "AccountCode"
COL_TXN_ACCOUNT_NAME = "AccountName"
COL_TXN_ACCOUNT_KIND = "AccountKind"
COL_TXN_ACCOUNT_OWNER = "Owner"
COL_TXN_ACCOUNT_ACTIVE = "Active"
COL_TXN_ACCOUNT_ALIASES = "AliasList"

# Transaction Lookup: Categories
COL_TXN_CATEGORY_LKP_CODE = "CategoryCode"
COL_TXN_CATEGORY_LKP_NAME = "CategoryName"
COL_TXN_CATEGORY_LKP_TYPE = "Type"
COL_TXN_CATEGORY_LKP_CLASS_SCOPE = "ClassScope"
COL_TXN_CATEGORY_LKP_TAX_FLAG_DEFAULT = "TaxFlagDefault"
COL_TXN_CATEGORY_LKP_BILLABLE_ALLOWED = "BillableAllowed"
COL_TXN_CATEGORY_LKP_MEDICAL_ELIGIBLE = "MedicalEligible"
COL_TXN_CATEGORY_LKP_DEDUCTIBLE_ELIGIBLE = "DeductibleEligible"
COL_TXN_CATEGORY_LKP_BUSINESS_DEDUCTIBLE_ELIGIBLE = "BusinessDeductibleEligible"
COL_TXN_CATEGORY_LKP_ACTIVE = "Active"
COL_TXN_CATEGORY_LKP_SORT_ORDER = "SortOrder"
COL_TXN_CATEGORY_LKP_NOTES = "Notes"

# Transaction Lookup: Business Units
COL_TXN_BUSINESS_UNIT_NAME = "BusinessUnit"
COL_TXN_BUSINESS_UNIT_OWNER = "Owner"
COL_TXN_BUSINESS_UNIT_ACTIVE = "Active"

# Transaction Lookup: Payees
COL_TXN_PAYEE_NAME = "PayeeName"
COL_TXN_PAYEE_DEFAULT_CATEGORY_CODE = "DefaultCategoryCode"
COL_TXN_PAYEE_ACTIVE = "Active"

# Disbursements
COL_DISB_ID = "DisbursementID"
COL_DISB_DATE = "Date"
COL_DISB_CLIENT_NAME = "ClientName"
COL_DISB_SUB_CLIENT = "SubClient"
COL_DISB_CLIENT_ID = "ClientID"
COL_DISB_PARENT_ID = "ParentID"
COL_DISB_MATTER_ID = "MatterID"
COL_DISB_DESCRIPTION = "Description"
COL_DISB_AMOUNT = "Amount"
COL_DISB_TAX_EXEMPT = "TaxExempt"
COL_DISB_BILL_PCT = "BillPct"
COL_DISB_INVOICE_REF = "InvoiceRef"
COL_DISB_PAYMENT_STATUS = "PaymentStatus"
COL_DISB_INVOICE_TOTAL = "InvoiceTotal"
COL_DISB_INVOICE_AMOUNT_PAID = "InvoiceAmountPaid"
COL_DISB_INVOICE_BALANCE_DUE = "InvoiceBalanceDue"
COL_DISB_CREATED_AT = "CreatedAt"
COL_DISB_REISSUE_INVOICE_NUM = "ReissueInvoiceNum"
# Governed supplier-bill traceability.  These remain blank for manually entered
# legacy disbursements and are appended so existing workbooks migrate safely.
COL_DISB_AP_BILL_ID = "APBillID"
COL_DISB_AP_ALLOCATION_ID = "APAllocationID"
COL_DISB_SOURCE_TRANSACTION_ID = "SourceTransactionID"
COL_DISB_ORIGINAL_CURRENCY = "OriginalCurrency"
COL_DISB_ORIGINAL_AMOUNT = "OriginalAmount"
COL_DISB_FX_RATE = "FXRate"
COL_DISB_SUPPLIER_INVOICE_REF = "SupplierInvoiceRef"
COL_DISB_DOCUMENT_PATH = "DocumentPath"

# Ledger
COL_LEDGER_ID = "LedgerID"
COL_LEDGER_DATE = "Date"
COL_LEDGER_CLIENT_VENDOR = "ClientVendor"
COL_LEDGER_DESCRIPTION = "Description"
COL_LEDGER_CATEGORY = "Category"
COL_LEDGER_REFERENCE = "Reference"
COL_LEDGER_BILLINGS_EXCL_HST = "BillingsExclHST"
COL_LEDGER_HST_COLLECTED = "HSTCollected"
COL_LEDGER_EXPENSES_EXCL_HST = "ExpensesExclHST"
COL_LEDGER_HST_PAID = "HSTPaid"
COL_LEDGER_COLLECTED = "Collected"
COL_LEDGER_WRITE_OFF = "WriteOff"
COL_LEDGER_RECEIVABLE = "Receivable"
COL_LEDGER_TRX_ID = "TrxID"
COL_LEDGER_EXTERNAL_REF_ID = "ExternalRefID"
COL_LEDGER_ORIGINAL_AMOUNT = "OriginalAmount"
COL_LEDGER_WORK_CLIENT = "WorkClient"
COL_LEDGER_CREATED_AT = "CreatedAt"

# Receivables
COL_RECV_INVOICE_NUM = "InvoiceNum"
COL_RECV_DATE = "Date"
COL_RECV_CLIENT = "Client"
COL_RECV_TOTAL_INVOICED = "TotalInvoiced"
COL_RECV_AMOUNT_PAID = "AmountPaid"
COL_RECV_CREDITS_ADJ = "CreditsAdj"
COL_RECV_BALANCE_DUE = "BalanceDue"
COL_RECV_STATUS = "Status"
COL_RECV_WORK_CLIENT = "WorkClient"

# Invoice Log
COL_INV_INVOICE_NUM = "InvoiceNum"
COL_INV_CLIENT_NAME = "ClientName"
COL_INV_SUB_CLIENT = "SubClient"
COL_INV_INVOICE_DATE = "InvoiceDate"
COL_INV_TOTAL_FEES = "TotalFees"
COL_INV_TOTAL_DISBURSEMENTS = "TotalDisbursements"
COL_INV_TOTAL_TAX = "TotalTax"
COL_INV_AGGREGATE_BILLED = "AggregateBilled"
COL_INV_BILL_TO_SNAPSHOT = "BillToSnapshot"
COL_INV_BILL_TO_CLIENT = "BillToClient"
COL_INV_FILE_PATH = "FilePath"

# HST Log
COL_HST_PERIOD_ID = "PeriodID"
COL_HST_PERIOD_START = "PeriodStart"
COL_HST_PERIOD_END = "PeriodEnd"
COL_HST_FILED_DATE = "FiledDate"
COL_HST_CONF_NUM = "ConfNum"
COL_HST_NET_TAX = "NetTax"
COL_HST_PAID_DATE = "PaidDate"
COL_HST_PAYMENT_REF = "PaymentRef"

# Draft Invoices
COL_DRAFT_ID = "DraftID"
COL_DRAFT_INVOICE_NUM = "InvoiceNum"
COL_DRAFT_CLIENT_ID = "ClientID"
COL_DRAFT_CLIENT_NAME = "ClientName"
COL_DRAFT_DATE = "Date"
COL_DRAFT_DISCOUNT_TYPE = "DiscountType"
COL_DRAFT_DISCOUNT_VALUE = "DiscountValue"
COL_DRAFT_AGENCY_SPLIT_PERCENT = "AgencySplitPercent"
COL_DRAFT_TOTAL_FEES = "TotalFees"
COL_DRAFT_TOTAL_DISB = "TotalDisbursements"
COL_DRAFT_TOTAL_TAX = "TotalTax"
COL_DRAFT_TOTAL_DUE = "TotalDue"
COL_DRAFT_GROUPING_PREF = "GroupingPref"
COL_DRAFT_IS_FLAT_FEE = "IsFlatFee"
COL_DRAFT_FLAT_FEE_DESC = "FlatFeeDesc"
COL_DRAFT_FLAT_FEE_AMOUNT = "FlatFeeAmount"
COL_DRAFT_RECONCILIATION_MODE = "ReconciliationMode"
COL_DRAFT_SHOW_TOTAL_HOURS = "ShowTotalHours"
COL_DRAFT_CUSTOM_SORT_ORDER = "CustomSortOrder"
# When an unpaid invoice was issued in error, the correction workflow retains
# its original number as the suggested replacement number on the draft.  This
# survives an app restart without exposing internal audit rows to the billing
# client, but it is deliberately not a hard finalization lock.
COL_DRAFT_REISSUE_INVOICE_NUM = "ReissueInvoiceNum"
COL_DRAFT_BILL_TO_SNAPSHOT = "BillToSnapshot"

# =============================================================================
# CORPORATE ENTITIES
# =============================================================================
COL_CORP_ENTITY_ID = "EntityID"
COL_CORP_CLIENT_ID = "ClientID"
COL_CORP_LEGAL_NAME = "LegalName"
COL_CORP_JURISDICTION = "Jurisdiction"
COL_CORP_INCORP_DATE = "IncorporationDate"
COL_CORP_INC_NUMBER = "IncorporationNumber"
COL_CORP_FISCAL_YE = "FiscalYearEnd"
COL_CORP_STATUS = "Status"
COL_CORP_NOTES = "Notes"
COL_CORP_CREATED = "CreatedAt"

# =============================================================================
# CORPORATE RELATIONSHIPS
# =============================================================================
COL_CREL_ID = "RelationshipID"
COL_CREL_SOURCE = "SourceEntityID"
COL_CREL_TARGET = "TargetEntityID"
COL_CREL_TYPE = "RelationshipType"  # e.g., "Shareholder", "Director", "Officer", "Subsidiary"
COL_CREL_TITLE = "Title"  # e.g., "President", "Secretary"
COL_CREL_SHARE_CLASS = "ShareClass"
COL_CREL_SHARES_HELD = "SharesHeld"
COL_CREL_OWNERSHIP_PCT = "OwnershipPercentage"
COL_CREL_START_DATE = "StartDate"
COL_CREL_END_DATE = "EndDate"
COL_CREL_ACTIVE = "Active"

# =============================================================================
# CORPORATE TRANSACTIONS
# =============================================================================
COL_CTX_ID = "TransactionID"
COL_CTX_ENTITY_ID = "EntityID"
COL_CTX_DATE = "Date"
COL_CTX_TYPE = "TransactionType" # "Issuance", "Transfer", "Redemption", "Dividend"
COL_CTX_FROM = "FromEntityID"
COL_CTX_TO = "ToEntityID"
COL_CTX_SHARE_CLASS = "ShareClass"
COL_CTX_SHARES_QTY = "NumberOfShares"
COL_CTX_PRICE_PER = "PricePerShare"
COL_CTX_TOTAL_VALUE = "TotalValue"
COL_CTX_DOC_REF = "DocumentReference"
COL_CTX_NOTES = "Notes"
COL_CTX_CREATED = "CreatedAt"
COL_DRAFT_GROUPING_PREF = "GroupingPref"
COL_DRAFT_CREATED_AT = "CreatedAt"
COL_DRAFT_UPDATED_AT = "UpdatedAt"

# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

TABLE_COLUMNS: Dict[str, List[str]] = {
    TBL_PARENTS: [
        COL_PARENT_ID, COL_PARENT_NAME, COL_PARENT_DEF_SHARE, COL_PARENT_DEF_RATE,
        COL_PARENT_ACTIVE, COL_PARENT_NOTES
    ],
    TBL_CLIENTS: [
        COL_CLIENT_ID, COL_CLIENT_NAME, COL_CLIENT_EMAIL, COL_CLIENT_PHONE,
        COL_CLIENT_STATUS, COL_CLIENT_ACTIVE, COL_CLIENT_NOTES
    ],
    TBL_CLIENT_PROFILES: [
        COL_PROFILE_CLIENT_ID,
        COL_PROFILE_LEGAL_NAME,
        COL_PROFILE_DISPLAY_NAME,
        COL_PROFILE_FIRST_NAME,
        COL_PROFILE_MIDDLE_NAME,
        COL_PROFILE_LAST_NAME,
        COL_PROFILE_ENTITY_TYPE,
        COL_PROFILE_PRINCIPAL_NAME,
        COL_PROFILE_PRINCIPAL_POSITION,
        COL_PROFILE_PRIMARY_EMAIL,
        COL_PROFILE_PRIMARY_PHONE,
        COL_PROFILE_SECONDARY_CONTACT,
        COL_PROFILE_SECONDARY_POSITION,
        COL_PROFILE_SECONDARY_EMAIL,
        COL_PROFILE_SECONDARY_PHONE,
        COL_PROFILE_ADDR1,
        COL_PROFILE_ADDR2,
        COL_PROFILE_CITY,
        COL_PROFILE_STATE,
        COL_PROFILE_POSTAL,
        COL_PROFILE_COUNTRY,
        COL_PROFILE_FULL_ADDRESS,
        COL_PROFILE_PARENT_ID,
        COL_PROFILE_PARENT_NAME,
        COL_PROFILE_WEBSITE,
        COL_PROFILE_TAX_ID,
        COL_PROFILE_INDUSTRY,
        COL_PROFILE_BILLING_EMAIL,
        COL_PROFILE_KYC_STATUS,
        COL_PROFILE_ONBOARDING_STATUS,
        COL_PROFILE_RETAINER_REQUIRED,
        COL_PROFILE_RETAINER_AMOUNT,
        COL_PROFILE_ENGAGEMENT_START,
        COL_PROFILE_DATE_CLIENT_ADDED,
        COL_PROFILE_BIRTHDAY,
        COL_PROFILE_REFERRAL_FROM,
        COL_PROFILE_CONFLICT_NOTES,
        COL_PROFILE_NOTES,
        COL_PROFILE_CREATED,
        COL_PROFILE_UPDATED,
    ],
    TBL_MATTERS: [
        COL_MATTER_ID,
        COL_MATTER_NUMBER,
        COL_MATTER_NAME,
        COL_MATTER_DISPLAY_NAME,
        COL_MATTER_CLIENT_ID,
        COL_MATTER_CLIENT_NAME,
        COL_MATTER_PARENT_ID,
        COL_MATTER_PARENT_NAME,
        COL_MATTER_TYPE,
        COL_MATTER_PRACTICE_AREA,
        COL_MATTER_STATUS,
        COL_MATTER_RESPONSIBLE_LAWYER,
        COL_MATTER_BILLING_ARRANGEMENT,
        COL_MATTER_BILLING_CONTACT,
        COL_MATTER_BILLING_EMAIL,
        COL_MATTER_DEF_RATE,
        COL_MATTER_DEF_SHARE,
        COL_MATTER_RATE_HISTORY,
        COL_MATTER_ENGAGEMENT_DATE,
        COL_MATTER_OPEN_DATE,
        COL_MATTER_CLOSE_DATE,
        COL_MATTER_COURT_FILE_NO,
        COL_MATTER_OPPOSING_PARTY,
        COL_MATTER_REFERRAL_FROM,
        COL_MATTER_DESCRIPTION,
        COL_MATTER_NOTES,
        COL_MATTER_REPRESENTATION_MODE,
        COL_MATTER_JOINT_NO_CONFIDENTIALITY_CONFIRMED,
        COL_MATTER_JOINT_INSTRUCTIONS_REQUIRE_ALL,
        COL_MATTER_JOINT_ENGAGEMENT_DOCUMENT,
        COL_MATTER_CREATED,
        COL_MATTER_UPDATED,
    ],
    TBL_MATTER_PARTIES: [
        COL_MATTER_PARTY_ID,
        COL_MATTER_PARTY_MATTER_ID,
        COL_MATTER_PARTY_CLIENT_ID,
        COL_MATTER_PARTY_CLIENT_NAME,
        COL_MATTER_PARTY_ROLE,
        COL_MATTER_PARTY_IS_FILE_ANCHOR,
        COL_MATTER_PARTY_IS_BILLING_RECIPIENT,
        COL_MATTER_PARTY_SORT_ORDER,
        COL_MATTER_PARTY_NOTES,
        COL_MATTER_PARTY_CREATED,
        COL_MATTER_PARTY_UPDATED,
    ],
    TBL_TIME: [
        COL_TIME_ENTRY_ID, COL_TIME_DATE, COL_TIME_CLIENT_ID, COL_TIME_MATTER_ID,
        COL_TIME_PARENT_ID, COL_TIME_DESC, COL_TIME_HOURS, COL_TIME_RATE,
        COL_TIME_SHARE_PCT, COL_TIME_GROSS, COL_TIME_NET, COL_TIME_HST,
        COL_TIME_TOTAL, COL_TIME_SECONDS, COL_TIME_STATUS, COL_TIME_INVOICE_REF,
        COL_TIME_INVOICE_STATUS, COL_TIME_PAYMENT_STATUS, COL_TIME_INVOICE_TOTAL,
        COL_TIME_INVOICE_AMOUNT_PAID, COL_TIME_INVOICE_BALANCE_DUE,
        COL_TIME_INVOICE_DATE, COL_TIME_REISSUE_INVOICE_NUM,
        COL_TIME_LOCK_AUDIT, COL_TIME_CREATED
    ],
    TBL_TRADEMARKS: [
        COL_TM_ID,
        COL_TM_JURISDICTION,
        COL_TM_JURISDICTION_OTHER,
        COL_TM_CLIENT_NAME,
        COL_TM_MATTER_NUMBER,
        COL_TM_INTERNAL_NOTES,
        COL_TM_TRADEMARK_TEXT,
        COL_TM_MARK_TYPE,
        COL_TM_DESIGN_REPRESENTATION,
        COL_TM_DESIGN_IMAGE_PASTE,
        COL_TM_COLOR_CLAIMED,
        COL_TM_COLOR_DESCRIPTION,
        COL_TM_NICE_CLASSES,
        COL_TM_GOODS_SERVICES,
        COL_TM_FOREIGN_PRIORITY,
        COL_TM_REGISTRY_LINK,
        COL_TM_APPLICATION_NO,
        COL_TM_REGISTRATION_NO,
        COL_TM_CURRENT_STATUS,
        COL_TM_APPLICANT_NAME_ADDRESS,
        COL_TM_FILING_DATE,
        COL_TM_REGISTRATION_DATE,
        COL_TM_RENEWAL_DEADLINE,
        COL_TM_CIPO_STATUS,
        COL_TM_TM5_STATUS,
        COL_TM_EXAMINERS_REPORT_DATE,
        COL_TM_OFFICE_ACTION_RESPONSE_DEADLINE,
        COL_TM_APPROVAL_DATE,
        COL_TM_ADVERTISEMENT_DATE,
        COL_TM_ADVERTISEMENT_VOL_ISSUE,
        COL_TM_OPPOSITION_DEADLINE,
        COL_TM_ALLOWANCE_DATE,
        COL_TM_REGISTER_TYPE,
        COL_TM_USPTO_STATUS_INDICATOR,
        COL_TM_OWNER_NAME_ADDRESS,
        COL_TM_ATTORNEY_OF_RECORD,
        COL_TM_PUBLICATION_DATE,
        COL_TM_NOTICE_OF_ALLOWANCE_DATE,
        COL_TM_SOU_DEADLINE,
        COL_TM_SOU_EXTENSION_TRACKING,
        COL_TM_SECTION8_DEADLINE,
        COL_TM_SECTION15_DEADLINE,
        COL_TM_SECTION9_DEADLINE,
        COL_TM_LOCAL_FOREIGN_ASSOCIATE,
        COL_TM_APPLICATION_REFERENCE_NO,
        COL_TM_PUBLICATION_ADVERTISEMENT_DATE,
        COL_TM_OPPOSITION_PERIOD_END_DATE,
        COL_TM_UPCOMING_LOCAL_DEADLINE,
        COL_TM_CREATED_AT,
        COL_TM_UPDATED_AT,
    ],
    TBL_TRANSACTIONS_MASTER: [
        COL_TXN_ID,
        COL_TXN_DATE,
        COL_TXN_CLASS,
        COL_TXN_BUSINESS_UNIT,
        COL_TXN_TYPE,
        COL_TXN_FROM_ACCOUNT,
        COL_TXN_TO_ACCOUNT,
        COL_TXN_PAYEE,
        COL_TXN_PARENT,
        COL_TXN_CLIENT,
        COL_TXN_MATTER,
        COL_TXN_CATEGORY_CODE,
        COL_TXN_CATEGORY_NAME,
        COL_TXN_MEMBER,
        COL_TXN_AMOUNT,
        COL_TXN_TAX_AMOUNT,
        COL_TXN_TAX_FLAG,
        COL_TXN_HST_EXEMPT,
        COL_TXN_GENERAL_OFFICE_EXPENSE,
        COL_TXN_SHADOW,
        COL_TXN_INVOICE_REF,
        COL_TXN_BILL_CLAIM_PCT,
        COL_TXN_TOTAL_CLAIM_AMOUNT,
        COL_TXN_EXPENSE_DETAILS,
        COL_TXN_NOTES,
        COL_TXN_STATUS,
        COL_TXN_CURRENCY,
        COL_TXN_VOID_REASON,
        COL_TXN_CLEARED_AT,
        COL_TXN_RECONCILED_AT,
        COL_TXN_CREATED_AT,
        COL_TXN_UPDATED_AT,
    ],
    TBL_TRANSACTION_ACCOUNTS: [
        COL_TXN_ACCOUNT_CODE,
        COL_TXN_ACCOUNT_NAME,
        COL_TXN_ACCOUNT_KIND,
        COL_TXN_ACCOUNT_OWNER,
        COL_TXN_ACCOUNT_ACTIVE,
        COL_TXN_ACCOUNT_ALIASES,
    ],
    TBL_TRANSACTION_CATEGORIES: [
        COL_TXN_CATEGORY_LKP_CODE,
        COL_TXN_CATEGORY_LKP_NAME,
        COL_TXN_CATEGORY_LKP_TYPE,
        COL_TXN_CATEGORY_LKP_CLASS_SCOPE,
        COL_TXN_CATEGORY_LKP_TAX_FLAG_DEFAULT,
        COL_TXN_CATEGORY_LKP_BILLABLE_ALLOWED,
        COL_TXN_CATEGORY_LKP_MEDICAL_ELIGIBLE,
        COL_TXN_CATEGORY_LKP_DEDUCTIBLE_ELIGIBLE,
        COL_TXN_CATEGORY_LKP_BUSINESS_DEDUCTIBLE_ELIGIBLE,
        COL_TXN_CATEGORY_LKP_ACTIVE,
        COL_TXN_CATEGORY_LKP_SORT_ORDER,
        COL_TXN_CATEGORY_LKP_NOTES,
    ],
    TBL_TRANSACTION_BUSINESS_UNITS: [
        COL_TXN_BUSINESS_UNIT_NAME,
        COL_TXN_BUSINESS_UNIT_OWNER,
        COL_TXN_BUSINESS_UNIT_ACTIVE,
    ],
    TBL_TRANSACTION_PAYEES: [
        COL_TXN_PAYEE_NAME,
        COL_TXN_PAYEE_DEFAULT_CATEGORY_CODE,
        COL_TXN_PAYEE_ACTIVE,
    ],
    TBL_DISBURSEMENTS: [
        COL_DISB_ID, COL_DISB_DATE, COL_DISB_CLIENT_NAME, COL_DISB_SUB_CLIENT,
        COL_DISB_CLIENT_ID, COL_DISB_PARENT_ID, COL_DISB_MATTER_ID,
        COL_DISB_DESCRIPTION, COL_DISB_AMOUNT, COL_DISB_TAX_EXEMPT,
        COL_DISB_BILL_PCT, COL_DISB_INVOICE_REF, COL_DISB_PAYMENT_STATUS,
        COL_DISB_INVOICE_TOTAL, COL_DISB_INVOICE_AMOUNT_PAID, COL_DISB_INVOICE_BALANCE_DUE,
        COL_DISB_REISSUE_INVOICE_NUM, COL_DISB_CREATED_AT,
        COL_DISB_AP_BILL_ID, COL_DISB_AP_ALLOCATION_ID,
        COL_DISB_SOURCE_TRANSACTION_ID, COL_DISB_ORIGINAL_CURRENCY,
        COL_DISB_ORIGINAL_AMOUNT, COL_DISB_FX_RATE,
        COL_DISB_SUPPLIER_INVOICE_REF, COL_DISB_DOCUMENT_PATH,
    ],
    TBL_LEDGER: [
        COL_LEDGER_ID, COL_LEDGER_DATE, COL_LEDGER_CLIENT_VENDOR,
        COL_LEDGER_DESCRIPTION, COL_LEDGER_CATEGORY, COL_LEDGER_REFERENCE,
        COL_LEDGER_BILLINGS_EXCL_HST, COL_LEDGER_HST_COLLECTED,
        COL_LEDGER_EXPENSES_EXCL_HST, COL_LEDGER_HST_PAID,
        COL_LEDGER_COLLECTED, COL_LEDGER_WRITE_OFF, COL_LEDGER_RECEIVABLE,
        COL_LEDGER_TRX_ID, COL_LEDGER_EXTERNAL_REF_ID,
        COL_LEDGER_ORIGINAL_AMOUNT, COL_LEDGER_WORK_CLIENT,
        COL_LEDGER_CREATED_AT,
    ],
    TBL_RECEIVABLES: [
        COL_RECV_INVOICE_NUM, COL_RECV_DATE, COL_RECV_CLIENT,
        COL_RECV_TOTAL_INVOICED, COL_RECV_AMOUNT_PAID, COL_RECV_CREDITS_ADJ,
        COL_RECV_BALANCE_DUE, COL_RECV_STATUS, COL_RECV_WORK_CLIENT,
    ],
    TBL_INVOICE_LOG: [
        COL_INV_INVOICE_NUM, COL_INV_CLIENT_NAME, COL_INV_SUB_CLIENT,
        COL_INV_INVOICE_DATE, COL_INV_TOTAL_FEES, COL_INV_TOTAL_DISBURSEMENTS,
        COL_INV_TOTAL_TAX, COL_INV_AGGREGATE_BILLED, COL_INV_BILL_TO_CLIENT,
        COL_INV_BILL_TO_SNAPSHOT,
        COL_INV_FILE_PATH,
    ],
    TBL_HST_LOG: [
        COL_HST_PERIOD_ID, COL_HST_PERIOD_START, COL_HST_PERIOD_END,
        COL_HST_FILED_DATE, COL_HST_CONF_NUM, COL_HST_NET_TAX,
        COL_HST_PAID_DATE, COL_HST_PAYMENT_REF,
    ],
    TBL_DRAFT_INVOICES: [
        COL_DRAFT_ID, COL_DRAFT_INVOICE_NUM, COL_DRAFT_CLIENT_ID,
        COL_DRAFT_CLIENT_NAME, COL_DRAFT_DATE, COL_DRAFT_DISCOUNT_TYPE, COL_DRAFT_DISCOUNT_VALUE, 
        COL_DRAFT_AGENCY_SPLIT_PERCENT, COL_DRAFT_TOTAL_FEES, COL_DRAFT_TOTAL_DISB, COL_DRAFT_TOTAL_TAX, COL_DRAFT_TOTAL_DUE,
        COL_DRAFT_GROUPING_PREF, COL_DRAFT_IS_FLAT_FEE, COL_DRAFT_FLAT_FEE_DESC, COL_DRAFT_FLAT_FEE_AMOUNT, 
        COL_DRAFT_RECONCILIATION_MODE, COL_DRAFT_SHOW_TOTAL_HOURS, COL_DRAFT_CUSTOM_SORT_ORDER,
        COL_DRAFT_REISSUE_INVOICE_NUM, COL_DRAFT_BILL_TO_SNAPSHOT,
        COL_DRAFT_CREATED_AT, COL_DRAFT_UPDATED_AT
    ],
    TBL_CORP_ENTITIES: [
        COL_CORP_ENTITY_ID, COL_CORP_CLIENT_ID, COL_CORP_LEGAL_NAME, COL_CORP_JURISDICTION,
        COL_CORP_INCORP_DATE, COL_CORP_INC_NUMBER, COL_CORP_FISCAL_YE, COL_CORP_STATUS,
        COL_CORP_NOTES, COL_CORP_CREATED
    ],
    TBL_CORP_RELATIONSHIPS: [
        COL_CREL_ID, COL_CREL_SOURCE, COL_CREL_TARGET, COL_CREL_TYPE, COL_CREL_TITLE,
        COL_CREL_SHARE_CLASS, COL_CREL_SHARES_HELD, COL_CREL_OWNERSHIP_PCT,
        COL_CREL_START_DATE, COL_CREL_END_DATE, COL_CREL_ACTIVE
    ],
    TBL_CORP_TRANSACTIONS: [
        COL_CTX_ID, COL_CTX_ENTITY_ID, COL_CTX_DATE, COL_CTX_TYPE, COL_CTX_FROM, COL_CTX_TO,
        COL_CTX_SHARE_CLASS, COL_CTX_SHARES_QTY, COL_CTX_PRICE_PER, COL_CTX_TOTAL_VALUE,
        COL_CTX_DOC_REF, COL_CTX_NOTES, COL_CTX_CREATED
    ]
}

# Aliases for loose matching (Legacy support / CSV ingest)
TABLE_ALIASES: Dict[str, Dict[str, List[str]]] = {
    TBL_PARENTS: {
        COL_PARENT_DEF_SHARE: ["DefaultCutPct", "DefaultYourSharePct", "SharePct"],
    },
    TBL_CLIENTS: {},
    TBL_CLIENT_PROFILES: {
        COL_PROFILE_DISPLAY_NAME: [COL_CLIENT_NAME, "ClientName", "Client"],
        COL_PROFILE_FIRST_NAME: ["First Name", "GivenName", "Given Name"],
        COL_PROFILE_MIDDLE_NAME: ["Middle Name", "MiddleInitial", "Middle Initial"],
        COL_PROFILE_LAST_NAME: ["Last Name", "Surname", "FamilyName", "Family Name"],
        COL_PROFILE_PRIMARY_EMAIL: [COL_CLIENT_EMAIL, "Email"],
        COL_PROFILE_PRIMARY_PHONE: [COL_CLIENT_PHONE, "Phone"],
        COL_PROFILE_PARENT_ID: [COL_PARENT_ID],
        COL_PROFILE_PARENT_NAME: [COL_PARENT_NAME, "Parent", "ParentClient"],
        COL_PROFILE_ENTITY_TYPE: ["ClientType", "Type"],
        COL_PROFILE_PRINCIPAL_POSITION: ["PrincipalTitle", "PrincipalRole", "Role"],
        COL_PROFILE_SECONDARY_CONTACT: ["SecondaryContact", "SecondaryName"],
        COL_PROFILE_SECONDARY_POSITION: ["SecondaryTitle", "SecondaryRole", "SecondaryPosition"],
        COL_PROFILE_SECONDARY_EMAIL: ["SecondaryEmail"],
        COL_PROFILE_SECONDARY_PHONE: ["SecondaryPhone"],
        COL_PROFILE_DATE_CLIENT_ADDED: ["ClientSinceDate", "DateAdded", "DateClientOpened"],
        COL_PROFILE_BIRTHDAY: ["DOB", "BirthDate", "DateOfBirth"],
        COL_PROFILE_REFERRAL_FROM: ["Referral", "ReferralSource", "ReferredBy"],
        COL_PROFILE_FULL_ADDRESS: ["Address", "FormattedAddress"],
        COL_PROFILE_NOTES: [COL_CLIENT_NOTES, "ClientNotes"],
        COL_PROFILE_CONFLICT_NOTES: ["Conflict", "ConflictCheckNotes"],
        COL_PROFILE_ONBOARDING_STATUS: ["Onboarding", "OnboardingStage"],
        COL_PROFILE_KYC_STATUS: ["KYC", "KycStatus"],
    },
    TBL_MATTERS: {
        COL_MATTER_NUMBER: ["FileNumberCode", "MatterCode", "MatterNo"],
        COL_MATTER_DEF_SHARE: ["DefaultCutPct", "DefaultYourSharePct", "SharePct"],
        COL_MATTER_CLIENT_ID: ["ClientName"],
        COL_MATTER_PARENT_ID: ["ParentName"],
        COL_MATTER_DISPLAY_NAME: ["MatterDisplayName", "Display"],
        COL_MATTER_CLIENT_NAME: ["Client", "ClientDisplayName"],
        COL_MATTER_PARENT_NAME: ["Parent", "ParentDisplayName"],
        COL_MATTER_TYPE: ["Type", "FileType"],
        COL_MATTER_PRACTICE_AREA: ["Practice", "AreaOfLaw"],
        COL_MATTER_RESPONSIBLE_LAWYER: ["ResponsibleAttorney", "Lawyer", "Owner"],
        COL_MATTER_BILLING_ARRANGEMENT: ["BillingType", "FeeArrangement"],
        COL_MATTER_BILLING_CONTACT: ["BillingContactName", "BillingAttention"],
        COL_MATTER_BILLING_EMAIL: ["InvoiceEmail"],
        COL_MATTER_ENGAGEMENT_DATE: ["EngagementDate"],
        COL_MATTER_OPEN_DATE: ["OpenDate", "OpenedDate"],
        COL_MATTER_CLOSE_DATE: ["CloseDate", "ClosedDate"],
        COL_MATTER_COURT_FILE_NO: ["CourtFileNo", "CourtFile", "FileNumber"],
        COL_MATTER_OPPOSING_PARTY: ["OpposingCounsel", "OpposingPartyName"],
        COL_MATTER_REFERRAL_FROM: ["ReferralSource", "ReferredBy"],
        COL_MATTER_DESCRIPTION: ["Summary", "MatterDescription"],
        COL_MATTER_NOTES: ["MatterNotes"],
        COL_MATTER_CREATED: ["Created"],
        COL_MATTER_UPDATED: ["Updated"],
    },
    TBL_TIME: {
        COL_TIME_SHARE_PCT: ["CutPct", "YourSharePct", "Percentage"],
        COL_TIME_GROSS: ["AmountToClient", "GrossAmount", "Amount to CS"],
        COL_TIME_NET: ["AmountToCory", "AmountToCS"],
        COL_TIME_CLIENT_ID: ["ClientName", "Client"],
        COL_TIME_MATTER_ID: ["MatterName", "Matter"],
        COL_TIME_PARENT_ID: ["ParentName", "Parent"],
        COL_TIME_HOURS: ["Time (in hrs) or Units", "Time"],
        COL_TIME_INVOICE_REF: ["Invoice", "Invoice #", "InvoiceNum", "InvoiceNumber"],
        COL_TIME_INVOICE_STATUS: ["Invoice State", "InvoiceState", "BillingStatus"],
        COL_TIME_PAYMENT_STATUS: ["PaidStatus", "Payment State", "PaymentState"],
        COL_TIME_INVOICE_TOTAL: ["TotalInvoiced", "Total_Invoiced"],
        COL_TIME_INVOICE_AMOUNT_PAID: ["AmountPaid", "Amount_Paid"],
        COL_TIME_INVOICE_BALANCE_DUE: ["BalanceDue", "Balance_Due"],
        COL_TIME_INVOICE_DATE: ["Invoice Date", "InvoiceDate"],
        COL_TIME_LOCK_AUDIT: ["TimerAudit", "LockEvents", "HandoffAudit"],
    },
    TBL_TRADEMARKS: {
        COL_TM_CLIENT_NAME: ["Client"],
        COL_TM_MATTER_NUMBER: ["Matter", "MatterNo"],
        COL_TM_INTERNAL_NOTES: ["InternalNotes", "Notes"],
        COL_TM_TRADEMARK_TEXT: ["Trademark", "MarkText"],
        COL_TM_MARK_TYPE: ["Type", "TrademarkType"],
        COL_TM_DESIGN_REPRESENTATION: ["DesignFile", "DesignImagePath"],
        COL_TM_NICE_CLASSES: ["NiceClassification", "InternationalClasses"],
        COL_TM_GOODS_SERVICES: ["GoodsAndServices", "GoodsServices"],
        COL_TM_FOREIGN_PRIORITY: ["ForeignPriority"],
        COL_TM_REGISTRY_LINK: ["RegistryUrl", "ExternalLink"],
        COL_TM_APPLICATION_NO: ["ApplicationNo", "SerialNumber"],
        COL_TM_REGISTRATION_NO: ["RegistrationNo"],
        COL_TM_CURRENT_STATUS: ["Status"],
        COL_TM_JURISDICTION_OTHER: ["JurisdictionCountryOffice"],
        COL_TM_APPLICATION_REFERENCE_NO: ["ApplicationRefNo", "ReferenceNumber"],
    },
    TBL_TRANSACTIONS_MASTER: {
        COL_TXN_ID: ["TxnID", "TransactionId"],
        COL_TXN_DATE: ["Date", "TransactionDate"],
        COL_TXN_CLASS: ["TxnClass"],
        COL_TXN_BUSINESS_UNIT: ["BusinessUnitName", "BU"],
        COL_TXN_FROM_ACCOUNT: ["SourceAccount", "AccountFrom"],
        COL_TXN_TO_ACCOUNT: ["DestinationAccount", "AccountTo"],
        COL_TXN_PAYEE: ["Vendor", "VendorPayee", "Counterparty"],
        COL_TXN_PARENT: [COL_PARENT_NAME, COL_PARENT_ID],
        COL_TXN_CLIENT: [COL_CLIENT_NAME, COL_CLIENT_ID],
        COL_TXN_MATTER: [COL_MATTER_NAME, COL_MATTER_ID, COL_MATTER_NUMBER],
        COL_TXN_CATEGORY_CODE: ["Category", "CatCode"],
        COL_TXN_CATEGORY_NAME: ["CategoryLabel", "CategoryDisplay"],
        COL_TXN_MEMBER: ["HouseholdMember", "OwnerMember"],
        COL_TXN_TAX_AMOUNT: ["HSTAmount", "Tax", "HST"],
        COL_TXN_TAX_FLAG: ["TaxCategory"],
        COL_TXN_HST_EXEMPT: ["IsHSTExempt"],
        COL_TXN_GENERAL_OFFICE_EXPENSE: ["OfficeExpense", "GeneralOffice"],
        COL_TXN_INVOICE_REF: ["InvoiceNumber", "InvoiceRefNo", "Invoice"],
        COL_TXN_BILL_CLAIM_PCT: ["ClaimPct", "BillablePct"],
        COL_TXN_TOTAL_CLAIM_AMOUNT: ["ClaimAmount", "TotalClaim"],
        COL_TXN_EXPENSE_DETAILS: ["Details", "Description"],
        COL_TXN_VOID_REASON: ["VoidNotes", "VoidComment"],
        COL_TXN_CLEARED_AT: ["ClearedDate"],
        COL_TXN_RECONCILED_AT: ["ReconciledDate"],
        COL_TXN_CREATED_AT: ["Created"],
        COL_TXN_UPDATED_AT: ["Updated"],
    },
    TBL_TRANSACTION_ACCOUNTS: {
        COL_TXN_ACCOUNT_ALIASES: ["Aliases", "Alias"],
        COL_TXN_ACCOUNT_KIND: ["Kind", "AccountType"],
    },
    TBL_TRANSACTION_CATEGORIES: {
        COL_TXN_CATEGORY_LKP_CODE: ["CatCode", "Code"],
        COL_TXN_CATEGORY_LKP_NAME: ["Category", "Name"],
        COL_TXN_CATEGORY_LKP_CLASS_SCOPE: ["Class", "ClassFilter"],
        COL_TXN_CATEGORY_LKP_TAX_FLAG_DEFAULT: ["TaxFlag", "DefaultTaxFlag"],
        COL_TXN_CATEGORY_LKP_BILLABLE_ALLOWED: ["Billable"],
        COL_TXN_CATEGORY_LKP_MEDICAL_ELIGIBLE: ["MedicalAllowed"],
        COL_TXN_CATEGORY_LKP_DEDUCTIBLE_ELIGIBLE: ["DeductibleAllowed"],
        COL_TXN_CATEGORY_LKP_BUSINESS_DEDUCTIBLE_ELIGIBLE: ["BusinessDeductibleAllowed"],
    },
    TBL_TRANSACTION_BUSINESS_UNITS: {},
    TBL_TRANSACTION_PAYEES: {
        COL_TXN_PAYEE_NAME: ["Payee", "Vendor"],
        COL_TXN_PAYEE_DEFAULT_CATEGORY_CODE: ["DefaultCategory", "CategoryCode"],
    },
    TBL_DISBURSEMENTS: {},
    TBL_LEDGER: {
        COL_LEDGER_CLIENT_VENDOR: ["Client/Vendor", "Client"],
        COL_LEDGER_TRX_ID: ["TransactionID"],
    },
    TBL_RECEIVABLES: {
        COL_RECV_INVOICE_NUM: ["Invoice#", "InvoiceNumber"],
        COL_RECV_CREDITS_ADJ: ["Credits", "Adjustments"],
    },
    TBL_INVOICE_LOG: {
        COL_INV_INVOICE_NUM: ["Invoice#", "InvoiceNumber"],
        COL_INV_INVOICE_DATE: ["Invoice Date", "Date Generated", "DateGenerated", "Date"],
        COL_INV_AGGREGATE_BILLED: ["TotalBilled", "AggregateBilledToClient"],
    },
    TBL_HST_LOG: {},
}
