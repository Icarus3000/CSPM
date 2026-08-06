"""
Omni-search command routing logic.

Extracted from app_controller.py to reduce monolith size.
Routes user queries to the appropriate lane/subwindow in the CSPM UI.
"""
import re
from typing import Any, Callable, Dict, Optional


# Lane titles — map tile index → display name.
LANE_TITLES = {
    0: "Clients & Matters",
    1: "Docketing & Deadlines",
    2: "Billing, Payments & Tax",
    3: "Finance, Reports & Operations",
}

# Lane keyword catalog (tile_index, title, keywords).
LANE_CATALOG = [
    (0, "Clients & Matters", ("client", "clients", "matter", "matters", "parent", "conflict", "kyc")),
    # include trademark as a docketing keyword so generic searches route into that lane
    (1, "Docketing & Deadlines", ("docket", "deadline", "tickler", "timer", "filing", "calendar", "trademark")),
    (2, "Billing, Payments & Tax", ("billing", "invoice", "payment", "write-off", "expense", "hst", "gst", "tax")),
    (3, "Finance, Reports & Operations", ("dashboard", "report", "wip", "ar", "ledger", "forecast", "operations")),
]

# Full pathway catalog — IDs match ModulePathways.js
# NOTE: removed IDs are commented out; their keywords still route to
# the screens that absorbed their functionality.
SUBWINDOW_CATALOG = [
    (0, "A01", "Client Directory", ("client directory", "clients list")),
    (0, "A02", "New Client Wizard", ("new client", "add client", "create client")),
    (0, "A03", "Client Profile 360", ("client profile", "client details", "client notes", "notes")),
    # A07 (Client Notes) removed — keywords routed to A03
    (0, "A04", "Client Contacts & Roles", ("client contacts", "contacts roles")),
    (0, "A05", "Parent-Child Link Manager", ("parent client", "parent child", "client hierarchy")),
    (0, "A06", "Client ID/KYC Record", ("kyc", "client id", "id record")),
    (0, "A08", "Conflict Check", ("conflict", "conflict check")),
    (0, "A09", "Matter Directory", ("matter directory", "matters list")),
    (0, "A10", "New Matter Wizard", ("new matter", "add matter", "create matter")),
    (0, "A11", "Matter Profile 360", ("matter profile", "matter details", "billing terms", "matter rate", "open matter", "close matter", "reopen matter")),
    # A12 (Matter Billing Terms) removed — keywords routed to A11
    # A13 (Matter Open/Close/Reopen) removed — keywords routed to A11
    (0, "A14", "Matter Reassignment", ("reassign matter", "matter reassignment")),
    (0, "A15", "Duplicate Merge Tool", ("duplicate merge", "merge clients", "merge matters")),
    (1, "B01", "Time Docket Entry", ("time docket", "docket entry", "new docket", "timer entry")),
    (1, "B02", "Fee Docket Entry", ("fee docket", "fee entry")),
    (1, "B03", "Timer Console", ("timer console", "stopwatch")),
    (1, "B04", "Docket Activity Report", ("docket activity report", "docket report", "time docket report", "docket review", "review queue")),
    (1, "B05", "Docket Adjustment/Void", ("docket adjustment", "void docket")),
    (1, "B06", "Batch Docket Entry", ("batch docket", "bulk docket")),
    (1, "B07", "Deadline Master Calendar", ("deadline calendar", "master calendar")),
    (1, "B08", "Deadline Entry Editor", ("deadline entry", "edit deadline")),
    (1, "B09", "Deadline Rules Library", ("deadline rules", "rules library")),
    (1, "B10", "Jurisdiction Profiles", ("jurisdiction", "country profile")),
    (1, "B11", "Tickler Scheduler", ("tickler", "scheduler")),
    (1, "B12", "Reminder Escalation Center", ("reminder escalation", "escalation")),
    (1, "B13", "Filing Checklist", ("filing checklist", "filing prep")),
    (1, "B14", "Deadline Risk Board", ("deadline risk", "risk board")),
    (1, "B15", "Deadline Audit Trail", ("deadline audit", "audit trail")),
    (1, "B16", "Trademark Filing", ("trademark", "trademark filing", "uspto", "cipo")),
    (1, "B17", "Trademark Directory", ("trademark directory", "search trademark", "trademark search")),
    (2, "C01", "WIP-to-Bill Workbench", ("wip to bill", "bill workbench")),
    (2, "C02", "Pre-Bill Editor", ("pre bill", "pre-bill", "proforma", "sample invoice")),
    # C04 (Proforma/Sample Invoice) removed — keywords routed to C02
    (2, "C03", "Invoice Builder", ("invoice builder", "build invoice", "invoice finalization", "invoice numbering")),
    (2, "C04", "Invoice Directory", ("invoice directory", "invoice explorer", "invoice dashboard", "invoice details", "search invoice")),
    (2, "C08", "Reverse an Invoice", ("reverse invoice", "invoice reversal", "credit memo")),
    (2, "C07", "Payment Entry", ("record payment", "payment entry", "post payment", "open invoice", "invoice selector")),
    # C08 (Open Invoice Selector) removed — keywords routed to C07
    (2, "C09", "Write-off/Adjustment Entry", ("write-off", "adjustment entry")),
    (2, "C10", "Collections Queue", ("collections", "ar collections")),
    (2, "C11", "Transactions Master", ("transactions master", "expense entry", "log expense")),
    (2, "C12", "Vendor & Expense Category Manager", ("vendor", "expense category")),
    (2, "C13", "Disbursement Rebill Queue", ("disbursement rebill", "rebill queue")),
    (2, "C14", "HST/GST Remittance Center", ("hst remittance", "gst remittance", "tax remittance")),
    (2, "C15", "Tax Filing Register", ("tax filing", "filing register")),
    (2, "C16", "Payment Method & Reference Register", ("payment method", "payment reference")),
    (2, "C17", "Bank Deposit Matching", ("bank deposit", "deposit matching")),
    (3, "D01", "Executive Dashboard", ("executive dashboard", "financial dashboard", "finance dashboard", "dashboard")),
    (3, "D02", "Revenue Dashboard", ("revenue dashboard", "revenue")),
    (3, "D03", "Expense Dashboard", ("expense dashboard", "expenses dashboard")),
    (3, "D04", "Net Income & Cash Increase", ("net income", "cash increase")),
    (3, "D05", "WIP Dashboard/Report", ("wip dashboard", "wip report")),
    (3, "D06", "A/R Aging & Detail", ("a/r", "ar aging", "accounts receivable")),
    (3, "D07", "Client Ledger Report", ("client ledger", "ledger by client")),
    (3, "D17", "Statement of Account", ("statement", "account statement", "client statement")),
    (3, "D08", "Matter Ledger Report", ("matter ledger", "ledger by matter")),
    (3, "D09", "Parent Ledger Report", ("parent ledger", "ledger by parent")),
    (3, "D10", "Productivity & Utilization Report", ("productivity report", "productivity", "utilization", "realization")),
    # D12 (Utilization/Realization Report) removed — keywords merged into D10
    (3, "D11", "Earnings Report", ("earnings report", "earnings")),
    (3, "D13", "Top Client Concentration", ("top clients", "client concentration")),
    (3, "D14", "Quarterly Performance Pack", ("quarterly performance", "performance pack")),
    (3, "D15", "Forecasting & Scenarios", ("forecast", "scenario")),
    (3, "D16", "Export/Print Packager", ("export", "print packager")),
    (3, "X01", "Global Search Results", ("global search",)),
    (3, "X02", "Notifications Center", ("notifications",)),
    (3, "X03", "Tasks & Approvals Inbox", ("approvals", "tasks inbox")),
    (3, "X04", "Document Workspace Browser", ("document workspace", "documents")),
    (3, "X05", "Template Manager", ("templates", "template manager")),
    (3, "X06", "User Roles & Permissions", ("roles", "permissions")),
    (3, "X07", "Audit Log Viewer", ("audit log", "audit viewer")),
    (3, "X08", "Number Sequence Manager", ("number sequence", "numbering")),
    (3, "X09", "Reference Data Manager", ("reference data",)),
    (3, "X10", "Integration Settings", ("integrations", "integration settings")),
    (3, "X11", "Backup/Restore & Retention", ("backup", "restore", "retention")),
    (3, "X12", "Data Quality Exceptions", ("data quality", "exceptions")),
]

_MATTER_PATTERN = re.compile(r"\bM-\d{4}-\d+\b", re.IGNORECASE)
_INVOICE_PATTERN = re.compile(r"\b(?:inv(?:oice)?[-\s#:]?\d+)\b", re.IGNORECASE)


def _route_from_subwindow_catalog(raw_query: str, normalized: str) -> Optional[Dict[str, Any]]:
    """Resolve explicit function/screen commands before probing workbook data."""
    for tile_index, subwindow_id, subwindow_title, aliases in SUBWINDOW_CATALOG:
        title_lc = subwindow_title.lower()
        if subwindow_id == "A01":
            if normalized == "a01" or normalized == "client directory" or normalized == "clients list":
                return _route(raw_query, tile_index, subwindow_id, subwindow_title, "subwindow")
            continue
        if normalized == subwindow_id.lower() or normalized in title_lc or title_lc in normalized:
            return _route(raw_query, tile_index, subwindow_id, subwindow_title, "subwindow")
        if any(normalized in alias or alias in normalized for alias in aliases):
            return _route(raw_query, tile_index, subwindow_id, subwindow_title, "subwindow")
    return None


def _route_from_lane_catalog(raw_query: str, normalized: str) -> Optional[Dict[str, Any]]:
    for tile_index, lane_title, aliases in LANE_CATALOG:
        lane_lc = lane_title.lower()
        if normalized in lane_lc or any(normalized in alias or alias in normalized for alias in aliases):
            return _route(raw_query, tile_index, "", lane_title, "lane")
    return None


def _route(
    raw_query: str,
    tile_index: int,
    subwindow_id: str,
    subwindow_title: str,
    query_type: str,
    routed_query_text: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ok": True,
        "tileIndex": int(tile_index),
        "title": LANE_TITLES.get(int(tile_index), ""),
        "subwindowId": str(subwindow_id or ""),
        "subwindowTitle": str(subwindow_title or ""),
        "queryType": str(query_type or "command"),
        "queryText": str(raw_query if routed_query_text is None else routed_query_text),
    }


def _route_from_top_result(raw_query: str, result_row: Dict[str, Any]) -> Dict[str, Any]:
    try:
        tile_index = int(result_row.get("routeTileIndex", 3))
    except Exception:
        tile_index = 3
    if tile_index < 0 or tile_index > 3:
        tile_index = 3

    subwindow_id = str(result_row.get("routeNodeId") or "X01").strip() or "X01"
    subwindow_title = str(result_row.get("routeNodeTitle") or "Global Search Results").strip()
    if not subwindow_title:
        subwindow_title = "Global Search Results"

    routed = _route(
        raw_query,
        tile_index,
        subwindow_id,
        subwindow_title,
        "top_result",
        raw_query,
    )
    for key in (
        "entityType",
        "entityTypeLabel",
        "entityId",
        "title",
        "subtitle",
        "status",
        "matchedFields",
        "clientId",
        "clientName",
        "legalName",
        "principalName",
        "primaryEmail",
        "matterId",
        "matterNumber",
        "matterName",
        "displayName",
        "parentId",
        "parentName",
        "transactionId",
        "txnDate",
        "businessUnit",
        "type",
        "payee",
        "categoryCode",
        "categoryName",
        "accountCode",
        "accountName",
        "trademarkId",
        "trademarkText",
    ):
        if key in result_row:
            routed[key] = result_row.get(key)
    return routed


def handle_omni_search_command(
    query: str,
    repo,
    report_failure: Callable[..., None],
) -> Dict[str, Any]:
    """Route an omni-search query to the appropriate UI lane/subwindow.

    Parameters:
        query: Raw query string from the search bar.
        repo: Repo facade with ``search_global_entities(query, mode, limit)`` method.
        report_failure: callable(user_message, *, context, exc, emit_signal) for error reporting.

    Returns:
        Dict with routing info (ok, tileIndex, title, subwindowId, subwindowTitle, queryType, queryText).
    """
    raw_query = str(query or "").strip()
    normalized = raw_query.lower()
    fallback: Dict[str, Any] = {
        "ok": False,
        "tileIndex": -1,
        "title": "",
        "subwindowId": "",
        "subwindowTitle": "",
        "queryType": "",
        "queryText": raw_query,
    }
    if normalized == "":
        return fallback

    # Explicit prefix-based lookups
    for prefix, strip_len, tile, sub_id, sub_title, qtype in [
        ("client:", 7, 0, "A01", "Client Directory", "client_lookup"),
        ("client ", 7, 0, "A01", "Client Directory", "client_lookup"),
        ("matter:", 7, 0, "A11", "Matter Profile 360", "matter_lookup"),
        ("matter ", 7, 0, "A11", "Matter Profile 360", "matter_lookup"),
        ("parent:", 7, 0, "A05", "Parent-Child Link Manager", "parent_lookup"),
        ("parent ", 7, 0, "A05", "Parent-Child Link Manager", "parent_lookup"),
    ]:
        if normalized.startswith(prefix):
            extracted = normalized[strip_len:].strip()
            if extracted:
                return _route(raw_query, tile, sub_id, sub_title, qtype, extracted)

    for prefix in ("global search:", "global search ", "search:"):
        if normalized.startswith(prefix):
            extracted = raw_query[len(prefix):].strip()
            if extracted:
                return _route(raw_query, 3, "X01", "Global Search Results", "global_lookup", extracted)

    if normalized in {"x01", "global search", "global search results", "search results"}:
        return _route(raw_query, 3, "X01", "Global Search Results", "subwindow", "")

    # Function/screen commands should behave like a command palette. Resolve them
    # before the broad data probe so phrases such as "new matter" open the wizard.
    catalog_route = _route_from_subwindow_catalog(raw_query, normalized)
    if catalog_route is not None:
        return catalog_route

    lane_route = _route_from_lane_catalog(raw_query, normalized)
    if lane_route is not None:
        return lane_route

    # Wide-net data lookup from the home omni bar opens the first ranked result.
    # The dedicated Global Search screen remains the place for browsing all matches.
    try:
        search_payload = repo.search_global_entities(
            query=raw_query,
            mode="any",
            limit=120,
        )
        if bool(search_payload.get("ok")) and int(search_payload.get("total", 0)) > 0:
            results = search_payload.get("results")
            if isinstance(results, list) and results:
                if len(results) == 1:
                    first = results[0]
                    if isinstance(first, dict):
                        return _route_from_top_result(raw_query, first)
            return _route(raw_query, 3, "X01", "Global Search Results", "global_lookup", raw_query)
    except Exception as exc:
        report_failure(
            "Global search probe failed",
            context="repo.search.global_probe",
            exc=exc,
            emit_signal=False,
        )

    # Pattern-based fallbacks keep lookup flows available before all entities are modeled.
    if _MATTER_PATTERN.search(raw_query):
        return _route(raw_query, 3, "X01", "Global Search Results", "global_lookup", "")

    if _INVOICE_PATTERN.search(raw_query) or normalized.startswith("invoice #"):
        return _route(raw_query, 3, "X01", "Global Search Results", "global_lookup", "")

    # Keep arbitrary free text on the results screen instead of guessing a single target.
    return _route(raw_query, 3, "X01", "Global Search Results", "global_lookup", "")
