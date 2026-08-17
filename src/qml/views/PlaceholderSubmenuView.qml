pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../components"
import "../standards"
import "../standards/SubwindowStyle.js" as SubwindowStyle
import "../standards/SemanticTheme.js" as SemanticTheme
import "./placeholder"
import "./corporate"

Item {
    id: root

    property var t
    property var metrics
    property var windowRef
    property var appRef: ((typeof app !== "undefined") && app !== null) ? app : null
    property alias transactionMasterView: transactionMasterLoader.item
    property alias paymentEntryView: paymentEntryLoader.item
    property alias wipBillingView: wipBillingLoader.item
    property alias invoiceBuilderView: invoiceBuilderLoader.item
    property alias invoiceDirectoryView: invoiceDirectoryLoader.item
    property alias invoiceReversalView: invoiceReversalLoader.item
    property alias legacyDocketsImportView: legacyDocketsImportLoader.item
    property var sfxBus: (root.windowRef && root.windowRef.sfxBusRef) ? root.windowRef.sfxBusRef : null
    property int tileIndex: -1
    property string titleText: "Module"
    property string laneKey: ""
    property var navItems: []
    property var allNavItems: []
    property string defaultNodeId: ""
    property var laneSummary: ({})
    property var initialState: null
    property bool detachedWindow: false
    property bool externalNavigationShell: false

    property string appStyle: (root.appRef && root.appRef.appStyle)
        ? String(root.appRef.appStyle)
        : (((typeof app !== "undefined") && app !== null && app.appStyle) ? String(app.appStyle) : "Professional")
    property color _accent: root.appStyle === "Professional" ? SemanticTheme.accentPrimary(root.t, root.appStyle) : ((t && t.accent) ? t.accent : "#4DA3FF")
    property color _text: root.appStyle === "Professional" ? SemanticTheme.inkPrimary(root.t, root.appStyle) : ((t && t.text) ? t.text : "#FFFFFF")
    property color _panel: root.appStyle === "Professional" ? SemanticTheme.surfaceRaised(root.t, root.appStyle) : ((t && t.panel2) ? t.panel2 : "#1A1A1A")
    property color _bg: root.appStyle === "Professional" ? SemanticTheme.surfaceApp(root.t, root.appStyle) : ((t && t.bg) ? t.bg : "#000000")
    property color _panelBase: root.appStyle === "Professional" ? SemanticTheme.surfacePanel(root.t, root.appStyle) : ((t && t.panel) ? t.panel : _panel)
    property real _bgLuma: (_bg.r * 0.299) + (_bg.g * 0.587) + (_bg.b * 0.114)
    property bool lightTheme: _bgLuma >= 0.58
    property bool isProMode: visualRules.isPro
    property color proBackground: SemanticTheme.surfaceApp(root.t, root.appStyle)
    property color proSurface: SemanticTheme.surfaceRaised(root.t, root.appStyle)
    property color proCanvas: SemanticTheme.surfacePanel(root.t, root.appStyle)
    property color proHoverFill: SemanticTheme.surfaceInput(root.t, root.appStyle)
    property color proInk: SemanticTheme.inkPrimary(root.t, root.appStyle)
    property color proMutedInk: SemanticTheme.inkMuted(root.t, root.appStyle)
    property color proBorder: SemanticTheme.borderSubtle(root.t, root.appStyle)
    property color proActiveBorder: SemanticTheme.borderStrong(root.t, root.appStyle)
    property color proAccent: SemanticTheme.accentPrimary(root.t, root.appStyle)
    property var scaleRatios: SubwindowStyle.placeholderRatios()
    property bool dirty: false
    property var _pendingStateForLoader: null
    property bool _hydrating: false
    property string activeNodeId: ""
    property bool saveInProgress: false
    property bool lastSaveOk: false
    property string lastSavedClientId: ""
    property string lastSavedMatterId: ""
    property string lastSavedTransactionId: ""
    property string saveMessage: ""
    property var parentClientOptions: []
    property var matterClientOptions: []
    property bool matterJointRetainer: false
    property var matterParties: []
    property bool matterJointNoConfidentialityConfirmed: false
    property bool matterJointInstructionsRequireAll: true
    property bool clientCreateForMatterParty: false
    property var matterPartyRoleOptions: ["Joint client", "Client", "Represented corporation", "Authorized instructing representative"]
    property string newClientOptionLabel: "new client"
    property bool _autoFieldMutation: false
    property bool legalNameAutoSync: true
    property bool matterDisplayNameAutoSync: true
    property bool matterBillingEmailAutoSync: true
    property bool matterBillingContactAutoSync: true
    property bool matterDefaultRateAutoSync: true
    property bool matterDefaultShareAutoSync: true
    property var practiceAreaOptions: ["General", "Intellectual Property", "Tax", "Corporate / Commercial", "Real Estate", "Litigation & Dispute Resolution", "Wills & Estates", "Family Law"]
    property var practiceAreaMatterTypes: {
        "General": ["General Consultation", "Notary / Commissioning", "Other"],
        "Intellectual Property": ["Trademark Filings", "Patent Filings", "Copyright Filings", "IP Litigation", "Cease and Desist", "IP Management", "IP Licensing", "Trade Secrets"],
        "Tax": ["CRA Audit / Reassessment", "Tax Litigation", "Voluntary Disclosure (VDP)", "Section 85 Rollover / Reorganization", "Estate Freeze", "Tax Planning & Advisory", "Commodity Tax / HST", "Notice of Objection"],
        "Corporate / Commercial": ["Incorporation / Organization", "Corporate Reorganization", "Share Purchase / Sale", "Asset Purchase / Sale", "Unanimous Shareholder Agreement (USA)", "Contract Drafting & Review", "Corporate Maintenance / Annual Returns", "Financing / Secured Lending", "Amalgamation / Dissolution"],
        "Real Estate": ["Residential Purchase", "Residential Sale", "Commercial Purchase", "Commercial Sale", "Refinance / Mortgage", "Commercial Leasing", "Title Transfer"],
        "Litigation & Dispute Resolution": ["Civil Litigation", "Commercial Litigation", "Small Claims", "Debt Recovery", "Breach of Contract", "Shareholder Dispute"],
        "Wills & Estates": ["Will Preparation", "Powers of Attorney", "Estate Administration / Probate", "Estate Litigation"],
        "Family Law": ["Separation Agreement", "Divorce", "Child / Spousal Support", "Cohabitation / Marriage Contract"]
    }
    property var lawyerOptions: [""]
    property bool individualNameAutoSync: true
    property bool individualNameFieldsReady: false
    property bool principalNameAutoSync: true
    property bool billingEmailAutoSync: true
    property var clientDirectoryRows: []
    property var clientDirectoryFilteredRows: []
    property var clientDirectoryNameOptions: []
    property string clientDirectoryQuery: ""
    property string clientDirectoryMode: "all"
    property var matterDirectoryRows: []
    property var matterDirectoryFilteredRows: []
    property var matterDirectoryNameOptions: []
    property string matterDirectoryQuery: ""
    property string matterDirectoryMode: "all"
    property var globalSearchRows: []
    property var globalSearchFilteredRows: []
    property var globalSearchFacetCounts: ({
        "client": 0,
        "matter": 0,
        "parent": 0,
        "invoice": 0,
        "tickler": 0,
        "deadline": 0,
        "docket": 0
    })
    property string globalSearchMode: "any"
    property string globalSearchEntityFilter: "all"
    property string globalSearchMessage: "Enter a search query."
    property bool globalSearchLastOk: true
    property string selectedClientId: ""
    property string selectedClientName: ""
    property var selectedClientProfile: ({})
    property string profileLookupMessage: ""
    property string pendingClientProfileAutoLoadKey: ""
    property string selectedMatterId: ""
    property string selectedMatterName: ""
    property var selectedMatterProfile: ({})
    // Keep record-detail panels reactive after a synchronous profile lookup.
    // A method-call binding against a dynamic `root` property can retain the
    // initial directory-shaped row instead of the loaded full profile.
    property var matterProfileRows: []
    property string matterProfileLookupMessage: ""
    // Loaded asynchronously so opening an editable matter does not stall while
    // its WIP and A/R are read from the workbook.
    property var matterFinancialSummary: ({ "ok": false })
    property bool matterFinancialSummaryLoading: false
    property string matterFinancialSummaryToken: ""
    property string matterPersistedStatus: ""
    Item {
        id: matterDescriptionInput
        property string text: ""
    }
    property bool clientEditMode: false
    property bool matterEditMode: false
    property bool clientCreateFromMatterMode: false
    property bool matterNumberAutoSync: true
    property string matterLastAutoNumber: ""
    property string editReturnNodeId: ""
    property string editReturnClientId: ""
    property string editReturnClientName: ""
    property string editReturnMatterId: ""
    property string editReturnMatterName: ""
    property string clientWizardDateTarget: ""
    property string clientSaveValidationSummary: ""
    property var entityTypeOptions: [
        "Individual",
        "Corporation",
        "LLC",
        "Partnership",
        "Sole Proprietorship",
        "Nonprofit",
        "Trust",
        "Government",
        "Other"
    ]

    VisualRules {
        id: visualRules
        appStyle: root.appStyle
    }
    property var onboardingOptions: [
        "Prospect",
        "Conflict Review",
        "KYC Pending",
        "Engagement Pending",
        "Active",
        "Archived"
    ]
    property var kycOptions: ["Pending", "In Review", "Cleared", "Failed", "Not Required"]
    property var clientStatusOptions: ["Active", "Prospect", "Inactive", "Closed", "Archived"]
    property var matterTypeOptions: [""]
    property var matterStatusOptions: ["Open", "Active", "Pending", "On Hold", "Closed", "Archived"]
    property var matterBillingArrangementOptions: ["Hourly", "Flat Fee", "Contingency", "Hybrid", "Retainer"]
    property var laneSwitchModel: [
        { "tileIndex": 0, "title": "Clients", "shortTitle": "Clients", "compactTitle": "C" },
        { "tileIndex": 1, "title": "Docketing", "shortTitle": "Docket", "compactTitle": "D" },
        { "tileIndex": 2, "title": "Billing", "shortTitle": "Billing", "compactTitle": "B" },
        { "tileIndex": 3, "title": "Finance", "shortTitle": "Finance", "compactTitle": "F" }
    ]

    signal submitRequested(var state)
    signal cancelRequested(var state)
    signal tearAwayRequested(var state)
    signal moduleJumpRequested(int tileIndex, var state)
    signal workspaceOpenRequested(int tileIndex, string nodeId, var state)
    signal reportWindowRequested(var reportDocument)

    function contentW() {
        if (metrics && typeof metrics.contentW === "number") return Math.max(1, metrics.contentW)
        return Math.max(1, root.width)
    }

    function contentH() {
        if (metrics && typeof metrics.contentH === "number") return Math.max(1, metrics.contentH)
        return Math.max(1, root.height)
    }

    function areaUnit() {
        return Math.sqrt(contentW() * contentH())
    }

    function areaFloorPx(ratio, fallbackPx) {
        var floorPx = (typeof fallbackPx === "number") ? fallbackPx : 1
        return Math.max(floorPx, Math.round(areaUnit() * ratio))
    }

    // Area-based metrics payload for child controls; independent of OS DPI scaling.
    property var responsiveMetrics: ({
        "contentW": contentW(),
        "contentH": contentH(),
        "scalePercent": (metrics && typeof metrics.scalePercent === "number") ? metrics.scalePercent : 100,
        "fontFloorTitlePx": areaFloorPx(0.0130, 12),
        "fontFloorIconPx": areaFloorPx(0.0120, 11),
        "fontFloorBodyPx": areaFloorPx(0.0109, 9),
        "fontFloorLabelPx": areaFloorPx(0.0098, 8)
    })

    function ratioPx(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(areaUnit() * ratio))
    }

    function ratioPxW(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        var numericRatio = Number(ratio)
        if (!isFinite(numericRatio) || numericRatio <= 0) {
            return Math.max(floorPx, 1)
        }
        // ratioPxW expects 0..1 ratios. If a fixed pixel value is accidentally
        // passed, treat it as pixels instead of multiplying by the window width.
        if (numericRatio > 1) {
            return Math.max(floorPx, Math.round(numericRatio))
        }
        return Math.max(floorPx, Math.round(contentW() * numericRatio))
    }

    function ratioPxH(ratio, minPx) {
        var floorPx = (typeof minPx === "number") ? minPx : 1
        return Math.max(floorPx, Math.round(contentH() * ratio))
    }

    function metricFloor(metricKey, fallbackPx) {
        if (responsiveMetrics && typeof responsiveMetrics[metricKey] === "number") {
            return Math.max(1, Math.round(responsiveMetrics[metricKey]))
        }
        if (metrics && typeof metrics[metricKey] === "number") {
            return Math.max(1, Math.round(metrics[metricKey]))
        }
        return Math.max(1, Math.round(fallbackPx))
    }

    function readableMinFontPx() {
        return root.metricFloor("fontFloorLabelPx", 8)
    }

    function formGridColumns(preferredColumns, availableWidth) {
        var desired = Math.max(1, Math.round(Number(preferredColumns || 1)))
        var fallbackWidth = Math.max(1, Math.round(Number(root.contentW() || root.width || 1)))
        var rawWidth = Number(availableWidth || fallbackWidth)
        if (!isFinite(rawWidth) || rawWidth <= 0) rawWidth = fallbackWidth
        var usableWidth = Math.max(1, Math.min(Math.round(rawWidth), fallbackWidth))
        var gap = root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
        var maxByWidth = Math.max(1, Math.floor((usableWidth + gap) / (root.formFieldMinimumWidthPx + gap)))
        return Math.max(1, Math.min(desired, maxByWidth))
    }

    function formGridLayoutWidth(gridItem) {
        var fallbackWidth = Math.max(1, Math.round(Number(root.contentW() || root.width || 1)))
        var candidate = fallbackWidth
        if (gridItem && gridItem.parent && typeof gridItem.parent.width === "number" && gridItem.parent.width > 1) {
            candidate = Number(gridItem.parent.width)
        } else if (gridItem && typeof gridItem.width === "number" && gridItem.width > 1) {
            candidate = Number(gridItem.width)
        }
        if (!isFinite(candidate) || candidate <= 0) candidate = fallbackWidth
        return Math.max(1, Math.min(Math.round(candidate), fallbackWidth))
    }

    function formGridSpan(columnCount, desiredSpan) {
        return Math.max(1, Math.min(Math.max(1, Number(columnCount || 1)), Math.max(1, Number(desiredSpan || 1))))
    }

// === SIDEBAR HOVER HELPERS (fix.py) ===
function sidebarHoverBlendFactor(hovered) {
    if (root.lightTheme) {
        return hovered ? 0.40 : 0.14
    }
    return hovered ? 0.58 : 0.20
}
function sidebarHoverFill(active, hovered, activeAlpha, hoverAlpha, idleAlpha) {
    if (root.isProMode) {
        return active ? root.proHoverFill : (hovered ? root.proSurface : "transparent")
    }
    if (active) {
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, activeAlpha)
    }
    var mixFactor = root.sidebarHoverBlendFactor(hovered)
    return Qt.rgba(
        (root._panel.r * (1.0 - mixFactor)) + (root._accent.r * mixFactor),
        (root._panel.g * (1.0 - mixFactor)) + (root._accent.g * mixFactor),
        (root._panel.b * (1.0 - mixFactor)) + (root._accent.b * mixFactor),
        hovered ? hoverAlpha : idleAlpha
    )
}
function sidebarHoverBorder(active, hovered, activeAlpha, hoverAlpha, idleAlpha) {
    if (root.isProMode) {
        return active ? root.proActiveBorder : (hovered ? root.proBorder : "transparent")
    }
    if (active) {
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, activeAlpha)
    }
    if (hovered) {
        return Qt.rgba(root._accent.r, root._accent.g, root._accent.b, hoverAlpha)
    }
    return Qt.rgba(root._text.r, root._text.g, root._text.b, idleAlpha)
}

    property int sectionRadiusPx: root.isProMode ? visualRules.radiusPanel : root.ratioPx(root.scaleRatios.descCornerPct, 10)
    property int fieldHeightPx: root.ratioPxH(0.060, 44)
    property int controlGapPx: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.pageSpacingPct * 0.72, 6)
    property int formFieldMinimumWidthPx: root.ratioPx(0.180, 176)

    function themeBucket() {
        if (_accent.g >= _accent.r && _accent.g >= _accent.b) return "emerald"
        if (_accent.b >= _accent.r && _accent.b >= _accent.g) return "sapphire"
        return "crimson"
    }

    function themeBackgroundSource() {
        return Qt.resolvedUrl("../../../assets/home_skyline_bw.png")
    }

    function backgroundColorizationStrength() {
        if (root.lightTheme) return 0.06
        var bucket = themeBucket()
        if (bucket === "sapphire") return 0.18
        if (bucket === "emerald") return 0.17
        return 0.20
    }

    function normalizedNavItems() {
        if (root.navItems && root.navItems.length !== undefined && root.navItems.length > 0) {
            return root.navItems
        }
        return [
            { "id": "P00", "title": "Placeholder Node" }
        ]
    }

    function searchNavItemsList() {
        if (root.allNavItems && root.allNavItems.length !== undefined && root.allNavItems.length > 0) {
            return root.allNavItems
        }
        return normalizedNavItems()
    }

    function currentNode() {
        var list = searchNavItemsList()
        for (var i = 0; i < list.length; i++) {
            var row = list[i]
            if (String(row.id || "") === String(root.activeNodeId || "")) {
                return row
            }
        }
        if (list.length > 0) return list[0]
        return { "id": "", "title": "Placeholder Node" }
    }

    function nodeTitleForId(nodeId) {
        var wanted = String(nodeId || "")
        var list = searchNavItemsList()
        for (var i = 0; i < list.length; i++) {
            var row = list[i]
            if (String(row.id || "") === wanted) {
                return String(row.title || row.label || wanted)
            }
        }
        return wanted
    }

    function nodeIndexForId(nodeId) {
        var wanted = String(nodeId || "")
        var list = searchNavItemsList()
        for (var i = 0; i < list.length; i++) {
            if (String(list[i].id || "") === wanted) {
                return i
            }
        }
        return -1
    }

    function ensureActiveNode() {
        var list = searchNavItemsList()
        if (list.length <= 0) {
            activeNodeId = ""
            return
        }
        var candidate = String(activeNodeId || "").trim()
        if (candidate.length <= 0) {
            candidate = String(defaultNodeId || "").trim()
        }
        if (candidate.length <= 0) {
            candidate = String(list[0].id || "")
        }
        var found = false
        for (var i = 0; i < list.length; i++) {
            if (String(list[i].id || "") === candidate) {
                found = true
                break
            }
        }
        if (!found) {
            candidate = String(list[0].id || "")
        }
        activeNodeId = candidate
    }

    function summaryLineA() {
        return laneSummary && laneSummary.lineA ? String(laneSummary.lineA) : "Module pathway placeholder active"
    }

    function summaryLineB() {
        return laneSummary && laneSummary.lineB ? String(laneSummary.lineB) : "Wire data handlers as backend entities land"
    }

    function summaryHeadline() {
        return laneSummary && laneSummary.headline ? String(laneSummary.headline) : "At a glance: placeholder"
    }

    function activeIsNewClientWizard() {
        return String(currentNode().id || "") === "A02"
    }

    function activeIsClientDirectory() {
        return String(currentNode().id || "") === "A01"
    }

    function activeIsClientProfile360() {
        return String(currentNode().id || "") === "A03"
    }

    function activeIsMatterDirectory() {
        return String(currentNode().id || "") === "A09"
    }

    function activeIsNewMatterWizard() {
        return String(currentNode().id || "") === "A10"
    }

    function activeIsMatterProfile360() {
        return String(currentNode().id || "") === "A11"
    }

    function activeIsGlobalSearch() {
        return String(currentNode().id || "") === "X01"
    }

    function activeIsTransactionsMaster() {
        return String(currentNode().id || "") === "C11"
    }

    function activeIsPaymentEntry() {
        var nid = String(currentNode().id || "")
        return nid === "C07" || nid === "C09"
    }

    function activeIsWipToBill() {
        var nid = String(currentNode().id || "")
        return nid === "C01" || nid === "C05"
    }

    function activeIsInvoiceBuilder() {
        var nid = String(currentNode().id || "")
        return nid === "C03" || nid === "C06"
    }

    function activeIsInvoiceReversal() {
        return String(currentNode().id || "") === "C08"
    }

    function activeIsInvoiceDirectory() {
        return String(currentNode().id || "") === "C04"
    }

    function activeIsAccountsPayable() {
        var nid = String(currentNode().id || "")
        return nid === "C18" || nid === "B18"
    }

    function initialInvoiceDraftNumber() {
        if (!root.activeIsInvoiceBuilder()) return ""
        var state = root.initialState
        if (!state || typeof state !== "object") return ""
        var keys = ["draftNum", "draftId", "invoiceDraftId"]
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i]
            if (state[key] === undefined || state[key] === null) continue
            var value = String(state[key] || "").trim()
            if (value.length > 0) return value
        }
        return ""
    }

    function initialInvoiceNumber() {
        if (!root.activeIsInvoiceReversal() && !root.activeIsInvoiceDirectory()) return ""
        var state = root.initialState
        if (!state || typeof state !== "object") return ""
        var keys = ["selectedInvoiceNum", "invoiceNum", "entityId", "invoiceId"]
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i]
            if (state[key] === undefined || state[key] === null) continue
            var value = String(state[key] || "").trim()
            if (value.length > 0) return value
        }
        return ""
    }

    function activeIsFinancialDashboard() {
        return String(currentNode().id || "") === "D01"
    }

    function activeIsARAgingReport() {
        return String(currentNode().id || "") === "D06"
    }

    function activeIsDocketActivityReport() {
        return String(currentNode().id || "") === "B04"
    }

    function activeIsProductivityDashboard() {
        return String(currentNode().id || "") === "D10"
    }

    function activeIsLegacyDocketsImport() {
        return String(currentNode().id || "") === "X13"
    }

    function activeIsClientLedgerReport() {
        return String(currentNode().id || "") === "D07"
    }

    function activeIsMatterTimeLedger() {
        return String(currentNode().id || "") === "D18"
    }

    function activeIsLedgerReport() {
        return root.activeIsClientLedgerReport() || root.activeIsMatterTimeLedger()
    }

    function activeIsStatementOfAccount() {
        return String(currentNode().id || "") === "D17"
    }

    function activeIsCorporateDirectory() {
        return String(currentNode().id || "") === "A21"
    }

    function activeIsCorporateProfile() {
        return String(currentNode().id || "") === "A22"
    }

    function activeIsCorporateTransactionWizard() {
        return String(currentNode().id || "") === "A23"
    }

    function _cleanLowerText(value) {
        return String(value === undefined || value === null ? "" : value).trim().toLowerCase()
    }

    function _dedupeSortedTextOptions(values) {
        var out = []
        var seen = ({})
        if (!values || values.length === undefined) return out
        for (var i = 0; i < values.length; i++) {
            var text = String(values[i] || "").trim()
            if (text.length <= 0) continue
            var key = text.toLowerCase()
            if (seen[key]) continue
            seen[key] = true
            out.push(text)
        }
        out.sort(function(a, b) { return String(a).localeCompare(String(b)) })
        return out
    }

    function _parentClientOptionsWithBlank(values) {
        var sorted = _dedupeSortedTextOptions(values)
        var out = [""]
        for (var i = 0; i < sorted.length; i++) out.push(sorted[i])
        return out
    }

    function _searchTerms(value) {
        var text = _cleanLowerText(value)
        if (text.length <= 0) return []
        var raw = text.match(/[a-z0-9@._:/#-]+/g)
        if (!raw || raw.length <= 0) return []
        var out = []
        var seen = ({})
        for (var i = 0; i < raw.length; i++) {
            var token = String(raw[i] || "").replace(/^[\s._,-]+|[\s._,-]+$/g, "")
            if (token.length <= 0) continue
            if (seen[token]) continue
            seen[token] = true
            out.push(token)
        }
        return out
    }

    function _rowValueJoinedLower(row) {
        if (!row || typeof row !== "object") return ""
        var chunks = []
        for (var key in row) {
            if (!row.hasOwnProperty(key)) continue
            var value = row[key]
            if (value === undefined || value === null) continue
            var text = String(value).trim()
            if (text.length > 0) chunks.push(text.toLowerCase())
        }
        return chunks.join(" ")
    }

    function _clientDirectorySearchText(row) {
        if (!row || typeof row !== "object") return ""
        // Directory search is intentionally restricted to the client's own
        // identity/contact fields.  `searchText` includes operational notes and
        // the billing parent, which made a parent-name search return every
        // client attached to that parent instead of the named client.
        var fields = [
            "clientId", "clientName", "displayName", "legalName",
            "firstName", "middleName", "lastName", "primaryEmail", "primaryPhone"
        ]
        var chunks = []
        for (var i = 0; i < fields.length; i++) {
            var value = row[fields[i]]
            if (value === undefined || value === null) continue
            var text = String(value).trim()
            if (text.length > 0) chunks.push(text.toLowerCase())
        }
        return chunks.join(" ")
    }

    function entityTypeIsIndividual() {
        return _cleanLowerText(entityTypeCombo.editText) === "individual"
    }

    function splitIndividualNameParts(textValue) {
        var text = String(textValue || "").replace(/\s+/g, " ").trim()
        if (text.length <= 0) return { "first": "", "middle": "", "last": "" }
        var commaIndex = text.indexOf(",")
        if (commaIndex > 0) {
            var last = text.slice(0, commaIndex).replace(/\s+/g, " ").trim()
            var given = text.slice(commaIndex + 1).replace(/\s+/g, " ").trim().split(/\s+/)
            if (last.length > 0 && given.length > 0 && given[0].length > 0) {
                return {
                    "first": given[0],
                    "middle": given.slice(1).join(" "),
                    "last": last
                }
            }
        }
        var parts = text.split(/\s+/)
        if (parts.length === 1) return { "first": parts[0], "middle": "", "last": "" }
        if (parts.length === 2) return { "first": parts[0], "middle": "", "last": parts[1] }
        return { "first": parts[0], "middle": parts.slice(1, parts.length - 1).join(" "), "last": parts[parts.length - 1] }
    }

    function individualFullNameFromInputs() {
        if (!individualNameFieldsReady) return ""
        var parts = [
            String(firstNameInput.text || "").trim(),
            String(middleNameInput.text || "").trim(),
            String(lastNameInput.text || "").trim()
        ]
        var out = []
        for (var i = 0; i < parts.length; i++) {
            if (parts[i].length > 0) out.push(parts[i])
        }
        return out.join(" ")
    }

    function syncIndividualNamePartsFromDisplay(clientName) {
        if (!individualNameFieldsReady || !entityTypeIsIndividual() || !root.individualNameAutoSync) return
        var parts = splitIndividualNameParts(clientName)
        _setTextFieldSilently(firstNameInput, parts.first)
        _setTextFieldSilently(middleNameInput, parts.middle)
        _setTextFieldSilently(lastNameInput, parts.last)
    }

    function syncIndividualDisplayFromParts() {
        if (!individualNameFieldsReady || !entityTypeIsIndividual() || root._hydrating || root._autoFieldMutation) return
        var fullName = individualFullNameFromInputs()
        if (fullName.length <= 0) return
        if (root.individualNameAutoSync || String(clientNameInput.text || "").trim().length <= 0) {
            _setTextFieldSilently(clientNameInput, fullName)
        }
        if (root.legalNameAutoSync) {
            _setTextFieldSilently(legalNameInput, fullName)
        }
        if (root.principalNameAutoSync) {
            _setTextFieldSilently(principalNameInput, fullName)
        }
    }

    function _setTextFieldSilently(fieldRef, textValue) {
        if (!fieldRef) return
        var nextText = String(textValue === undefined || textValue === null ? "" : textValue)
        if (String(fieldRef.text || "") === nextText) return
        root._autoFieldMutation = true
        fieldRef.text = nextText
        root._autoFieldMutation = false
    }

    function _setComboBoxSilently(comboRef, textValue) {
        if (!comboRef) return
        var nextText = String(textValue === undefined || textValue === null ? "" : textValue)
        if (String(comboRef.editText || "") === nextText) return
        root._autoFieldMutation = true
        comboRef.editText = nextText
        var idx = comboRef.find(nextText)
        if (idx >= 0) comboRef.currentIndex = idx
        root._autoFieldMutation = false
    }

    function _parseIsoDateOrToday(textValue) {
        var text = String(textValue || "").trim()
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
        if (match) {
            var year = Number(match[1])
            var monthIndex = Number(match[2]) - 1
            var day = Number(match[3])
            var candidate = new Date(year, monthIndex, day)
            if (candidate.getFullYear() === year
                && candidate.getMonth() === monthIndex
                && candidate.getDate() === day) {
                return candidate
            }
        }
        return new Date()
    }

    function openClientWizardDatePicker(targetKey, existingText, px, py) {
        clientWizardDateTarget = String(targetKey || "")
        clientWizardCalendar.selectedDate = _parseIsoDateOrToday(existingText)
        clientWizardCalendar.openAt(px, py)
    }

    function refreshAutoSyncFlags() {
        var clientNameLower = _cleanLowerText(clientNameInput.text)
        var legalNameLower = _cleanLowerText(legalNameInput.text)
        var principalNameLower = _cleanLowerText(principalNameInput.text)
        var primaryEmailLower = _cleanLowerText(primaryEmailInput.text)
        var billingEmailLower = _cleanLowerText(billingEmailInput.text)

        root.legalNameAutoSync = legalNameLower.length <= 0 || legalNameLower === clientNameLower
        if (individualNameFieldsReady) {
            var splitParts = splitIndividualNameParts(clientNameInput.text)
            var firstNameLower = _cleanLowerText(firstNameInput.text)
            var middleNameLower = _cleanLowerText(middleNameInput.text)
            var lastNameLower = _cleanLowerText(lastNameInput.text)
            root.individualNameAutoSync = (firstNameLower.length <= 0 && middleNameLower.length <= 0 && lastNameLower.length <= 0)
                || (firstNameLower === _cleanLowerText(splitParts.first)
                    && middleNameLower === _cleanLowerText(splitParts.middle)
                    && lastNameLower === _cleanLowerText(splitParts.last))
        }
        root.principalNameAutoSync = principalNameLower.length <= 0 || principalNameLower === clientNameLower
        root.billingEmailAutoSync = billingEmailLower.length <= 0 || billingEmailLower === primaryEmailLower
    }

    function refreshMatterAutoSyncFlags() {
        var matterNameLower = _cleanLowerText(matterNameInput ? matterNameInput.text : "")
        var displayNameLower = _cleanLowerText(matterDisplayNameInput ? matterDisplayNameInput.text : "")
        root.matterDisplayNameAutoSync = displayNameLower.length <= 0 || displayNameLower === matterNameLower
    }

    function matterBillingArrangementIsFlatFee() {
        return _cleanLowerText(matterBillingArrangementCombo ? matterBillingArrangementCombo.editText : "") === "flat fee"
    }

    function applyClientWizardAutoPopulate() {
        if (root._hydrating) return
        var clientName = String(clientNameInput.text || "").trim()
        var primaryEmail = String(primaryEmailInput.text || "").trim()
        if (clientName.length > 0) {
            syncIndividualNamePartsFromDisplay(clientName)
        }
        if (root.principalNameAutoSync && entityTypeIsIndividual() && clientName.length > 0) {
            _setTextFieldSilently(principalNameInput, clientName)
        }
        if (root.billingEmailAutoSync && primaryEmail.length > 0) {
            _setTextFieldSilently(billingEmailInput, primaryEmail)
        }
    }

    function _phoneDigits(textValue) {
        return String(textValue || "").replace(/\D/g, "")
    }

    function _normalizeUsPhone(textValue) {
        var raw = String(textValue || "").trim()
        var digits = _phoneDigits(raw)
        if (digits.length === 11 && digits.charAt(0) === "1") {
            digits = digits.slice(1)
        }
        if (digits.length !== 10) {
            return {
                "valid": false,
                "formatted": raw,
                "digits": digits
            }
        }
        return {
            "valid": true,
            "formatted": digits.slice(0, 3) + "-" + digits.slice(3, 6) + "-" + digits.slice(6),
            "digits": digits
        }
    }

    function _formatPhoneForDisplay(textValue) {
        var raw = String(textValue || "").trim()
        if (raw.length <= 0) return ""
        var digits = _phoneDigits(raw)
        if (digits.length <= 0) return ""
        var normalized = _normalizeUsPhone(raw)
        return normalized.valid ? normalized.formatted : raw
    }

    function _formatPhoneField(fieldRef) {
        if (!fieldRef) return false
        var currentText = String(fieldRef.text || "").trim()
        if (currentText.length <= 0) return false
        var normalized = _normalizeUsPhone(currentText)
        if (!normalized.valid) return false
        if (String(normalized.formatted) === currentText) return false
        _setTextFieldSilently(fieldRef, normalized.formatted)
        if (!root._hydrating) root.dirty = true
        return true
    }

    function normalizeClientWizardPhoneFields() {
        _formatPhoneField(primaryPhoneInput)
        _formatPhoneField(secondaryPhoneInput)
    }

    function _looksLikeEmailAddress(textValue) {
        var email = String(textValue || "").trim()
        if (email.length <= 0) return true
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
    }

    function collectClientWizardValidationIssues() {
        var issues = []
        var phoneChecks = [
            { "label": "Primary Phone", "value": primaryPhoneInput.text },
            { "label": "Secondary Phone", "value": secondaryPhoneInput.text }
        ]
        for (var i = 0; i < phoneChecks.length; i++) {
            var phoneValue = String(phoneChecks[i].value || "").trim()
            if (phoneValue.length <= 0) continue
            var normalizedPhone = _normalizeUsPhone(phoneValue)
            if (!normalizedPhone.valid) {
                issues.push(phoneChecks[i].label + " must use 10 digits (xxx-xxx-xxxx).")
            }
        }

        var emailChecks = [
            { "label": "Primary Email", "value": primaryEmailInput.text },
            { "label": "Secondary Email", "value": secondaryEmailInput.text },
            { "label": "Billing Email", "value": billingEmailInput.text }
        ]
        for (var j = 0; j < emailChecks.length; j++) {
            var emailValue = String(emailChecks[j].value || "").trim()
            if (emailValue.length <= 0) continue
            if (!_looksLikeEmailAddress(emailValue)) {
                issues.push(emailChecks[j].label + " is not in a valid email format.")
            }
        }
        return issues
    }

    function _validationIssueSummary(issues) {
        if (!issues || issues.length <= 0) return ""
        var lines = []
        for (var i = 0; i < issues.length; i++) {
            lines.push("- " + String(issues[i] || ""))
        }
        return lines.join("\n")
    }

    function clientRowIsActive(row) {
        var statusText = _cleanLowerText(row && row.status !== undefined ? row.status : "")
        var activeNum = Number(row && row.active !== undefined ? row.active : 1)
        var activeFlag = isFinite(activeNum) ? activeNum !== 0 : true
        return activeFlag && statusText !== "inactive" && statusText !== "closed" && statusText !== "archived"
    }

    function rebuildClientDirectoryFilteredRows() {
        var rows = clientDirectoryRows && clientDirectoryRows.length !== undefined ? clientDirectoryRows : []
        var query = _cleanLowerText(clientDirectoryQuery)
        var terms = _searchTerms(clientDirectoryQuery)
        var activeOnly = _cleanLowerText(clientDirectoryMode) === "active"
        var filtered = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue
            if (activeOnly && !clientRowIsActive(row)) continue
            if (query.length > 0) {
                var haystack = _clientDirectorySearchText(row)
                var matched = true
                if (terms.length > 0) {
                    for (var tIdx = 0; tIdx < terms.length; tIdx++) {
                        if (haystack.indexOf(String(terms[tIdx] || "")) < 0) {
                            matched = false
                            break
                        }
                    }
                } else {
                    matched = haystack.indexOf(query) >= 0
                }
                if (!matched) continue
            }
            filtered.push(row)
        }
        clientDirectoryFilteredRows = filtered
    }

    function _rebuildClientDirectoryNameOptions() {
        var rows = clientDirectoryRows && clientDirectoryRows.length !== undefined ? clientDirectoryRows : []
        var seen = ({})
        var names = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue
            var name = String(row.clientName || row.displayName || "").trim()
            if (name.length <= 0) continue
            var key = name.toLowerCase()
            if (seen[key]) continue
            seen[key] = true
            names.push(name)
        }
        names.sort(function(a, b) { return String(a).localeCompare(String(b)) })
        clientDirectoryNameOptions = names
    }

    function setDirectorySelection(row) {
        if (!row) return
        selectedClientId = String(row.clientId || "")
        selectedClientName = String(row.clientName || row.displayName || "")
    }

    function clientProfileStateForDirectoryRow(row) {
        var clientId = String(row && row.clientId !== undefined ? row.clientId : "").trim()
        var clientTitle = String(row && row.displayName !== undefined ? row.displayName : "").trim()
        if (clientTitle.length <= 0) clientTitle = String(row && row.clientName !== undefined ? row.clientName : "").trim()
        if (clientTitle.length <= 0) clientTitle = clientId

        var state = snapshotState()
        state.focusNodeId = "A03"
        state.focusNodeTitle = nodeTitleForId("A03")
        state.selectedClientId = clientId
        state.selectedClientName = clientTitle
        state.clientProfileAutoLoadKey = clientId.length > 0 ? clientId : clientTitle
        state.autoLoadClientProfile = true
        state.clientDirectoryQueryText = clientTitle
        state.clientDirectoryModeText = clientDirectoryMode
        state.option3EntityType = "client"
        state.option3EntityId = clientId.length > 0 ? clientId : clientTitle
        state.option3EntityTitle = clientTitle
        state.dirty = false
        return state
    }

    function refreshClientDirectory(activeOnlyMode) {
        var rows = []
        try {
            if (appRef && appRef.listClientDirectory) {
                rows = appRef.listClientDirectory()
            } else if (appRef && appRef.listClientNames) {
                var names = appRef.listClientNames()
                for (var i = 0; i < names.length; i++) {
                    rows.push({
                        "clientId": "",
                        "clientName": String(names[i] || ""),
                        "displayName": String(names[i] || ""),
                        "status": "Active",
                        "active": 1,
                        "primaryEmail": "",
                        "primaryPhone": "",
                        "entityType": ""
                    })
                }
            }
        } catch (e) {
            rows = []
        }

        clientDirectoryRows = rows && rows.length !== undefined ? rows : []
        _rebuildClientDirectoryNameOptions()

        if (activeOnlyMode === true) {
            clientDirectoryMode = "active"
        }
        rebuildClientDirectoryFilteredRows()

        if (clientDirectoryFilteredRows.length > 0) {
            var matched = false
            for (var r = 0; r < clientDirectoryFilteredRows.length; r++) {
                var row = clientDirectoryFilteredRows[r]
                var rid = String(row.clientId || "")
                var rname = String(row.clientName || row.displayName || "")
                if ((selectedClientId.length > 0 && rid === selectedClientId)
                    || (selectedClientId.length <= 0 && selectedClientName.length > 0 && rname === selectedClientName)) {
                    matched = true
                    break
                }
            }
            if (!matched) {
                setDirectorySelection(clientDirectoryFilteredRows[0])
            }
        } else {
            selectedClientId = ""
            if (selectedClientName.length > 0 && activeOnlyMode === true) {
                selectedClientName = ""
            }
        }
        refreshMatterWizardClientOptions()
    }

    function matterRowIsActive(row) {
        var statusText = _cleanLowerText(row && row.status !== undefined ? row.status : "")
        var activeNum = Number(row && row.active !== undefined ? row.active : 1)
        var activeFlag = isFinite(activeNum) ? activeNum !== 0 : true
        return activeFlag && statusText !== "inactive" && statusText !== "closed" && statusText !== "archived"
    }

    function rebuildMatterDirectoryFilteredRows() {
        var rows = matterDirectoryRows && matterDirectoryRows.length !== undefined ? matterDirectoryRows : []
        var query = _cleanLowerText(matterDirectoryQuery)
        var terms = _searchTerms(matterDirectoryQuery)
        var activeOnly = _cleanLowerText(matterDirectoryMode) === "active"
        var filtered = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue
            if (activeOnly && !matterRowIsActive(row)) continue
            if (query.length > 0) {
                var haystack = _rowValueJoinedLower(row)
                var matched = true
                if (terms.length > 0) {
                    for (var tIdx = 0; tIdx < terms.length; tIdx++) {
                        if (haystack.indexOf(String(terms[tIdx] || "")) < 0) {
                            matched = false
                            break
                        }
                    }
                } else {
                    matched = haystack.indexOf(query) >= 0
                }
                if (!matched) continue
            }
            filtered.push(row)
        }
        filtered.sort(function(a, b) {
            var numA = String(a.matterNumber || "").toLowerCase()
            var numB = String(b.matterNumber || "").toLowerCase()
            if (numA < numB) return -1
            if (numA > numB) return 1

            var clientA = String(a.clientName || "").toLowerCase()
            var clientB = String(b.clientName || "").toLowerCase()
            if (clientA < clientB) return -1
            if (clientA > clientB) return 1

            var nameA = String(a.displayName || a.matterName || "").toLowerCase()
            var nameB = String(b.displayName || b.matterName || "").toLowerCase()
            if (nameA < nameB) return -1
            if (nameA > nameB) return 1

            var statA = String(a.status || "").toLowerCase()
            var statB = String(b.status || "").toLowerCase()
            if (statA < statB) return -1
            if (statA > statB) return 1

            return 0
        })
        matterDirectoryFilteredRows = filtered
    }

    function matterDocketDisplayLabel(row) {
        var src = row || ({})
        var matterNumber = String(src.matterNumber || "").trim()
        var matterName = String(src.matterName || src.displayName || "").trim()

        if (matterNumber.length > 0 && matterName.length > 0) {
            return matterNumber + " - " + matterName
        }
        if (matterNumber.length > 0) return matterNumber
        return matterName
    }

    function matterDirectoryOptionLabel(row) {
        var src = row || ({})
        var docketLabel = root.matterDocketDisplayLabel(src)
        var clientName = String(src.clientName || "").trim()

        if (docketLabel.length <= 0) {
            docketLabel = String(src.displayName || src.matterName || src.matterId || "").trim()
        }

        // Important: do not show only "Legacy Unassigned - Review Required".
        // Many imported matters share that same name. Include matter number and client.
        if (clientName.length > 0) {
            return docketLabel + " — " + clientName
        }
        return docketLabel
    }

    function resolveMatterDirectoryRowByKey(rawKey) {
        var key = String(rawKey || "").trim()
        var keyLower = key.toLowerCase()
        var rows = matterDirectoryRows && matterDirectoryRows.length !== undefined ? matterDirectoryRows : []

        if (keyLower.length <= 0 && selectedMatterId.length > 0) {
            keyLower = String(selectedMatterId || "").trim().toLowerCase()
        }

        function score(row) {
            if (!row) return -1

            var matterId = String(row.matterId || "").trim()
            var matterNumber = String(row.matterNumber || "").trim()
            var matterName = String(row.matterName || "").trim()
            var displayName = String(row.displayName || "").trim()
            var optionLabel = root.matterDirectoryOptionLabel(row)
            var docketLabel = root.matterDocketDisplayLabel(row)

            var matterIdLower = matterId.toLowerCase()
            var matterNumberLower = matterNumber.toLowerCase()
            var matterNameLower = matterName.toLowerCase()
            var displayNameLower = displayName.toLowerCase()
            var optionLabelLower = optionLabel.toLowerCase()
            var docketLabelLower = docketLabel.toLowerCase()

            if (keyLower.length <= 0) return -1
            if (matterIdLower.length > 0 && keyLower === matterIdLower) return 1000
            if (matterNumberLower.length > 0 && keyLower === matterNumberLower) return 950
            if (optionLabelLower.length > 0 && keyLower === optionLabelLower) return 900
            if (docketLabelLower.length > 0 && keyLower === docketLabelLower) return 850
            if (matterNumberLower.length > 0 && keyLower.indexOf(matterNumberLower) === 0) return 800
            if (optionLabelLower.length > 0 && optionLabelLower.indexOf(keyLower) >= 0) return 500
            if (docketLabelLower.length > 0 && docketLabelLower.indexOf(keyLower) >= 0) return 450
            if (displayNameLower.length > 0 && keyLower === displayNameLower) return 250
            if (matterNameLower.length > 0 && keyLower === matterNameLower) return 200
            return -1
        }

        var best = null
        var bestScore = -1
        var tied = false

        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            var s = score(row)
            if (s > bestScore) {
                best = row
                bestScore = s
                tied = false
            } else if (s === bestScore && s >= 0) {
                tied = true
            }
        }

        // If the only match is an ambiguous duplicate matter name, do not guess.
        if (tied && bestScore <= 250) {
            return ({})
        }

        return best || ({})
    }

    function _rebuildMatterDirectoryNameOptions() {
        var rows = matterDirectoryRows && matterDirectoryRows.length !== undefined ? matterDirectoryRows : []
        var seen = ({})
        var names = []

        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue

            var name = root.matterDirectoryOptionLabel(row)
            if (name.length <= 0) continue

            var key = name.toLowerCase()
            if (seen[key]) continue
            seen[key] = true
            names.push(name)
        }

        names.sort(function(a, b) { return String(a).localeCompare(String(b)) })
        matterDirectoryNameOptions = names
    }

    function setMatterDirectorySelection(row) {
        if (!row) return
        selectedMatterId = String(row.matterId || "")
        selectedMatterName = root.matterDirectoryOptionLabel(row)
    }

    function matterProfileStateForDirectoryRow(row) {
        var matterId = String(row && row.matterId !== undefined ? row.matterId : "").trim()
        var matterNumber = String(row && row.matterNumber !== undefined ? row.matterNumber : "").trim()
        var matterTitle = root.matterDirectoryOptionLabel(row || ({}))
        if (matterTitle.length <= 0) matterTitle = matterNumber.length > 0 ? matterNumber : matterId

        var state = snapshotState()
        state.focusNodeId = "A11"
        state.focusNodeTitle = nodeTitleForId("A11")
        state.selectedMatterId = matterId
        state.selectedMatterName = matterTitle
        state.matterDirectoryQueryText = matterTitle
        state.matterDirectoryModeText = matterDirectoryMode
        state.option3EntityType = "matter"
        state.option3EntityId = matterId.length > 0 ? matterId : (matterNumber.length > 0 ? matterNumber : matterTitle)
        state.option3EntityTitle = matterTitle
        state.dirty = false
        return state
    }

    function refreshMatterWizardClientOptions() {
        var names = []
        try {
            if (appRef && appRef.listClientNames) {
                var loaded = appRef.listClientNames()
                if (loaded && loaded.length !== undefined) {
                    for (var i = 0; i < loaded.length; i++) {
                        var name = String(loaded[i] || "").trim()
                        if (name.length > 0) names.push(name)
                    }
                }
            }
        } catch (e0) {
        }
        if (names.length <= 0 && clientDirectoryNameOptions && clientDirectoryNameOptions.length !== undefined) {
            for (var j = 0; j < clientDirectoryNameOptions.length; j++) {
                var fallbackName = String(clientDirectoryNameOptions[j] || "").trim()
                if (fallbackName.length > 0) names.push(fallbackName)
            }
        }
        matterClientOptions = _matterClientOptionsWithNewClient(names)
    }

    function _isNewClientOption(value) {
        var text = _cleanLowerText(value)
        return text.length > 0 && text === _cleanLowerText(root.newClientOptionLabel)
    }

    function _matterClientOptionsWithNewClient(names) {
        var sorted = _dedupeSortedTextOptions(names)
        var options = [""]
        for (var i = 0; i < sorted.length; i++) {
            var optionText = String(sorted[i] || "").trim()
            if (optionText.length <= 0 || _isNewClientOption(optionText)) continue
            options.push(optionText)
        }
        options.push(root.newClientOptionLabel)
        return options
    }

    function refreshLawyerOptions() {
        var names = [""]
        try {
            if (appRef && appRef.listFirmLawyers) {
                var loaded = appRef.listFirmLawyers()
                if (loaded && loaded.length !== undefined) {
                    for (var i = 0; i < loaded.length; i++) {
                        var name = String(loaded[i] || "").trim()
                        if (name.length > 0) names.push(name)
                    }
                }
            }
        } catch (e) {
        }
        lawyerOptions = names
    }

    function _matterWizardClientName() {
        var clientName = String(matterClientCombo.editText || "").trim()
        return _isNewClientOption(clientName) ? "" : clientName
    }

    function _matterPartyIndexByName(clientName) {
        var wanted = String(clientName || "").trim().toLowerCase()
        for (var i = 0; i < matterParties.length; i++) {
            if (String(matterParties[i].clientName || "").trim().toLowerCase() === wanted) return i
        }
        return -1
    }

    function addMatterParty(clientName, fileAnchor) {
        var name = String(clientName || "").trim()
        if (name.length <= 0 || _isNewClientOption(name)) return false
        var next = matterParties.slice(0)
        var existing = _matterPartyIndexByName(name)
        if (existing >= 0) {
            if (fileAnchor) {
                for (var i = 0; i < next.length; i++) next[i].isFileAnchor = i === existing
                matterParties = next
            }
            return false
        }
        if (fileAnchor) {
            for (var j = 0; j < next.length; j++) next[j].isFileAnchor = false
        }
        next.push({
            "clientName": name,
            "role": "Joint client",
            "isFileAnchor": !!fileAnchor || next.length === 0,
            "isBillingRecipient": true,
            "notes": ""
        })
        matterParties = next
        return true
    }

    function removeMatterParty(index) {
        if (index < 0 || index >= matterParties.length) return
        var next = matterParties.slice(0)
        var removedWasAnchor = !!next[index].isFileAnchor
        next.splice(index, 1)
        if (removedWasAnchor && next.length > 0) next[0].isFileAnchor = true
        matterParties = next
        if (next.length > 0) {
            for (var i = 0; i < next.length; i++) {
                if (next[i].isFileAnchor) {
                    _setComboBoxSilently(matterClientCombo, String(next[i].clientName || ""))
                    break
                }
            }
        }
        if (!root._hydrating) root.dirty = true
    }

    function updateMatterParty(index, key, value) {
        if (index < 0 || index >= matterParties.length) return
        var next = matterParties.slice(0)
        var row = Object.assign({}, next[index])
        if (key === "isFileAnchor" && value) {
            for (var i = 0; i < next.length; i++) {
                next[i] = Object.assign({}, next[i])
                next[i].isFileAnchor = i === index
            }
            _setComboBoxSilently(matterClientCombo, String(row.clientName || ""))
        }
        row[key] = value
        next[index] = row
        matterParties = next
        if (!root._hydrating) root.dirty = true
    }

    function syncJointMatterAnchorFromClient() {
        if (!matterJointRetainer) return
        var anchorName = _matterWizardClientName()
        if (anchorName.length > 0) addMatterParty(anchorName, true)
    }

    function setMatterJointRetainer(enabled) {
        matterJointRetainer = !!enabled
        if (matterJointRetainer) {
            syncJointMatterAnchorFromClient()
        } else {
            matterParties = []
            matterJointNoConfidentialityConfirmed = false
            matterJointInstructionsRequireAll = true
        }
        if (!root._hydrating) root.dirty = true
    }

    function refreshMatterDirectory(activeOnlyMode) {
        var rows = []
        try {
            if (appRef && appRef.listMatterDirectory) {
                rows = appRef.listMatterDirectory()
            } else if (appRef && appRef.listMatterNames) {
                var names = appRef.listMatterNames()
                for (var i = 0; i < names.length; i++) {
                    rows.push({
                        "matterId": "",
                        "matterName": String(names[i] || ""),
                        "displayName": String(names[i] || ""),
                        "status": "Open",
                        "active": 1
                    })
                }
            }
        } catch (e) {
            rows = []
        }

        matterDirectoryRows = rows && rows.length !== undefined ? rows : []
        _rebuildMatterDirectoryNameOptions()

        if (activeOnlyMode === true) {
            matterDirectoryMode = "active"
        }
        rebuildMatterDirectoryFilteredRows()

        if (matterDirectoryFilteredRows.length > 0) {
            var matched = false
            for (var r = 0; r < matterDirectoryFilteredRows.length; r++) {
                var row = matterDirectoryFilteredRows[r]
                var rid = String(row.matterId || "")
                var rname = String(row.matterName || row.displayName || "")
                if ((selectedMatterId.length > 0 && rid === selectedMatterId)
                    || (selectedMatterId.length <= 0 && selectedMatterName.length > 0 && rname === selectedMatterName)) {
                    matched = true
                    break
                }
            }
            if (!matched) {
                var matchedInAll = false
                if (matterDirectoryMode !== "all") {
                    for (var rAll = 0; rAll < matterDirectoryRows.length; rAll++) {
                        var rAllRow = matterDirectoryRows[rAll]
                        var rAllId = String(rAllRow.matterId || "")
                        var rAllName = String(rAllRow.matterName || rAllRow.displayName || "")
                        if ((selectedMatterId.length > 0 && rAllId === selectedMatterId)
                            || (selectedMatterId.length <= 0 && selectedMatterName.length > 0 && rAllName === selectedMatterName)) {
                            matchedInAll = true
                            break
                        }
                    }
                }
                
                if (matchedInAll) {
                    matterDirectoryMode = "all"
                    rebuildMatterDirectoryFilteredRows()
                } else {
                    setMatterDirectorySelection(matterDirectoryFilteredRows[0])
                }
            }
        } else {
            selectedMatterId = ""
            if (selectedMatterName.length > 0 && activeOnlyMode === true) {
                selectedMatterName = ""
            }
        }
    }

    function openMatterProfileFromDirectory(row) {
        if (!row) return
        setMatterDirectorySelection(row)
        var state = matterProfileStateForDirectoryRow(row)
        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(0, "A11", state)
            return
        }
        gotoNode("A11")
        loadSelectedMatterProfile("")
    }

    function initializeNewMatterWithClient(clientName) {
        var name = String(clientName || "").trim()

        _hydrating = true
        root.matterEditMode = false

        _setTextFieldSilently(matterNameInput, "")
        _setTextFieldSilently(matterNumberInput, "")
        _setTextFieldSilently(matterDisplayNameInput, "")
        _setComboBoxSilently(matterClientCombo, name)
        _setComboBoxSilently(matterParentCombo, "")
        root.matterJointRetainer = false
        root.matterParties = []
        root.matterJointNoConfidentialityConfirmed = false
        root.matterJointInstructionsRequireAll = true
        root.clientCreateForMatterParty = false
        matterJointRetainerCheck.checked = false
        jointNoConfidentialityCheck.checked = false
        jointInstructionsCheck.checked = true
        _setTextFieldSilently(matterJointEngagementDocumentInput, "")
        _setComboBoxSilently(matterTypeCombo, "General")
        _setComboBoxSilently(matterStatusCombo, "Open")
        _setComboBoxSilently(matterPracticeAreaCombo, "General")
        _setComboBoxSilently(matterResponsibleLawyerCombo, "")
        _setComboBoxSilently(matterBillingArrangementCombo, "Hourly")
        _setTextFieldSilently(matterBillingContactInput, "")
        _setTextFieldSilently(matterBillingEmailInput, "")
        _setTextFieldSilently(matterDefaultRateInput, "0.00")
        _setTextFieldSilently(matterDefaultShareInput, "100.00")
        _setTextFieldSilently(matterRateHistoryInput, "[]")
        root.matterDefaultRateAutoSync = true
        root.matterDefaultShareAutoSync = true
        _setTextFieldSilently(matterDateOfEngagementInput, "")
        _setTextFieldSilently(matterCourtFileInput, "")
        _setTextFieldSilently(matterOpposingPartyInput, "")
        _setTextFieldSilently(matterReferralFromInput, "")
        _setTextFieldSilently(matterDescriptionInput, "")
        _setTextFieldSilently(notesInput, "")

        selectedMatterId = ""
        selectedMatterName = ""
        root.selectedClientName = name
        root.matterNumberAutoSync = true
        root.matterLastAutoNumber = ""
        saveMessage = "Create a new matter. Fill in fields and click Save Matter."

        root.refreshMatterWizardClientOptions()
        root.refreshParentClientOptions()
        root.refreshMatterDirectory(false)

        _hydrating = false
        root.applyMatterWizardAutoPopulate()
        root.dirty = false

        if (root.externalNavigationShell && !root.detachedWindow) {
            var state = root.snapshotState()
            state.selectedClientName = name
            root.workspaceOpenRequested(0, "A10", state)
        } else {
            gotoNode("A10")
        }
    }

    function resolveMatterDirectoryRowForDocket(explicitMatterKey) {
        var key = String(explicitMatterKey || "").trim()
        var keyLower = key.toLowerCase()
        var rows = []

        try {
            if (appRef && appRef.listMatterDirectory) {
                rows = appRef.listMatterDirectory()
            }
        } catch (e0) {
            rows = []
        }

        if (!rows || rows.length === undefined) rows = []

        function matterDisplay(row) {
            var num = String(row.matterNumber || "").trim()
            var name = String(row.matterName || row.displayName || "").trim()
            if (num.length > 0 && name.length > 0) return num + " - " + name
            if (name.length > 0) return name
            return num
        }

        function scoreRow(row) {
            if (!row) return -1
            var matterId = String(row.matterId || "").trim()
            var matterNumber = String(row.matterNumber || "").trim()
            var matterName = String(row.matterName || "").trim()
            var displayName = String(row.displayName || "").trim()
            var display = matterDisplay(row)

            if (keyLower.length <= 0) return -1
            if (matterId.toLowerCase() === keyLower) return 100
            if (matterNumber.toLowerCase() === keyLower) return 95
            if (display.toLowerCase() === keyLower) return 90
            if (displayName.toLowerCase() === keyLower) return 85
            if (matterName.toLowerCase() === keyLower) return 80
            if (keyLower.indexOf(matterNumber.toLowerCase()) === 0 && matterNumber.length > 0) return 75
            if (display.toLowerCase().indexOf(keyLower) >= 0) return 60
            if (keyLower.indexOf(displayName.toLowerCase()) >= 0 && displayName.length > 0) return 50
            if (keyLower.indexOf(matterName.toLowerCase()) >= 0 && matterName.length > 0) return 45
            return -1
        }

        var best = null
        var bestScore = -1

        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            var score = scoreRow(row)
            if (score > bestScore) {
                best = row
                bestScore = score
            }
        }

        if (best) return best

        var profile = root.selectedMatterProfile || ({})
        if (profile && Object.keys(profile).length > 0) return profile

        return ({})
    }

    function loadSelectedMatterProfile(explicitKey) {
        var key = String(explicitKey || "").trim()
        if (key.length <= 0) key = String(selectedMatterId || "").trim()
        if (key.length <= 0) key = String(selectedMatterName || "").trim()

        if (key.length <= 0) {
            selectedMatterProfile = ({})
            refreshMatterProfileRows()
            matterFinancialSummary = ({ "ok": false })
            matterFinancialSummaryLoading = false
            matterProfileLookupMessage = "Select a matter to load profile details."
            return
        }

        if (!appRef || !appRef.getMatterProfile) {
            selectedMatterProfile = ({})
            refreshMatterProfileRows()
            matterProfileLookupMessage = "Matter profile lookup is unavailable."
            return
        }

        var row = root.resolveMatterDirectoryRowByKey(key)
        var lookupKey = String(row.matterId || row.matterNumber || key).trim()

        var result = ({})
        try {
            result = appRef.getMatterProfile(lookupKey)
        } catch (e) {
            result = { "ok": false, "message": String(e), "matter": ({}) }
        }

        if (result && result.ok && result.matter) {
            var loaded = result.matter || ({})
            var loadedRow = root.resolveMatterDirectoryRowByKey(String(loaded.matterId || loaded.matterNumber || lookupKey))
            selectedMatterProfile = loaded
            refreshMatterProfileRows()
            selectedMatterId = String(loaded.matterId || selectedMatterId || "")
            selectedMatterName = root.matterDirectoryOptionLabel(
                Object.keys(loadedRow).length > 0 ? loadedRow : loaded
            )
            matterProfileLookupMessage = "Matter profile loaded."
            matterPersistedStatus = String(loaded.status || "Open").trim()
            refreshMatterFinancialSummary(selectedMatterId)
        } else {
            selectedMatterProfile = ({})
            refreshMatterProfileRows()
            matterFinancialSummary = ({ "ok": false })
            matterFinancialSummaryLoading = false
            matterProfileLookupMessage = result && result.message ? String(result.message) : ("Matter not found: " + key)
        }
    }

    function refreshMatterFinancialSummary(matterId) {
        var id = String(matterId || selectedMatterId || "").trim()
        if (id.length <= 0 || !appRef || !appRef.requestMatterFinancialSummary) {
            matterFinancialSummary = ({ "ok": false })
            matterFinancialSummaryLoading = false
            return
        }
        matterFinancialSummaryToken = "matter-financial-"
            + id + "-" + Date.now() + "-" + Math.random().toString(36).slice(2)
        matterFinancialSummaryLoading = true
        matterFinancialSummary = ({ "ok": false, "matterId": id })
        appRef.requestMatterFinancialSummary(matterFinancialSummaryToken, id)
    }

    function matterFinancialMoney(value) {
        var numeric = Number(value || 0)
        if (!isFinite(numeric)) numeric = 0
        return "$" + numeric.toLocaleString(Qt.locale(), "f", 2)
    }

    function matterStatusIsFinanciallyRestricted(statusValue) {
        var status = String(statusValue || "").trim().toLowerCase()
        return status === "on hold" || status === "closed" || status === "archived"
    }

    function matterStatusSelectionIsBlocked(statusValue) {
        if (!matterEditMode || !matterStatusIsFinanciallyRestricted(statusValue)) return false
        var currentStatus = String(matterPersistedStatus || "").trim().toLowerCase()
        if (currentStatus === String(statusValue || "").trim().toLowerCase()) return false
        return !!(matterFinancialSummary && matterFinancialSummary.ok && matterFinancialSummary.hasFinancialBlockers)
    }

    function matterFinancialBlockerText() {
        var summary = matterFinancialSummary || ({})
        var parts = []
        var wipCount = Number(summary.unbilledWipCount || 0)
        var invoiceCount = Number(summary.unpaidInvoiceCount || 0)
        if (wipCount > 0) parts.push(wipCount + " unbilled WIP item(s) " + matterFinancialMoney(summary.unbilledWipAmount))
        if (invoiceCount > 0) parts.push(invoiceCount + " unpaid invoice(s) " + matterFinancialMoney(summary.unpaidInvoiceAmount))
        return parts.join(" and ")
    }

    function openMatterWipLedger() {
        var matterId = String(selectedMatterId || "").trim()
        if (matterId.length <= 0) return
        var state = {
            "focusNodeId": "B04",
            "matterIdFilterText": matterId,
            "matterFilterText": "All Matters",
            "statusModeText": "Unbilled WIP",
            "currentPreset": "all",
            "forceNewInstance": true
        }
        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(1, "B04", state)
            return
        }
        root._pendingStateForLoader = state
        root.gotoNode("B04")
        if (docketActivityReportPanel && docketActivityReportPanel.applyState) {
            docketActivityReportPanel.applyState(state, true)
        }
    }

    function openMatterInvoice(invoiceNum) {
        var invoice = String(invoiceNum || "").trim()
        if (invoice.length <= 0) return
        var state = {
            "focusNodeId": "C04",
            "selectedInvoiceNum": invoice,
            "forceNewInstance": true
        }
        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(2, "C04", state)
            return
        }
        root._pendingStateForLoader = state
        root.gotoNode("C04")
        if (invoiceDirectoryView && invoiceDirectoryView.applyJumpState) {
            invoiceDirectoryView.applyJumpState(state)
        }
    }

    function _matterClientProfileByName(clientName) {
        var nameLower = _cleanLowerText(clientName)
        if (nameLower.length <= 0) return null
        var rows = clientDirectoryRows && clientDirectoryRows.length !== undefined ? clientDirectoryRows : []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue
            var rowName = _cleanLowerText(row.clientName || row.displayName || "")
            if (rowName === nameLower) {
                var clientId = String(row.clientId || "")
                if (clientId.length > 0 && appRef && appRef.loadClientProfile) {
                    try {
                        return appRef.loadClientProfile(clientId) || null
                    } catch (e) {
                        return null
                    }
                }
            }
        }
        return null
    }

    function applyMatterWizardAutoPopulate() {
        if (root._hydrating) return
        var matterName = String(matterNameInput.text || "").trim()
        if (!root.matterEditMode && root.matterDisplayNameAutoSync && matterName.length > 0) {
            _setTextFieldSilently(matterDisplayNameInput, matterName)
        }
        var clientName = _matterWizardClientName()
        var profile = _matterClientProfileByName(clientName)
        
        var billingEmail = String(matterBillingEmailInput.text || "").trim()
        if (root.matterBillingEmailAutoSync && profile) {
            var email = String(profile["Billing Email"] || profile.billingEmail || profile["Primary Email"] || profile.primaryEmail || "").trim()
            if (email.length > 0) {
                _setTextFieldSilently(matterBillingEmailInput, email)
            }
        }
        
        var billingContact = String(matterBillingContactInput.text || "").trim()
        if (root.matterBillingContactAutoSync && profile) {
            var contact = String(profile["Principal Name"] || profile.principalName || profile["Display Name"] || profile.displayName || profile["Client Name"] || profile.clientName || profile["Legal Name"] || profile.legalName || "").trim()
            if (contact.length > 0) {
                _setTextFieldSilently(matterBillingContactInput, contact)
            }
        }
        
        var billingClientName = _cleanLowerText(matterParentCombo.editText)
        if (!root.matterEditMode && clientName.length > 0) {
            if (billingClientName === "" || billingClientName === "no billing client") {
                _setComboBoxSilently(matterParentCombo, clientName)
                billingClientName = _cleanLowerText(clientName)
            }
        }
        var billingClientName = _cleanLowerText(matterParentCombo.editText)
        var isLIHDC = billingClientName.indexOf("lihdc professional corporation") >= 0
        var targetRate = isLIHDC ? "425.00" : "475.00"
        var targetShare = isLIHDC ? "70" : "100"
        
        if (root.matterDefaultRateAutoSync && !root.matterEditMode) {
            _setTextFieldSilently(matterDefaultRateInput, targetRate)
        }
        if (root.matterDefaultShareAutoSync && !root.matterEditMode) {
            _setTextFieldSilently(matterDefaultShareInput, targetShare)
        }
        
        if (!root.matterEditMode && String(matterPracticeAreaCombo.editText || "").trim() === "") {
            _setComboBoxSilently(matterPracticeAreaCombo, "General")
        }

        applyMatterNumberAutoPopulate()
    }

    function applyMatterNumberAutoPopulate() {
        if (root._hydrating) return
        if (!root.matterNumberAutoSync) return
        if (!appRef || !appRef.previewMatterNumber) return
        var suggested = ""
        try {
            suggested = appRef.previewMatterNumber(
                _matterWizardClientName(),
                String(matterTypeCombo.editText || ""),
                String(matterDateOpenedInput.text || ""),
                root.matterEditMode ? String(root.selectedMatterId || "") : ""
            )
        } catch (e0) {
            suggested = ""
        }
        suggested = String(suggested || "").trim()
        if (suggested.length <= 0) return
        root.matterLastAutoNumber = suggested
        _setTextFieldSilently(matterNumberInput, suggested)
    }

    function handleMatterClientActivated() {
        if (root._hydrating) return
        if (_isNewClientOption(matterClientCombo.editText)) {
            startNewClientFromMatterWizard()
            return
        }
        root.dirty = true
        root.syncJointMatterAnchorFromClient()
        applyMatterWizardAutoPopulate()
    }

    function requestExternalWorkspaceFocus(nodeId) {
        if (!root.externalNavigationShell || root.detachedWindow) return
        var targetNodeId = String(nodeId || "")
        if (targetNodeId.length <= 0) return
        var state = root.snapshotState()
        state.focusNodeId = targetNodeId
        state.focusNodeTitle = nodeTitleForId(targetNodeId)
        root.workspaceOpenRequested(root.tileIndex, targetNodeId, state)
    }

    function startNewClientFromMatterWizard(suggestedClientName, addAsMatterParty) {
        root.clientCreateFromMatterMode = true
        root.clientCreateForMatterParty = !!addAsMatterParty
        root.clientEditMode = false
        root.editReturnNodeId = "A10"
        root.saveMessage = "Create and save the client, then you will return to Matter Wizard."

        var suggestedName = String(suggestedClientName || matterClientCombo.editText || "").trim()
        if (_isNewClientOption(suggestedName)) suggestedName = ""

        _hydrating = true
        gotoNode("A02")
        refreshParentClientOptions()
        _hydrating = false

        _setTextFieldSilently(clientNameInput, suggestedName)
        _setTextFieldSilently(legalNameInput, suggestedName)
        _setTextFieldSilently(firstNameInput, "")
        _setTextFieldSilently(middleNameInput, "")
        _setTextFieldSilently(lastNameInput, "")
        _setComboBoxSilently(parentClientCombo, "")
        _setTextFieldSilently(conflictNotesInput, "")
        _setTextFieldSilently(clientNotesInput, "")
        if (String(clientStatusCombo.editText || "").trim().length <= 0) {
            _setComboBoxSilently(clientStatusCombo, "Active")
        }
        refreshAutoSyncFlags()
        applyClientWizardAutoPopulate()
        root.dirty = true
        requestExternalWorkspaceFocus("A02")
    }

    function returnToMatterWizardAfterClientCreate(createdClientName) {
        var clientName = String(createdClientName || "").trim()
        root.clientCreateFromMatterMode = false
        root.clientEditMode = false
        root.editReturnNodeId = ""
        root.editReturnClientId = ""
        root.editReturnClientName = ""

        _hydrating = true
        gotoNode("A10")
        _hydrating = false

        refreshClientDirectory(false)
        refreshMatterDirectory(false)
        refreshMatterWizardClientOptions()
        if (clientName.length > 0) {
            if (root.clientCreateForMatterParty) {
                root.addMatterParty(clientName, root.matterParties.length === 0)
            } else {
                _setComboBoxSilently(matterClientCombo, clientName)
                root.syncJointMatterAnchorFromClient()
            }
            root.dirty = true
        } else if (_isNewClientOption(matterClientCombo.editText)) {
            _setComboBoxSilently(matterClientCombo, "")
        }
        applyMatterWizardAutoPopulate()
        saveMessage = clientName.length > 0
            ? (root.clientCreateForMatterParty
                ? ("New client added to matter parties: " + clientName)
                : ("New client linked to matter: " + clientName))
            : "Returned to Matter Wizard."
        root.clientCreateForMatterParty = false
        requestExternalWorkspaceFocus("A10")
    }

    function editSelectedMatterInWizard() {
        var profile = selectedMatterProfile || ({})
        var profileKeys = Object.keys(profile)
        if (profileKeys.length <= 0) {
            loadSelectedMatterProfile("")
            profile = selectedMatterProfile || ({})
            profileKeys = Object.keys(profile)
        }

        var matterName = String(profile.matterName || selectedMatterName || "").trim()
        if (matterName.length <= 0) {
            matterProfileLookupMessage = "Load a matter profile before editing."
            return
        }

        matterEditMode = true
        editReturnNodeId = String(currentNode().id || "A11")
        editReturnMatterId = String(profile.matterId || selectedMatterId || "")
        editReturnMatterName = matterName

        _hydrating = true
        gotoNode("A10")
        refreshMatterWizardClientOptions()
        refreshParentClientOptions()
        refreshMatterDirectory(false)

        _setTextFieldSilently(matterNameInput, matterName)
        _setTextFieldSilently(matterNumberInput, String(profile.matterNumber || ""))
        _setTextFieldSilently(matterDisplayNameInput, String(profile.displayName || matterName))
        _setComboBoxSilently(matterClientCombo, String(profile.clientName || ""))
        _setComboBoxSilently(matterParentCombo, String(profile.parentName || ""))
        root.matterJointRetainer = !!profile.isJointRetainer
        root.matterParties = profile.parties && profile.parties.length !== undefined ? profile.parties : []
        root.matterJointNoConfidentialityConfirmed = !!profile.jointNoConfidentialityConfirmed
        root.matterJointInstructionsRequireAll = profile.jointInstructionsRequireAll !== undefined
            ? !!profile.jointInstructionsRequireAll : true
        matterJointRetainerCheck.checked = root.matterJointRetainer
        jointNoConfidentialityCheck.checked = root.matterJointNoConfidentialityConfirmed
        jointInstructionsCheck.checked = root.matterJointInstructionsRequireAll
        _setTextFieldSilently(matterJointEngagementDocumentInput, String(profile.jointEngagementDocument || ""))
        _setComboBoxSilently(matterTypeCombo, String(profile.matterType || "General"))
        _setComboBoxSilently(matterStatusCombo, String(profile.status || "Open"))
        matterPersistedStatus = String(profile.status || "Open").trim()
        _setComboBoxSilently(matterPracticeAreaCombo, String(profile.practiceArea || ""))
        _setComboBoxSilently(matterResponsibleLawyerCombo, String(profile.responsibleLawyer || ""))
        _setComboBoxSilently(
            matterBillingArrangementCombo,
            String(profile.billingArrangement || "Hourly")
        )
        _setTextFieldSilently(matterBillingContactInput, String(profile.billingContact || ""))
        _setTextFieldSilently(matterBillingEmailInput, String(profile.billingEmail || ""))
        _setTextFieldSilently(matterDefaultRateInput, String(profile.defaultRate || "0.00"))
        _setTextFieldSilently(matterDefaultShareInput, String(profile.defaultSharePct || "100.00"))
        _setTextFieldSilently(matterRateHistoryInput, String(profile.rateHistory || "[]"))
        root.matterDefaultRateAutoSync = true
        root.matterDefaultShareAutoSync = true
        _setTextFieldSilently(matterDateOfEngagementInput, String(profile.dateOfEngagement || ""))
        _setTextFieldSilently(
            matterDateOpenedInput,
            String(profile.dateOpened || Qt.formatDate(new Date(), "yyyy-MM-dd"))
        )
        _setTextFieldSilently(matterDateClosedInput, String(profile.dateClosed || ""))
        _setTextFieldSilently(matterCourtFileInput, String(profile.courtFileNumber || ""))
        _setTextFieldSilently(matterOpposingPartyInput, String(profile.opposingParty || ""))
        _setTextFieldSilently(matterReferralFromInput, String(profile.referralFrom || ""))
        _setTextFieldSilently(matterDescriptionInput, String(profile.description || ""))
        _setTextFieldSilently(notesInput, String(profile.notes || ""))

        selectedMatterId = String(profile.matterId || selectedMatterId || "")
        selectedMatterName = matterName
        root.matterNumberAutoSync = false
        root.matterLastAutoNumber = String(matterNumberInput.text || "").trim()
        saveMessage = "Editing matter: " + matterName + ". Update fields and click Save Matter."

        _hydrating = false
        refreshMatterAutoSyncFlags()
        applyMatterWizardAutoPopulate()
        root.dirty = false
    }

    function returnFromMatterEdit() {
        if (!matterEditMode) return false

        var targetNode = String(editReturnNodeId || "A11")
        var targetMatterId = String(editReturnMatterId || selectedMatterId || "")
        var targetMatterName = String(editReturnMatterName || selectedMatterName || "")

        matterEditMode = false
        root.matterNumberAutoSync = true
        root.matterLastAutoNumber = ""
        editReturnNodeId = ""
        editReturnClientId = ""
        editReturnClientName = ""
        editReturnMatterId = ""
        editReturnMatterName = ""
        saveMessage = ""

        _hydrating = true
        selectedMatterId = targetMatterId
        selectedMatterName = targetMatterName
        gotoNode(targetNode)
        _hydrating = false

        if (targetNode === "A11") {
            loadSelectedMatterProfile(targetMatterId.length > 0 ? targetMatterId : targetMatterName)
        }
        return true
    }

    function _matterProfileText(key, fallback) {
        var value = selectedMatterProfile && selectedMatterProfile[key] !== undefined
            ? selectedMatterProfile[key]
            : ""
        var text = String(value === undefined || value === null ? "" : value).trim()
        if (text.length > 0) return text
        return String(fallback || "")
    }

    function _matterProfileDisplayText(key, fallback) {
        var text = _matterProfileText(key, fallback)
        return text.length > 0 ? text : "[blank]"
    }

    function _matterProfileBoolText(key, trueText, falseText) {
        var raw = _matterProfileText(key, "")
        var normalized = _cleanLowerText(raw)
        if (normalized === "1" || normalized === "true" || normalized === "yes") {
            return String(trueText || "Yes")
        }
        if (normalized === "0" || normalized === "false" || normalized === "no") {
            return String(falseText || "No")
        }
        return raw.length > 0 ? raw : String(falseText || "No")
    }

    function matterProfileOrderedModel() {
        var joint = !!(selectedMatterProfile && selectedMatterProfile.isJointRetainer)
        var partyRows = selectedMatterProfile && selectedMatterProfile.parties
            ? selectedMatterProfile.parties : []
        var partySummary = ""
        for (var i = 0; i < partyRows.length; i++) {
            var party = partyRows[i] || ({})
            var label = String(party.clientName || "").trim()
            var role = String(party.role || "").trim()
            if (label.length > 0) partySummary += (partySummary.length > 0 ? "\n" : "") + label + (role.length > 0 ? " - " + role : "")
        }
        return [
            { "label": "Matter Number", "value": _matterProfileDisplayText("matterNumber", "") },
            { "label": "Matter Name", "value": _matterProfileDisplayText("matterName", "") , "multiline": true, "wrap": true },
            { "label": "Display Name", "value": _matterProfileDisplayText("displayName", "") , "multiline": true, "wrap": true },
            { "label": joint ? "File Anchor" : "Client", "value": _matterProfileDisplayText("clientName", "") },
            { "label": "Representation", "value": _matterProfileDisplayText("representationMode", "Single Client") },
            { "label": "Matter Parties", "value": partySummary.length > 0 ? partySummary : "[blank]", "multiline": true, "wrap": true },
            { "label": "Billing Client", "value": _matterProfileDisplayText("parentName", "") },
            { "label": "Matter Type", "value": _matterProfileDisplayText("matterType", "") },
            { "label": "Matter Status", "value": _matterProfileDisplayText("status", "") },
            { "label": "Practice Area", "value": _matterProfileDisplayText("practiceArea", "") },
            { "label": "Responsible Lawyer", "value": _matterProfileDisplayText("responsibleLawyer", "") },
            { "label": "Billing Arrangement", "value": _matterProfileDisplayText("billingArrangement", "") },
            { "label": "Billing Contact", "value": _matterProfileDisplayText("billingContact", "") },
            { "label": "Billing Email", "value": _matterProfileDisplayText("billingEmail", "") },
            { "label": "Default Rate", "value": _matterProfileDisplayText("defaultRate", "0.00") },
            { "label": "Default Share %", "value": _matterProfileDisplayText("defaultSharePct", "100.00") },
            { "label": "Date Of Engagement", "value": _matterProfileDisplayText("dateOfEngagement", "") },
            { "label": "Date Opened", "value": _matterProfileDisplayText("dateOpened", "") },
            { "label": "Date Closed", "value": _matterProfileDisplayText("dateClosed", "") },
            { "label": "Court File Number", "value": _matterProfileDisplayText("courtFileNumber", "") },
            { "label": "Opposing Party", "value": _matterProfileDisplayText("opposingParty", "") },
            { "label": "Referral From", "value": _matterProfileDisplayText("referralFrom", "") },
            { "label": "Description", "value": _matterProfileDisplayText("description", ""), "multiline": true },
            { "label": "Matter Notes", "value": _matterProfileDisplayText("notes", ""), "multiline": true },
            { "label": "Client ID", "value": _matterProfileDisplayText("clientId", "") },
            { "label": "Billing Client ID", "value": _matterProfileDisplayText("parentId", "") },
            { "label": "Active", "value": _matterProfileBoolText("active", "Yes", "No") },
            { "label": "Created At", "value": _matterProfileDisplayText("createdAt", "") },
            { "label": "Updated At", "value": _matterProfileDisplayText("updatedAt", "") },
            { "label": "Matter ID", "value": _matterProfileDisplayText("matterId", "") }
        ]
    }

    function refreshMatterProfileRows() {
        var ordered = matterProfileOrderedModel()
        var rows = []
        for (var i = 0; i < ordered.length; i += 2) {
            rows.push({
                "left": ordered[i],
                "right": (i + 1) < ordered.length ? ordered[i + 1] : null
            })
        }
        matterProfileRows = rows
    }

    function matterProfileRowModel() {
        var rows = matterProfileRows && matterProfileRows.length !== undefined
            ? matterProfileRows : []
        return rows
    }

    function buildMatterProfilePayload() {
        var defaultRate = parseFloat(matterDefaultRateInput.text)
        if (!isFinite(defaultRate)) defaultRate = 0.0
        var defaultSharePct = parseFloat(matterDefaultShareInput.text)
        if (!isFinite(defaultSharePct)) defaultSharePct = 100.0
        var status = String(matterStatusCombo.editText || "").trim()
        if (status.length <= 0) status = "Open"

        return {
            "matterId": matterEditMode ? String(selectedMatterId || "") : "",
            "matterNumber": matterNumberInput.text,
            "matterName": matterNameInput.text,
            "displayName": matterDisplayNameInput.text,
            "clientName": _matterWizardClientName(),
            "parentName": root.matterJointRetainer ? "" : String(matterParentCombo.editText || "").trim(),
            "matterType": matterTypeCombo.editText,
            "practiceArea": String(matterPracticeAreaCombo.editText || ""),
            "status": String(matterStatusCombo.editText || ""),
            "responsibleLawyer": String(matterResponsibleLawyerCombo.editText || ""),
            "billingArrangement": matterBillingArrangementCombo.editText,
            "billingContact": matterBillingContactInput.text,
            "billingEmail": matterBillingEmailInput.text,
            "defaultRate": defaultRate,
            "defaultSharePct": defaultSharePct,
            "rateHistory": String(matterRateHistoryInput.text || "[]"),
            "dateOfEngagement": matterDateOfEngagementInput.text,
            "dateOpened": matterDateOpenedInput.text,
            "dateClosed": matterDateClosedInput.text,
            "courtFileNumber": matterCourtFileInput.text,
            "opposingParty": matterOpposingPartyInput.text,
            "referralFrom": matterReferralFromInput.text,
            "description": matterDescriptionInput.text,
            "notes": notesInput.text,
            "representationMode": root.matterJointRetainer ? "Joint Retainer" : "Single Client",
            "jointNoConfidentialityConfirmed": root.matterJointNoConfidentialityConfirmed,
            "jointInstructionsRequireAll": root.matterJointInstructionsRequireAll,
            "jointEngagementDocument": matterJointEngagementDocumentInput.text,
            "parties": root.matterJointRetainer ? root.matterParties : []
        }
    }

    function _runMatterProfileSave() {
        if (saveInProgress) return
        saveInProgress = true
        var result = {}
        var payload = buildMatterProfilePayload()
        try {
            if (appRef && appRef.saveMatterProfile) {
                result = appRef.saveMatterProfile(payload)
            } else {
                result = {
                    "ok": false,
                    "message": "Backend matter profile save is unavailable."
                }
            }
        } catch (e) {
            result = {
                "ok": false,
                "message": String(e)
            }
        }
        saveInProgress = false
        lastSaveOk = !!(result && result.ok)
        lastSavedMatterId = (result && result.matterId !== undefined && result.matterId !== null)
            ? String(result.matterId)
            : ""

        // A successful editor save must be reflected by a fresh workbook read
        // before we leave the edit screen.  This prevents a stale profile from
        // looking like a saved rename, and keeps the editor open if the exact
        // name/display-name pair was not persisted.
        if (lastSaveOk && root.matterEditMode) {
            var verification = ({})
            try {
                verification = appRef && appRef.getMatterProfile
                    ? appRef.getMatterProfile(lastSavedMatterId)
                    : ({ "ok": false, "message": "Matter profile verification is unavailable." })
            } catch (eVerify) {
                verification = { "ok": false, "message": String(eVerify) }
            }

            var verifiedMatter = verification && verification.matter ? verification.matter : ({})
            var expectedMatterName = String(payload.matterName || "").trim()
            var expectedDisplayName = String(payload.displayName || payload.matterName || "").trim()
            var namesPersisted = verification && verification.ok
                && String(verifiedMatter.matterName || "").trim() === expectedMatterName
                && String(verifiedMatter.displayName || "").trim() === expectedDisplayName

            if (!namesPersisted) {
                lastSaveOk = false
                root.dirty = true
                saveMessage = "Matter changes could not be verified in the workbook. Review the fields and save again; the editor has remained open."
                return
            }

            selectedMatterProfile = verifiedMatter
            refreshMatterProfileRows()
            selectedMatterId = String(verifiedMatter.matterId || lastSavedMatterId || selectedMatterId || "")
            selectedMatterName = root.matterDirectoryOptionLabel(verifiedMatter)
        }

        if (result && result.message !== undefined && String(result.message).length > 0) {
            saveMessage = String(result.message)
        } else if (lastSaveOk) {
            saveMessage = "Matter profile saved to workbook."
        } else {
            saveMessage = "Matter profile save failed."
        }
        if (lastSaveOk) {
            root.matterPersistedStatus = String(matterStatusCombo.editText || "Open").trim()
            root.dirty = false
            root.refreshMatterDirectory(false)
            root.refreshMatterWizardClientOptions()
            if (root.returnFromMatterEdit()) {
                root.matterProfileLookupMessage = "Matter profile updated and reloaded from the workbook."
            }
            root.submitRequested(root.snapshotState())
        } else {
            root.dirty = true
        }
    }

    function trySaveMatterProfile() {
        if (root.matterJointRetainer) {
            if (root.matterParties.length < 2) {
                saveMessage = "Add at least two independent clients to a joint retainer."
                root.dirty = true
                return
            }
            if (!root.matterJointNoConfidentialityConfirmed) {
                saveMessage = "Confirm the joint-retainer shared-information acknowledgement before saving."
                root.dirty = true
                return
            }
            var billingRecipients = 0
            for (var i = 0; i < root.matterParties.length; i++) {
                if (root.matterParties[i].isBillingRecipient) billingRecipients++
            }
            if (billingRecipients < 1) {
                saveMessage = "Select at least one designated invoice recipient."
                root.dirty = true
                return
            }
        }
        if (!_looksLikeEmailAddress(matterBillingEmailInput.text)) {
            saveMessage = "Billing Email is not in a valid email format."
            root.dirty = true
            return
        }
        _runMatterProfileSave()
    }

    function requestMatterArchive() {
        if (!root.matterEditMode) {
            root.saveMessage = "Load an existing matter before archiving it."
            return
        }
        if (String(root.matterPersistedStatus || "").trim().toLowerCase() === "archived") {
            root.saveMessage = "This matter is already archived."
            return
        }
        if (root.matterStatusSelectionIsBlocked("Archived")) {
            root.saveMessage = "This matter cannot be archived while it has "
                + root.matterFinancialBlockerText()
                + ". Resolve that financial work first."
            root.lastSaveOk = false
            return
        }
        archiveMatterConfirmPopup.open()
    }

    function archiveMatterAfterConfirmation() {
        archiveMatterConfirmPopup.blockerMessage = ""
        root._setComboBoxSilently(matterStatusCombo, "Archived")
        root.dirty = true
        root.trySaveMatterProfile()
        if (root.lastSaveOk) {
            archiveMatterConfirmPopup.close()
            root.saveMessage = "Matter archived. New time, fee, and disbursement entries require the protected re-open flow."
        } else {
            archiveMatterConfirmPopup.blockerMessage = String(root.saveMessage || "CSPM could not archive this matter.")
        }
    }

    function emptyGlobalSearchFacets() {
        return {
            "client": 0,
            "matter": 0,
            "parent": 0,
            "invoice": 0,
            "transaction": 0,
            "account": 0,
            "category": 0,
            "business_unit": 0,
            "payee": 0,
            "tickler": 0,
            "deadline": 0,
            "docket": 0,
            "trademark": 0
        }
    }

    function globalSearchTypeOptions() {
        return [
            { "id": "all", "label": "All" },
            { "id": "client", "label": "Clients" },
            { "id": "matter", "label": "Matters" },
            { "id": "parent", "label": "Billing Clients" },
            { "id": "docket", "label": "Dockets" },
            { "id": "transaction", "label": "Transactions" },
            { "id": "account", "label": "Accounts" },
            { "id": "category", "label": "Categories" },
            { "id": "business_unit", "label": "Business Units" },
            { "id": "payee", "label": "Payees" },
            { "id": "tickler", "label": "Ticklers" },
            { "id": "deadline", "label": "Deadlines" },
            { "id": "invoice", "label": "Invoices" },
            { "id": "trademark", "label": "Trademarks" }
        ]
    }

    function globalSearchFacetCount(typeId) {
        var key = _cleanLowerText(typeId)
        if (key.length <= 0 || key === "all") {
            return globalSearchRows && globalSearchRows.length !== undefined
                ? Number(globalSearchRows.length)
                : 0
        }
        if (globalSearchFacetCounts && globalSearchFacetCounts[key] !== undefined) {
            return Number(globalSearchFacetCounts[key] || 0)
        }
        return 0
    }

    function rebuildGlobalSearchFilteredRows() {
        var rows = globalSearchRows && globalSearchRows.length !== undefined ? globalSearchRows : []
        var filterKey = _cleanLowerText(globalSearchEntityFilter)
        if (filterKey.length <= 0) filterKey = "all"
        var filtered = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue
            var rowType = _cleanLowerText(row.entityType)
            if (filterKey !== "all" && rowType !== filterKey) continue
            filtered.push(row)
        }
        globalSearchFilteredRows = filtered
    }

    function refreshGlobalSearchResults() {
        if (!activeIsGlobalSearch()) return
        var query = String(queryInput.text || "").trim()
        if (query.length <= 0) {
            globalSearchRows = []
            globalSearchFilteredRows = []
            globalSearchFacetCounts = emptyGlobalSearchFacets()
            globalSearchMessage = "Enter a search query."
            globalSearchLastOk = true
            return
        }

        if (!appRef || !appRef.searchGlobalEntities) {
            globalSearchRows = []
            globalSearchFilteredRows = []
            globalSearchFacetCounts = emptyGlobalSearchFacets()
            globalSearchMessage = "Global search backend is unavailable."
            globalSearchLastOk = false
            return
        }

        var payload = ({})
        try {
            payload = appRef.searchGlobalEntities(query, globalSearchMode)
        } catch (e) {
            payload = { "ok": false, "message": String(e), "results": [], "facets": ({}) }
        }

        var rows = (payload && payload.results && payload.results.length !== undefined) ? payload.results : []
        var facets = (payload && payload.facets) ? payload.facets : emptyGlobalSearchFacets()
        globalSearchRows = rows
        globalSearchFacetCounts = facets
        rebuildGlobalSearchFilteredRows()

        if (payload && payload.ok) {
            var total = Number(payload.total || rows.length || 0)
            var filteredCount = Number(globalSearchFilteredRows.length || 0)
            globalSearchMessage = "Results: " + String(total)
                + (String(globalSearchEntityFilter || "all").toLowerCase() !== "all"
                    ? (" | Filtered: " + String(filteredCount))
                    : "")
            globalSearchLastOk = true
        } else {
            globalSearchMessage = (payload && payload.message)
                ? String(payload.message)
                : "Search failed."
            globalSearchLastOk = false
        }
    }

    function setGlobalSearchMode(modeText) {
        var mode = _cleanLowerText(modeText)
        globalSearchMode = (mode === "boolean") ? "boolean" : "any"
        refreshGlobalSearchResults()
    }

    function setGlobalSearchEntityFilter(typeId) {
        var key = _cleanLowerText(typeId)
        if (key.length <= 0) key = "all"
        globalSearchEntityFilter = key
        rebuildGlobalSearchFilteredRows()
        if (activeIsGlobalSearch()) {
            var total = globalSearchRows && globalSearchRows.length !== undefined ? globalSearchRows.length : 0
            var filteredCount = globalSearchFilteredRows && globalSearchFilteredRows.length !== undefined
                ? globalSearchFilteredRows.length
                : 0
            globalSearchMessage = "Results: " + String(total)
                + (key !== "all" ? (" | Filtered: " + String(filteredCount)) : "")
        }
    }

    function openGlobalSearchResult(row) {
        if (!row) return
        var targetTile = Number(row.routeTileIndex)
        if (!isFinite(targetTile) || targetTile < 0 || targetTile > 3) targetTile = 3

        var targetState = {
            "focusNodeId": String(row.routeNodeId || ""),
            "focusNodeTitle": String(row.routeNodeTitle || ""),
            "omniQuery": String(queryInput.text || ""),
            "omniQueryType": "global_lookup",
            "globalSearchModeText": globalSearchMode,
            "globalSearchFilterText": globalSearchEntityFilter
        }
        if (_cleanLowerText(row.entityType) === "client") {
            targetState.selectedClientId = String(row.clientId || "")
            targetState.selectedClientName = String(row.clientName || row.displayName || row.title || "")
            targetState.clientDirectoryQueryText = String(row.title || "")
            targetState.clientProfileAutoLoadKey = targetState.selectedClientId.length > 0
                ? targetState.selectedClientId
                : targetState.selectedClientName
            targetState.autoLoadClientProfile = true
            targetState.option3EntityType = "client"
            targetState.option3EntityId = targetState.selectedClientId.length > 0
                ? targetState.selectedClientId
                : targetState.selectedClientName
            targetState.option3EntityTitle = targetState.selectedClientName
        } else if (_cleanLowerText(row.entityType) === "matter") {
            targetState.selectedMatterId = String(row.matterId || row.entityId || "")
            targetState.selectedMatterName = String(row.matterName || row.displayName || row.title || "")
            targetState.matterDirectoryQueryText = String(row.title || "")
            targetState.option3EntityType = "matter"
            targetState.option3EntityId = targetState.selectedMatterId.length > 0
                ? targetState.selectedMatterId
                : targetState.selectedMatterName
            targetState.option3EntityTitle = targetState.selectedMatterName
        } else if (_cleanLowerText(row.entityType) === "docket") {
            var hours = Number(row.hours || 0)
            if (!isFinite(hours) || hours < 0) hours = 0.0
            var rawSeconds = Math.max(0, Math.round(hours * 3600))
            
            targetState.lastSavedEntryId = String(row.entryId || row.entityId || "")
            targetState.dateText = String(row.date || "")
            targetState.clientText = String(row.clientName || row.clientId || "")
            targetState.matterText = String(row.matterName || row.matterId || "")
            if (targetState.matterText.toLowerCase() === "no matter") targetState.matterText = ""
            targetState.descriptionText = String(row.description || "")
            targetState.timeText = String(hours.toFixed(2))
            targetState.rateText = String(Number(row.rate || 0).toFixed(2))
            targetState.billText = String(Number(row.sharePct || 100).toFixed(2))
            targetState.docketStatusText = String(row.status || "Draft")
            targetState.elapsedSeconds = rawSeconds
            targetState.lastPersistedSeconds = rawSeconds
        } else if (_cleanLowerText(row.entityType) === "invoice") {
            receivableEditorPopup.invoiceNum = String(row.invoiceNum || row.entityId || "")
            receivableEditorPopup.open()
            return
        }

        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(targetTile, String(targetState.focusNodeId || row.routeNodeId || ""), targetState)
            return
        }

        var state = snapshotState()
        state._targetTileState = targetState
        moduleJumpRequested(targetTile, state)
    }

    function globalResultClientHeadline(row) {
        var legalName = String(row && row.legalName !== undefined ? row.legalName : "").trim()
        if (legalName.length > 0) return legalName
        var fallbackTitle = String(row && row.title !== undefined ? row.title : "").trim()
        return fallbackTitle
    }

    function globalResultClientSecondary(row) {
        var pieces = []
        var principal = String(row && row.principalName !== undefined ? row.principalName : "").trim()
        var email = String(row && row.primaryEmail !== undefined ? row.primaryEmail : "").trim()
        var phone = _formatPhoneForDisplay(row && row.primaryPhone !== undefined ? row.primaryPhone : "")
        if (principal.length > 0) pieces.push(principal)
        if (email.length > 0) pieces.push(email)
        if (phone.length > 0) pieces.push(phone)
        return pieces.join(" | ")
    }

    function openDocketReportEntryForEdit(row) {
        if (!row) return
        var nextMatter = String(row.matterName || "").trim()
        if (nextMatter.toLowerCase() === "no matter") nextMatter = ""
        var hours = Number(row.hours)
        if (!isFinite(hours) || hours < 0) hours = 0.0
        var rawSeconds = parseInt(row.rawSeconds)
        if (!isFinite(rawSeconds) || rawSeconds < 0) {
            rawSeconds = Math.max(0, Math.round(hours * 3600))
        }
        var targetState = {
            "focusNodeId": "B01",
            "dateText": String(row.date || ""),
            "clientText": String(row.clientName || ""),
            "matterText": nextMatter,
            "descriptionText": String(row.description || ""),
            "timeText": String(hours.toFixed(2)),
            "rateText": String(Number(row.rate || 0).toFixed(2)),
            "billText": String(Number(row.sharePct || 0).toFixed(2)),
            "docketStatusText": String(row.status || "Draft"),
            "elapsedSeconds": rawSeconds,
            "lastPersistedSeconds": rawSeconds
        }
        var state = snapshotState()
        state._targetTileState = targetState
        moduleJumpRequested(1, state)
    }

    function openTimeDocketForSelectedMatter(explicitMatterKey) {
        var key = String(explicitMatterKey || "").trim()
        if (key.length <= 0) key = String(root.selectedMatterId || "").trim()
        if (key.length <= 0) key = String(root.selectedMatterName || "").trim()

        if (key.length <= 0) {
            root.matterProfileLookupMessage = "Select a matter before docketing time."
            return
        }

        var row = root.resolveMatterDirectoryRowByKey(key)
        if (!row || Object.keys(row).length <= 0) {
            root.matterProfileLookupMessage = "Could not resolve a unique matter from: " + key
            return
        }

        var lookupKey = String(row.matterId || row.matterNumber || key).trim()
        root.loadSelectedMatterProfile(lookupKey)

        var profile = root.selectedMatterProfile || ({})
        var matterId = String(profile.matterId || row.matterId || "").trim()
        var matterNumber = String(profile.matterNumber || row.matterNumber || "").trim()
        var matterName = String(profile.matterName || row.matterName || row.displayName || "").trim()
        var clientName = String(profile.clientName || row.clientName || "").trim()
        var parentName = String(profile.parentName || row.parentName || "").trim()
        var docketMatterText = root.matterDocketDisplayLabel({
            "matterNumber": matterNumber,
            "matterName": matterName
        })

        var rateNumber = Number(profile.defaultRate !== undefined ? profile.defaultRate : row.defaultRate)
        if (!isFinite(rateNumber) || rateNumber < 0) rateNumber = 0

        var shareNumber = Number(profile.defaultSharePct !== undefined ? profile.defaultSharePct : row.defaultSharePct)
        if (!isFinite(shareNumber) || shareNumber <= 0) shareNumber = 100

        var entityId = matterId.length > 0 ? matterId : (matterNumber.length > 0 ? matterNumber : docketMatterText)
        var tabTitle = docketMatterText.length > 0 ? docketMatterText : root.matterDirectoryOptionLabel(row)

        var targetState = {
            "cspmQuickAction": "matter360Docket",
            "forceApplyStateAfterOpen": true,
            "forceNewDocketContext": true,
            "forceNewInstance": true,
            "suppressBucketRefreshOnce": true,

            "tileIndex": 1,
            "titleText": "Docketing",
            "focusNodeId": "B01",
            "focusNodeTitle": "Time Docket Entry",

            "dateText": Qt.formatDate(new Date(), "yyyy-MM-dd"),
            "parentText": parentName,
            "billingClientText": parentName,
            "clientText": clientName,
            "matterText": docketMatterText,
            "taskText": "",
            "descriptionText": "",
            "timeText": "0.00",
            "rateText": rateNumber.toFixed(2),
            "billText": shareNumber.toFixed(2),
            "docketStatusText": "Draft",

            "elapsedSeconds": 0,
            "lastPersistedSeconds": 0,
            "lastSavedEntryId": "",
            "persistedBucketKey": "",
            "isRunning": false,
            "dirty": true,

            "selectedMatterId": matterId,
            "selectedMatterName": matterName,
            "selectedClientName": clientName,
            "matterId": matterId,
            "matterNumber": matterNumber,
            "matterName": matterName,
            "clientName": clientName,
            "parentName": parentName,

            "entityType": "matter",
            "entityId": entityId,
            "entityTitle": tabTitle,
            "option3EntityType": "matter",
            "option3EntityId": entityId,
            "option3EntityTitle": tabTitle,
            "tabEntityType": "matter",
            "tabEntityId": entityId,
            "tabEntityTitle": tabTitle,
            "tabTitle": "Docket: " + tabTitle
        }

        root.matterProfileLookupMessage = "Opening Time Docket Entry for " + tabTitle + "."

        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(1, "B01", targetState)
            return
        }

        var state = root.snapshotState()
        state._targetTileState = targetState
        root.moduleJumpRequested(1, state)
    }

    function openClientProfileFromDirectory(row) {
        if (!row) return
        setDirectorySelection(row)
        var state = clientProfileStateForDirectoryRow(row)
        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(0, "A03", state)
            return
        }
        gotoNode("A03")
        loadSelectedClientProfile(state.clientProfileAutoLoadKey)
    }

    function editClientFromDirectory(row) {
        if (!row) return
        setDirectorySelection(row)
        var state = clientProfileStateForDirectoryRow(row)
        var clientKey = String(state.clientProfileAutoLoadKey || "").trim()

        loadSelectedClientProfile(clientKey)
        editSelectedClientInWizard()
        if (!root.clientEditMode) return

        // A directory double-click is an edit action.  The editor returns to
        // the selected client's Profile 360 when the user cancels or saves.
        root.editReturnNodeId = "A03"
        state.focusNodeId = "A02"
        state.focusNodeTitle = "Edit Client Profile"
        state.editClientFromDirectory = true

        if (root.externalNavigationShell && !root.detachedWindow) {
            root.workspaceOpenRequested(0, "A02", state)
            return
        }
    }

    function _resolveClientProfileKey(rawKey) {
        var key = String(rawKey || "").trim()
        if (key.length <= 0) return ""
        var keyLower = _cleanLowerText(key)
        var rows = clientDirectoryRows && clientDirectoryRows.length !== undefined ? clientDirectoryRows : []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row) continue
            var rowId = String(row.clientId || "").trim()
            if (rowId.length > 0 && _cleanLowerText(rowId) === keyLower) {
                return rowId
            }
            var rowName = String(row.clientName || row.displayName || "").trim()
            if (rowName.length > 0 && _cleanLowerText(rowName) === keyLower) {
                if (rowId.length > 0) {
                    return rowId
                }
                return rowName
            }
        }
        return key
    }

    function loadSelectedClientProfile(explicitKey) {
        var key = String(explicitKey || "").trim()
        if (key.length <= 0) {
            key = String(selectedClientId || "").trim()
        }
        if (key.length <= 0) {
            key = String(selectedClientName || "").trim()
        }
        key = _resolveClientProfileKey(key)
        if (key.length <= 0) {
            selectedClientProfile = ({})
            profileLookupMessage = "Select a client to load profile details."
            return
        }
        if (!appRef || !appRef.getClientProfile) {
            selectedClientProfile = ({})
            profileLookupMessage = "Client profile lookup is unavailable."
            return
        }

        var result = ({})
        try {
            result = appRef.getClientProfile(key)
        } catch (e) {
            result = { "ok": false, "message": String(e), "client": ({}) }
        }

        if (result && result.ok && result.client) {
            selectedClientProfile = result.client
            selectedClientId = String(result.client.clientId || selectedClientId || "")
            selectedClientName = String(result.client.clientName || selectedClientName || "")
            pendingClientProfileAutoLoadKey = ""
            profileLookupMessage = "Profile loaded."
        } else {
            selectedClientProfile = ({})
            profileLookupMessage = result && result.message ? String(result.message) : ("Client not found: " + key)
        }
    }

    function autoLoadSelectedClientProfile(explicitKey) {
        var key = String(explicitKey || "").trim()
        if (key.length <= 0) key = String(selectedClientId || "").trim()
        if (key.length <= 0) key = String(selectedClientName || "").trim()
        pendingClientProfileAutoLoadKey = key

        if (key.length <= 0) {
            loadSelectedClientProfile("")
            return
        }

        var loaded = selectedClientProfile || ({})
        var loadedId = String(loaded.clientId || "").trim()
        var loadedName = String(loaded.clientName || "").trim()
        var keyLower = _cleanLowerText(key)
        if ((loadedId.length > 0 && _cleanLowerText(loadedId) === keyLower)
                || (loadedName.length > 0 && _cleanLowerText(loadedName) === keyLower)) {
            profileLookupMessage = "Profile loaded."
            pendingClientProfileAutoLoadKey = ""
            return
        }

        profileLookupMessage = "Loading profile..."
        if (appRef && appRef.backendBooted === false) {
            clientProfileAutoLoadRetryTimer.restart()
            return
        }
        loadSelectedClientProfile(key)
        if (profileLookupMessage === "Backend is still loading.") {
            clientProfileAutoLoadRetryTimer.restart()
        }
    }

    function editSelectedClientInWizard() {
        var profile = selectedClientProfile || ({})
        var profileKeys = Object.keys(profile)
        if (profileKeys.length <= 0) {
            loadSelectedClientProfile("")
            profile = selectedClientProfile || ({})
            profileKeys = Object.keys(profile)
        }

        var clientName = String(profile.clientName || selectedClientName || "").trim()
        if (clientName.length <= 0) {
            profileLookupMessage = "Load a client profile before editing."
            return
        }

        clientEditMode = true
        editReturnNodeId = String(currentNode().id || "A03")
        editReturnClientId = String(profile.clientId || selectedClientId || "")
        editReturnClientName = clientName

        _hydrating = true
        gotoNode("A02")
        refreshParentClientOptions()

        _setTextFieldSilently(clientNameInput, clientName)
        _setTextFieldSilently(legalNameInput, String(profile.legalName || clientName))
        _setTextFieldSilently(firstNameInput, String(profile.firstName || ""))
        _setTextFieldSilently(middleNameInput, String(profile.middleName || ""))
        _setTextFieldSilently(lastNameInput, String(profile.lastName || ""))
        _setComboBoxSilently(entityTypeCombo, String(profile.entityType || "Corporation"))
        _setComboBoxSilently(clientStatusCombo, String(profile.status || "Active"))
        _setTextFieldSilently(principalNameInput, String(profile.principalName || ""))
        _setTextFieldSilently(principalPositionInput, String(profile.principalPosition || ""))
        _setTextFieldSilently(primaryEmailInput, String(profile.primaryEmail || ""))
        _setTextFieldSilently(primaryPhoneInput, String(profile.primaryPhone || ""))
        _setTextFieldSilently(secondaryContactInput, String(profile.secondaryContactName || ""))
        _setTextFieldSilently(secondaryPositionInput, String(profile.secondaryContactPosition || ""))
        _setTextFieldSilently(secondaryEmailInput, String(profile.secondaryContactEmail || ""))
        _setTextFieldSilently(secondaryPhoneInput, String(profile.secondaryContactPhone || ""))
        _setComboBoxSilently(parentClientCombo, String(profile.parentClientName || ""))
        _setComboBoxSilently(onboardingCombo, String(profile.onboardingStatus || "Prospect"))
        _setTextFieldSilently(addressLine1Input, String(profile.addressLine1 || ""))
        _setTextFieldSilently(addressLine2Input, String(profile.addressLine2 || ""))
        _setTextFieldSilently(cityInput, String(profile.city || ""))
        _setTextFieldSilently(stateProvinceInput, String(profile.stateProvince || ""))
        _setTextFieldSilently(postalCodeInput, String(profile.postalCode || ""))
        _setTextFieldSilently(countryInput, String(profile.country || ""))
        _setTextFieldSilently(websiteInput, String(profile.website || ""))
        _setTextFieldSilently(taxIdInput, String(profile.taxId || ""))
        _setTextFieldSilently(industryInput, String(profile.industry || ""))
        _setTextFieldSilently(billingEmailInput, String(profile.billingEmail || ""))
        _setComboBoxSilently(kycCombo, String(profile.kycStatus || "Pending"))
        _setComboBoxSilently(
            retainerRequiredCombo,
            Number(profile.retainerRequired || 0) !== 0 ? "Yes" : "No"
        )
        _setTextFieldSilently(retainerAmountInput, String(profile.retainerAmount || "0.00"))
        _setTextFieldSilently(engagementStartInput, String(profile.engagementStartDate || ""))
        _setTextFieldSilently(
            dateClientAddedInput,
            String(profile.dateClientAdded || Qt.formatDate(new Date(), "yyyy-MM-dd"))
        )
        _setTextFieldSilently(birthdayInput, String(profile.birthday || ""))
        _setTextFieldSilently(referralFromInput, String(profile.referralFrom || ""))
        _setTextFieldSilently(conflictNotesInput, String(profile.conflictNotes || ""))
        _setTextFieldSilently(clientNotesInput, String(profile.notes || ""))

        selectedClientId = String(profile.clientId || selectedClientId || "")
        selectedClientName = clientName
        saveMessage = "Editing client: " + clientName + ". Update fields and click Save Client."

        refreshAutoSyncFlags()
        _hydrating = false
        applyClientWizardAutoPopulate()
        root.dirty = false
    }

    function returnFromClientEdit() {
        if (!clientEditMode) return false

        var targetNode = String(editReturnNodeId || "A03")
        var targetClientId = String(editReturnClientId || selectedClientId || "")
        var targetClientName = String(editReturnClientName || selectedClientName || "")

        clientEditMode = false
        editReturnNodeId = ""
        editReturnClientId = ""
        editReturnClientName = ""
        editReturnMatterId = ""
        editReturnMatterName = ""
        saveMessage = ""

        _hydrating = true
        selectedClientId = targetClientId
        selectedClientName = targetClientName
        gotoNode(targetNode)
        _hydrating = false

        if (targetNode === "A03") {
            loadSelectedClientProfile(targetClientId.length > 0 ? targetClientId : targetClientName)
        }
        return true
    }

    function _profileText(key, fallback) {
        var value = selectedClientProfile && selectedClientProfile[key] !== undefined
            ? selectedClientProfile[key]
            : ""
        var text = String(value === undefined || value === null ? "" : value).trim()
        if (text.length > 0) return text
        return String(fallback || "")
    }

    function _profileDisplayText(key, fallback) {
        var text = _profileText(key, fallback)
        return text.length > 0 ? text : "[blank]"
    }

    function _profileBoolText(key, trueText, falseText) {
        var raw = _profileText(key, "")
        var normalized = _cleanLowerText(raw)
        if (normalized === "1" || normalized === "true" || normalized === "yes") {
            return String(trueText || "Yes")
        }
        if (normalized === "0" || normalized === "false" || normalized === "no") {
            return String(falseText || "No")
        }
        return raw.length > 0 ? raw : String(falseText || "No")
    }

    function clientProfileOrderedModel() {
        return [
            { "label": "Client Name", "value": _profileDisplayText("clientName", "") },
            { "label": "Legal Name", "value": _profileDisplayText("legalName", "") },
            { "label": "First Name", "value": _profileDisplayText("firstName", "") },
            { "label": "Middle Name", "value": _profileDisplayText("middleName", "") },
            { "label": "Last Name", "value": _profileDisplayText("lastName", "") },
            { "label": "Entity Type", "value": _profileDisplayText("entityType", "") },
            { "label": "Client Status", "value": _profileDisplayText("status", "") },
            { "label": "Principal Name", "value": _profileDisplayText("principalName", "") },
            { "label": "Principal Position", "value": _profileDisplayText("principalPosition", "") },
            { "label": "Primary Email", "value": _profileDisplayText("primaryEmail", "") },
            { "label": "Primary Phone", "value": _profileDisplayText("primaryPhone", "") },
            { "label": "Secondary Contact", "value": _profileDisplayText("secondaryContactName", "") },
            { "label": "Secondary Position", "value": _profileDisplayText("secondaryContactPosition", "") },
            { "label": "Secondary Email", "value": _profileDisplayText("secondaryContactEmail", "") },
            { "label": "Secondary Phone", "value": _profileDisplayText("secondaryContactPhone", "") },
            { "label": "Billing Client", "value": _profileDisplayText("parentClientName", "") },
            { "label": "Onboarding Stage", "value": _profileDisplayText("onboardingStatus", "") },
            { "label": "Address Line 1", "value": _profileDisplayText("addressLine1", "") },
            { "label": "Address Line 2", "value": _profileDisplayText("addressLine2", "") },
            { "label": "City", "value": _profileDisplayText("city", "") },
            { "label": "State/Province", "value": _profileDisplayText("stateProvince", "") },
            { "label": "Postal Code", "value": _profileDisplayText("postalCode", "") },
            { "label": "Country", "value": _profileDisplayText("country", "") },
            { "label": "Website", "value": _profileDisplayText("website", "") },
            { "label": "Tax ID", "value": _profileDisplayText("taxId", "") },
            { "label": "Industry", "value": _profileDisplayText("industry", "") },
            { "label": "Billing Email", "value": _profileDisplayText("billingEmail", "") },
            { "label": "KYC Status", "value": _profileDisplayText("kycStatus", "") },
            { "label": "Retainer Required", "value": _profileBoolText("retainerRequired", "Yes", "No") },
            { "label": "Retainer Amount", "value": _profileDisplayText("retainerAmount", "0.00") },
            { "label": "Engagement Start", "value": _profileDisplayText("engagementStartDate", "") },
            { "label": "Date Client Added", "value": _profileDisplayText("dateClientAdded", "") },
            { "label": "Birthday", "value": _profileDisplayText("birthday", "") },
            { "label": "Referral From", "value": _profileDisplayText("referralFrom", "") },
            { "label": "Formatted Address", "value": _profileDisplayText("fullAddress", ""), "multiline": true },
            { "label": "Conflict Notes", "value": _profileDisplayText("conflictNotes", ""), "multiline": true },
            { "label": "Client Notes", "value": _profileDisplayText("notes", ""), "multiline": true },
            { "label": "Display Name", "value": _profileDisplayText("displayName", "") , "multiline": true, "wrap": true },
            { "label": "Internal Client ID", "value": _profileDisplayText("internalClientId", "") },
            { "label": "Billing Client ID", "value": _profileDisplayText("parentClientId", "") },
            { "label": "Active", "value": _profileBoolText("active", "Yes", "No") },
            { "label": "Created At", "value": _profileDisplayText("createdAt", "") },
            { "label": "Updated At", "value": _profileDisplayText("updatedAt", "") },
            { "label": "Client ID", "value": _profileDisplayText("clientId", "") }
        ]
    }

    function clientProfileRowModel() {
        var ordered = clientProfileOrderedModel()
        var rows = []
        for (var i = 0; i < ordered.length; i += 2) {
            rows.push({
                "left": ordered[i],
                "right": (i + 1) < ordered.length ? ordered[i + 1] : null
            })
        }
        return rows
    }

    function buildFormattedAddressPreview() {
        var lines = []
        var line1 = String(addressLine1Input.text || "").trim()
        var line2 = String(addressLine2Input.text || "").trim()
        var city = String(cityInput.text || "").trim()
        var stateProvince = String(stateProvinceInput.text || "").trim()
        var postal = String(postalCodeInput.text || "").trim()
        var country = String(countryInput.text || "").trim()

        if (line1.length > 0) lines.push(line1)
        if (line2.length > 0) lines.push(line2)

        var locality = ""
        if (city.length > 0 && stateProvince.length > 0) {
            locality = city + ", " + stateProvince
        } else if (city.length > 0) {
            locality = city
        } else if (stateProvince.length > 0) {
            locality = stateProvince
        }
        if (postal.length > 0) {
            locality = locality.length > 0 ? (locality + " " + postal) : postal
        }
        if (locality.length > 0) lines.push(locality)
        if (country.length > 0) lines.push(country)
        return lines.join("\n")
    }

    function buildClientProfilePayload() {
        var clientStatusText = String(clientStatusCombo.editText || "").trim()
        var normalizedStatus = clientStatusText.length > 0 ? clientStatusText : "Active"
        var activeFlag = normalizedStatus.toLowerCase() === "inactive"
            || normalizedStatus.toLowerCase() === "closed"
            || normalizedStatus.toLowerCase() === "archived"
            ? 0
            : 1

        var retainerAmount = parseFloat(retainerAmountInput.text)
        if (!isFinite(retainerAmount)) retainerAmount = 0.0

        return {
            "clientName": clientNameInput.text,
            "displayName": clientNameInput.text,
            "legalName": legalNameInput.text,
            "firstName": firstNameInput.text,
            "middleName": middleNameInput.text,
            "lastName": lastNameInput.text,
            "entityType": entityTypeCombo.editText,
            "principalName": principalNameInput.text,
            "principalPosition": principalPositionInput.text,
            "parentClientName": String(parentClientCombo.editText || "").trim(),
            "primaryEmail": primaryEmailInput.text,
            "primaryPhone": primaryPhoneInput.text,
            "secondaryContactName": secondaryContactInput.text,
            "secondaryContactPosition": secondaryPositionInput.text,
            "secondaryContactEmail": secondaryEmailInput.text,
            "secondaryContactPhone": secondaryPhoneInput.text,
            "addressLine1": addressLine1Input.text,
            "addressLine2": addressLine2Input.text,
            "city": cityInput.text,
            "stateProvince": stateProvinceInput.text,
            "postalCode": postalCodeInput.text,
            "country": countryInput.text,
            "fullAddress": buildFormattedAddressPreview(),
            "website": websiteInput.text,
            "taxId": taxIdInput.text,
            "industry": industryInput.text,
            "billingEmail": billingEmailInput.text,
            "kycStatus": kycCombo.editText,
            "onboardingStatus": onboardingCombo.editText,
            "retainerRequired": String(retainerRequiredCombo.editText || "").toLowerCase() === "yes" ? 1 : 0,
            "retainerAmount": retainerAmount,
            "engagementStartDate": engagementStartInput.text,
            "dateClientAdded": dateClientAddedInput.text,
            "birthday": birthdayInput.text,
            "referralFrom": referralFromInput.text,
            "conflictNotes": conflictNotesInput.text,
            "notes": clientNotesInput.text,
            "status": normalizedStatus,
            "active": activeFlag
        }
    }

    function _runClientProfileSave() {
        if (saveInProgress) return
        saveInProgress = true
        var result = {}
        try {
            if (appRef && appRef.saveClientProfile) {
                result = appRef.saveClientProfile(buildClientProfilePayload())
            } else {
                result = {
                    "ok": false,
                    "message": "Backend client profile save is unavailable."
                }
            }
        } catch (e) {
            result = {
                "ok": false,
                "message": String(e)
            }
        }
        saveInProgress = false
        lastSaveOk = !!(result && result.ok)
        lastSavedClientId = (result && result.clientId !== undefined && result.clientId !== null)
            ? String(result.clientId)
            : ""
        if (result && result.message !== undefined && String(result.message).length > 0) {
            saveMessage = String(result.message)
        } else if (lastSaveOk) {
            saveMessage = "Client profile saved to workbook."
        } else {
            saveMessage = "Client profile save failed."
        }
        if (lastSaveOk) {
            root.dirty = false
            root.refreshClientDirectory(false)
            root.refreshParentClientOptions()
            if (root.clientCreateFromMatterMode) {
                var savedClientName = String(clientNameInput.text || "").trim()
                if (result && result.savedRow) {
                    var dictDisplayName = String(result.savedRow["DisplayName"] || result.savedRow.DisplayName || result.savedRow["ClientName"] || result.savedRow.ClientName || "").trim()
                    if (dictDisplayName.length > 0) savedClientName = dictDisplayName
                }
                root.returnToMatterWizardAfterClientCreate(savedClientName)
                root.submitRequested(root.snapshotState())
                return
            }
            if (root.returnFromClientEdit()) {
                root.profileLookupMessage = "Profile updated."
            }
            root.submitRequested(root.snapshotState())
        } else {
            root.dirty = true
        }
    }

    function trySaveClientProfile(allowValidationOverride) {
        normalizeClientWizardPhoneFields()
        if (!allowValidationOverride) {
            var issues = collectClientWizardValidationIssues()
            if (issues.length > 0) {
                clientSaveValidationSummary = _validationIssueSummary(issues)
                clientSaveValidationPopup.open()
                return
            }
        }
        _runClientProfileSave()
    }

    function requestOption3Save(command, tab) {
        var saveCommand = String(command || "").trim()
        if (saveCommand === "client-profile") {
            trySaveClientProfile(false)
            return true
        }
        if (saveCommand === "matter-profile") {
            trySaveMatterProfile()
            return true
        }
        if (saveCommand === "transaction") {
            if (transactionMasterView && transactionMasterView.runPrimaryAction) {
                transactionMasterView.runPrimaryAction()
                return true
            }
            return false
        }
        if (saveCommand === "payment") {
            if (paymentEntryView && paymentEntryView.runPrimaryAction) {
                paymentEntryView.runPrimaryAction()
                return true
            }
            return false
        }
        if (saveCommand === "primary-action") {
            requestPrimaryAction()
            return true
        }
        return false
    }

    function requestPrimaryAction() {
        if (activeIsGlobalSearch()) {
            refreshGlobalSearchResults()
            root.dirty = false
            return
        }
        if (activeIsDocketActivityReport()) {
            if (docketActivityReportPanel && docketActivityReportPanel.runReport) {
                docketActivityReportPanel.runReport()
            }
            root.dirty = false
            return
        }
        if (activeIsFinancialDashboard()) {
            if (financialDashboardPanel && financialDashboardPanel.refreshDashboard) {
                financialDashboardPanel.refreshDashboard()
            }
            root.dirty = false
            return
        }
        if (activeIsARAgingReport()) {
            if (arAgingReportPanel && arAgingReportPanel.refreshReport) {
                arAgingReportPanel.refreshReport()
            }
            root.dirty = false
            return
        }
        if (activeIsClientDirectory()) {
            refreshClientDirectory(false)
            root.dirty = false
            return
        }
        if (activeIsClientProfile360()) {
            loadSelectedClientProfile("")
            root.dirty = false
            return
        }
        if (activeIsMatterDirectory()) {
            refreshMatterDirectory(false)
            root.dirty = false
            return
        }
        if (activeIsMatterProfile360()) {
            loadSelectedMatterProfile("")
            root.dirty = false
            return
        }
        if (activeIsNewMatterWizard()) {
            trySaveMatterProfile()
            return
        }
        if (activeIsTransactionsMaster()) {
            if (transactionMasterView && transactionMasterView.runPrimaryAction) {
                transactionMasterView.runPrimaryAction()
            }
            return
        }
        if (activeIsPaymentEntry()) {
            if (paymentEntryView && paymentEntryView.runPrimaryAction) {
                paymentEntryView.runPrimaryAction()
            }
            return
        }
        if (!activeIsNewClientWizard()) {
            root.dirty = false
            root.submitRequested(root.snapshotState())
            return
        }
        trySaveClientProfile(false)
    }

    function requestCancelAction() {
        if (activeIsNewClientWizard() && clientCreateFromMatterMode) {
            returnToMatterWizardAfterClientCreate("")
            root.dirty = false
            return
        }
        if (activeIsNewClientWizard() && clientEditMode) {
            returnFromClientEdit()
            root.dirty = false
            return
        }
        if (activeIsNewMatterWizard() && matterEditMode) {
            if (root.dirty) {
                discardMatterEditPopup.open()
                return
            }
            returnFromMatterEdit()
            root.dirty = false
            return
        }
        root.cancelRequested(root.snapshotState())
    }

    function refreshParentClientOptions() {
        if (!appRef || !appRef.listClientNames) {
            parentClientOptions = [""]
            return
        }
        var parents = []
        try {
            parents = appRef.listClientNames()
        } catch (e) {
            parents = []
        }
        parentClientOptions = _parentClientOptionsWithBlank(parents)
    }

    function snapshotState() {
        var node = root.currentNode()
        var baseState = {
            "tileIndex": root.tileIndex,
            "titleText": root.titleText,
            "laneKey": root.laneKey,
            "focusNodeId": root.activeNodeId,
            "focusNodeTitle": node ? String(node.title || "") : "",
            "dirty": root.dirty,
            "omniQuery": queryInput.text,
            "clientDirectoryQueryText": root.clientDirectoryQuery,
            "clientDirectoryModeText": clientDirectoryMode,
            "matterDirectoryQueryText": root.matterDirectoryQuery,
            "matterDirectoryModeText": matterDirectoryMode,
            "selectedClientId": root.selectedClientId,
            "selectedClientName": root.selectedClientName,
            "selectedMatterId": root.selectedMatterId,
            "selectedMatterName": root.selectedMatterName
        }

        if (wipBillingView && typeof wipBillingView.snapshotState === "function") {
            var wipState = wipBillingView.snapshotState()
            for (var k in wipState) {
                baseState[k] = wipState[k]
            }
        } else if (paymentEntryView && typeof paymentEntryView.snapshotState === "function") {
            // Payment Entry is a live financial form.  Preserve its selected
            // invoice and in-progress values whenever the work-tab shell
            // checkpoints or restores state.
            var paymentState = paymentEntryView.snapshotState()
            for (var paymentKey in paymentState) {
                baseState[paymentKey] = paymentState[paymentKey]
            }
        } else if (root._pendingStateForLoader && typeof root._pendingStateForLoader === "object") {
            for (var k2 in root._pendingStateForLoader) {
                if (k2 === "selectedClientFilter" || k2 === "selectedBillingClientFilter" || k2 === "clientIdToDraft" || k2 === "matterId") {
                    baseState[k2] = root._pendingStateForLoader[k2]
                }
            }
        }

        return baseState
    }

    function applyInitialState(state) {
        if (!state) return
        root._pendingStateForLoader = state
        _hydrating = true
        if (state.focusNodeId !== undefined) {
            root.activeNodeId = String(state.focusNodeId || "")
        }
        ensureActiveNode()
        if (state.omniQuery !== undefined) queryInput.text = String(state.omniQuery || "")
        if (state.globalSearchModeText !== undefined) {
            globalSearchMode = _cleanLowerText(state.globalSearchModeText) === "boolean" ? "boolean" : "any"
        }
        if (state.globalSearchFilterText !== undefined) {
            globalSearchEntityFilter = _cleanLowerText(state.globalSearchFilterText) || "all"
        }
        if (state.clientDirectoryQueryText !== undefined) {
            root.clientDirectoryQuery = String(state.clientDirectoryQueryText || "")
        }
        if (state.clientDirectoryModeText !== undefined) {
            clientDirectoryMode = _cleanLowerText(state.clientDirectoryModeText) === "active" ? "active" : "all"
        }
        if (state.matterDirectoryQueryText !== undefined) {
            root.matterDirectoryQuery = String(state.matterDirectoryQueryText || "")
        }
        if (state.matterDirectoryModeText !== undefined) {
            matterDirectoryMode = _cleanLowerText(state.matterDirectoryModeText) === "active" ? "active" : "all"
        }
        if (state.selectedClientId !== undefined) root.selectedClientId = String(state.selectedClientId || "")
        if (state.selectedClientName !== undefined) root.selectedClientName = String(state.selectedClientName || "")
        if (state.selectedMatterId !== undefined) root.selectedMatterId = String(state.selectedMatterId || "")
        if (state.selectedMatterName !== undefined) root.selectedMatterName = String(state.selectedMatterName || "")
        root.dirty = !!state.dirty
        _hydrating = false
        if (root.activeIsClientDirectory()) {
            root.refreshClientDirectory(false)
        }
        if (root.activeIsMatterDirectory()) {
            root.refreshMatterDirectory(false)
        }
        if (root.activeIsClientProfile360()) {
            root.refreshClientDirectory(false)
            root.autoLoadSelectedClientProfile(
                state.clientProfileAutoLoadKey !== undefined ? String(state.clientProfileAutoLoadKey || "") : ""
            )
        }
        if (root.activeIsMatterProfile360()) {
            root.refreshMatterDirectory(false)
            root.loadSelectedMatterProfile("")
        }
        if (root.activeIsGlobalSearch()) {
            root.refreshGlobalSearchResults()
        }
        if (root.activeIsTransactionsMaster() && transactionMasterView) {
            transactionMasterView.refreshLookupData()
            if (transactionMasterView.loadRecentTransactions) {
                transactionMasterView.loadRecentTransactions()
            }
            if (transactionMasterView.applyState) {
                transactionMasterView.applyState(state)
            }
        }
        if (root.activeIsPaymentEntry() && paymentEntryView) {
            paymentEntryView.applyState(state)
        }
        if (root.activeIsAccountsPayable() && accountsPayableLoader.item
                && accountsPayableLoader.item.applyStartupState) {
            accountsPayableLoader.item.applyStartupState(state)
        }
        if (root.activeIsInvoiceReversal() && invoiceReversalView) {
            invoiceReversalView.applyJumpState(state)
        }
        if (root.activeIsWipToBill()) {
            console.log("PlaceholderSubmenuView: routing to WIP To Bill Workbench. wipBillingView is", wipBillingView)
            if (wipBillingView && wipBillingView.applyInitialState) {
                wipBillingView.applyInitialState(state)
            } else {
                console.log("PlaceholderSubmenuView: ERROR - wipBillingView is null or undefined when trying to apply state!")
            }
        }
        if (root.activeIsDocketActivityReport() && docketActivityReportPanel && docketActivityReportPanel.applyState) {
            docketActivityReportPanel.applyState(state, true)
        }
        var matterTimeLedgerShell = matterTimeLedgerLoader.item
        var matterTimeLedgerPanel = matterTimeLedgerShell ? matterTimeLedgerShell["reportPanel"] : null
        if (root.activeIsMatterTimeLedger() && matterTimeLedgerPanel
                && matterTimeLedgerPanel.applyState) {
            matterTimeLedgerPanel.applyState(state)
        }
        if (root.activeIsInvoiceBuilder() && invoiceBuilderView) {
            var dn = root.initialInvoiceDraftNumber()
            invoiceBuilderView._loadDrafts()
            if (dn) {
                invoiceBuilderView.draftNum = dn
            }
        }
    }

    function gotoNode(nodeId) {
        root.activeNodeId = String(nodeId || "")
        ensureActiveNode()
        if (!_hydrating) {
            // Reports do not have a draft to save. In particular, D17 used to
            // inherit the generic placeholder's dirty flag and showed an
            // alarming but false "Unsaved" badge on first open.
            root.dirty = !root.activeIsStatementOfAccount()
        }
    }

    onNavItemsChanged: ensureActiveNode()
    onDefaultNodeIdChanged: ensureActiveNode()
    onActiveNodeIdChanged: {
        if (root.activeIsStatementOfAccount()) {
            root.dirty = false
        }
        if (root._hydrating) return
        if (root.activeIsNewClientWizard()) {
            root.refreshParentClientOptions()
            root.applyClientWizardAutoPopulate()
        }
        if (root.activeIsNewMatterWizard()) {
            root.refreshParentClientOptions()
            root.refreshMatterWizardClientOptions()
            if (!root.matterEditMode && root.selectedClientName.length > 0) {
                _setComboBoxSilently(matterClientCombo, root.selectedClientName)
            }
            if (!root.matterEditMode && String(matterNumberInput.text || "").trim().length <= 0) {
                root.matterNumberAutoSync = true
            }
            root.applyMatterWizardAutoPopulate()
        }
        if (root.activeIsClientDirectory()) {
            root.refreshClientDirectory(false)
        }
        if (root.activeIsClientProfile360()) {
            root.refreshClientDirectory(false)
            root.autoLoadSelectedClientProfile("")
        }
        if (root.activeIsMatterDirectory()) {
            root.refreshMatterDirectory(false)
        }
        if (root.activeIsMatterProfile360()) {
            root.refreshMatterDirectory(false)
            root.loadSelectedMatterProfile("")
        }
        if (root.activeIsGlobalSearch()) {
            root.refreshGlobalSearchResults()
        }
        if (root.activeIsDocketActivityReport() && docketActivityReportPanel && docketActivityReportPanel.runReport) {
            docketActivityReportPanel.runReport()
        }
        if (root.activeIsTransactionsMaster() && transactionMasterView) {
            transactionMasterView.refreshLookupData()
        }
        if (root.activeIsPaymentEntry() && paymentEntryView) {
            paymentEntryView.refreshInvoices()
        }
    }

    Connections {
        target: root.appRef
        ignoreUnknownSignals: true
        function onMatterFinancialSummaryReady(requestId, summary) {
            if (String(requestId || "") !== root.matterFinancialSummaryToken) return
            root.matterFinancialSummaryLoading = false
            root.matterFinancialSummary = summary || ({ "ok": false })
        }
        function onMatterFinancialSummaryFailed(requestId, message) {
            if (String(requestId || "") !== root.matterFinancialSummaryToken) return
            root.matterFinancialSummaryLoading = false
            root.matterFinancialSummary = ({
                "ok": false,
                "matterId": root.selectedMatterId,
                "message": String(message || "Could not load WIP and unpaid invoices.")
            })
        }
        function onBackendBootChanged() {
            if (!(root.appRef && root.appRef.backendBooted)) return
            root.refreshParentClientOptions()
            root.refreshClientDirectory(false)
            root.refreshMatterDirectory(false)
            root.refreshMatterWizardClientOptions()
            if (transactionMasterView && transactionMasterView.refreshLookupData) {
                transactionMasterView.refreshLookupData()
            }
            if (paymentEntryView && paymentEntryView.refreshInvoices) {
                paymentEntryView.refreshInvoices()
            }
            if (root.activeIsGlobalSearch()) {
                root.refreshGlobalSearchResults()
            }
            if (root.activeIsDocketActivityReport() && docketActivityReportPanel && docketActivityReportPanel.runReport) {
                docketActivityReportPanel.runReport()
            }
            if (root.activeIsClientProfile360()) {
                root.autoLoadSelectedClientProfile("")
            }
            if (root.activeIsMatterProfile360()) {
                root.loadSelectedMatterProfile("")
            }
        }
        function onClientDataChanged() {
            root.refreshParentClientOptions()
            root.refreshClientDirectory(false)
            root.refreshMatterDirectory(false)
            root.refreshMatterWizardClientOptions()
            if (transactionMasterView && transactionMasterView.refreshLookupData) {
                transactionMasterView.refreshLookupData()
            }
            if (paymentEntryView && paymentEntryView.refreshInvoices) {
                paymentEntryView.refreshInvoices()
            }
            if (root.activeIsGlobalSearch()) {
                root.refreshGlobalSearchResults()
            }
            if (root.activeIsDocketActivityReport() && docketActivityReportPanel && docketActivityReportPanel.runReport) {
                docketActivityReportPanel.runReport()
            }
            if (root.activeIsClientProfile360()) {
                root.autoLoadSelectedClientProfile("")
            }
            if (root.activeIsMatterProfile360()) {
                root.loadSelectedMatterProfile("")
            }
        }

        function onTransactionDataChanged() {
            if (transactionMasterView && transactionMasterView.loadRecentTransactions) {
                transactionMasterView.loadRecentTransactions()
            }
            if (paymentEntryView && paymentEntryView.refreshInvoices) {
                paymentEntryView.refreshInvoices()
            }
            if (root.activeIsGlobalSearch()) {
                root.refreshGlobalSearchResults()
            }
        }

        function onTransactionLookupDataChanged() {
            if (transactionMasterView && transactionMasterView.refreshLookupData) {
                transactionMasterView.refreshLookupData()
            }
        }
    }

    JellyCalendar {
        id: clientWizardCalendar
        t: root.t
        metrics: root.responsiveMetrics
        hostWindow: root.Window.window
        onDatePicked: function(d) {
            var iso = Qt.formatDate(d, "yyyy-MM-dd")
            if (root.clientWizardDateTarget === "dateClientAdded") {
                dateClientAddedInput.text = iso
            } else if (root.clientWizardDateTarget === "engagementStart") {
                engagementStartInput.text = iso
            } else if (root.clientWizardDateTarget === "birthday") {
                birthdayInput.text = iso
            } else if (root.clientWizardDateTarget === "matterDateOfEngagement") {
                matterDateOfEngagementInput.text = iso
            } else if (root.clientWizardDateTarget === "matterDateOpened") {
                matterDateOpenedInput.text = iso
            } else if (root.clientWizardDateTarget === "matterDateClosed") {
                matterDateClosedInput.text = iso
            }
            root.clientWizardDateTarget = ""
            if (!root._hydrating) root.dirty = true
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.isProMode ? root.proBackground : root._bg
        z: -3
    }

    Image {
        id: laneBackdrop
        visible: !root.isProMode
        anchors.fill: parent
        source: root.themeBackgroundSource()
        fillMode: Image.PreserveAspectCrop
        smooth: true
        asynchronous: false
        retainWhileLoading: true
        cache: true
        mipmap: true
        opacity: root.lightTheme ? 0.50 : 0.72
        z: -2
        layer.enabled: true
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: root.lightTheme ? 0.02 : 0.06
            blurMax: 44
            saturation: root.lightTheme ? 0.12 : 0.30
            brightness: root.lightTheme ? 0.05 : -0.02
            colorizationColor: root._accent
            colorization: root.backgroundColorizationStrength()
            autoPaddingEnabled: false
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.isProMode
            ? "transparent"
            : Qt.rgba(root._panelBase.r, root._panelBase.g, root._panelBase.b, root.lightTheme ? 0.22 : 0.14)
        z: -1
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.pageMarginPct, 10)
        spacing: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.pageSpacingPct * 0.70, 6)

        Rectangle {
            id: laneSidebar
            Layout.preferredWidth: ((root.externalNavigationShell && root.isProMode) || root.detachedWindow)
                ? 0
                : root.ratioPxW(0.228, 224)
            Layout.fillHeight: true
            visible: !((root.externalNavigationShell && root.isProMode) || root.detachedWindow)
            enabled: visible
            radius: root.sectionRadiusPx
            color: root.isProMode ? root.proSurface : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.88)
            border.width: root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
            border.color: root.isProMode ? root.proBorder : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                spacing: root.isProMode ? 10 : root.ratioPx(0.0035, 2)

                Text {
                    Layout.fillWidth: true
                    text: root.titleText
                    color: root.isProMode ? root.proInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.96)
                    font.family: visualRules.textFontFamily
                    font.pixelSize: root.isProMode
                        ? visualRules.proSectionTitleFontPx
                        : root.ratioPx(root.scaleRatios.headerSubtitleFontPct * 1.03, root.metricFloor("fontFloorLabelPx", 10))
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: "Pathway map"
                    color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.70)
                    font.family: visualRules.textFontFamily
                    font.pixelSize: root.isProMode
                        ? visualRules.proCaptionFontPx
                        : root.ratioPx(root.scaleRatios.hintFontPct * 0.88, root.metricFloor("fontFloorLabelPx", 8))
                    elide: Text.ElideRight
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.isProMode
                    spacing: root.ratioPx(0.0045, 4)
                    Repeater {
                        model: root.laneSwitchModel
                        delegate: Rectangle {
                            id: laneChip
                            required property var modelData
                              Layout.fillWidth: true
                              Layout.preferredHeight: root.ratioPxH(0.033, 24)
                              radius: height / 2
                              property bool active: root.tileIndex === laneChip.modelData.tileIndex
                              property bool hovered: laneChipHover.containsMouse
                              color: active
                                  ? root.sidebarHoverFill(active, true, 0.24, 0.98, 0.82)
                                  : root.sidebarHoverFill(active, hovered, 0.24, 0.98, 0.82)
                              border.width: 1
                              border.color: active
                                  ? root.sidebarHoverBorder(active, true, 0.72, 0.98, 0.16)
                                  : root.sidebarHoverBorder(active, hovered, 0.72, 0.98, 0.16)
Behavior on color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}
Behavior on border.color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}

                            Text {
                                anchors.centerIn: parent
                                readonly property real labelWidthPx: Math.max(1, parent.width - root.ratioPx(0.010, 8))
                                width: labelWidthPx
                                text: String(laneChip.modelData.title || "")
                                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.90)
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                font.pixelSize: root.ratioPx(0.0090, root.metricFloor("fontFloorLabelPx", 7))
                                minimumPixelSize: Math.max(6, root.readableMinFontPx() - 2)
                                fontSizeMode: Text.Fit
                                font.weight: Font.DemiBold
                            }

                            MouseArea {
                                id: laneChipHover
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton
                                cursorShape: laneChip.active ? Qt.ArrowCursor : Qt.PointingHandCursor
                                onClicked: function(mouse) {
                                    mouse.accepted = true
                                    if (!laneChip.active) {
                                        root.moduleJumpRequested(laneChip.modelData.tileIndex, root.snapshotState())
                                    }
                                }
                            }
                            ToolTip.visible: laneChipHover.containsMouse
                            ToolTip.delay: 280
                            ToolTip.text: String(laneChip.modelData.title || "")
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: root.isProMode ? root.proBorder : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth

                    ListView {
                        id: navList
                        width: parent.width
                        model: root.normalizedNavItems()
                        spacing: root.ratioPx(0.0042, 3)
                        delegate: Rectangle {
                            id: navRow
                            required property var modelData
                            width: navList.width
                              height: root.ratioPxH(0.050, 36)
                              radius: root.isProMode ? visualRules.radiusControl : Math.max(6, root.ratioPx(root.scaleRatios.descCornerPct * 0.80, 7))
                              property bool current: String(modelData.id || "") === String(root.activeNodeId || "")
                              property bool hovered: navHover.containsMouse
                              color: current
                                  ? root.sidebarHoverFill(current, true, 0.22, 0.96, 0.80)
                                  : root.sidebarHoverFill(current, hovered, 0.22, 0.96, 0.80)
                              border.width: 1
                              border.color: current
                                  ? root.sidebarHoverBorder(current, true, 0.68, 0.94, 0.16)
                                  : root.sidebarHoverBorder(current, hovered, 0.68, 0.94, 0.16)
Behavior on color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}
Behavior on border.color {
    ColorAnimation {
        duration: 160
        easing.type: Easing.OutCubic
    }
}

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: root.ratioPx(0.0062, 5)
                                anchors.rightMargin: root.ratioPx(0.0062, 5)
                                spacing: root.ratioPx(0.0035, 3)

                                Text {
                                    Layout.fillWidth: true
                                    text: String(navRow.modelData.title || "Placeholder Node")
                                    color: root.isProMode
                                        ? (navRow.current || navRow.hovered ? root.proInk : root.proMutedInk)
                                        : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.93)
                                    elide: Text.ElideRight
                                    font.family: visualRules.textFontFamily
                                    font.pixelSize: root.isProMode
                                        ? visualRules.proLabelFontPx
                                        : root.ratioPx(0.0120, root.metricFloor("fontFloorLabelPx", 9))
                                    fontSizeMode: Text.Fit
                                    minimumPixelSize: Math.max(7, root.readableMinFontPx() - 1)
                                    font.weight: navRow.current ? Font.DemiBold : Font.Medium
                                  }
                              }

                            MouseArea {
                                id: navHover
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.LeftButton
                                cursorShape: navRow.current !== undefined ? (navRow.current ? Qt.ArrowCursor : Qt.PointingHandCursor) : (navRow.isCurrent ? Qt.ArrowCursor : Qt.PointingHandCursor)
                                onPressed: function(mouse) { mouse.accepted = false }
                            }

                              TapHandler {
                                  enabled: !navRow.current
                                  onTapped: root.gotoNode(navRow.modelData.id)
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: laneCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.isProMode ? 0 : root.sectionRadiusPx
            color: root.isProMode ? "transparent" : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.86)
            border.width: root.isProMode ? 0 : root.ratioPx(root.scaleRatios.descIdleBorderPct, 1)
            border.color: root.isProMode ? "transparent" : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.10)
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.isProMode ? 0 : root.ratioPx(root.scaleRatios.pageMarginPct * 0.66, 8)
                spacing: root.isProMode ? 10 : root.ratioPx(root.scaleRatios.pageSpacingPct * 0.52, 5)

                RowLayout {
                    id: headerRow
                    Layout.fillWidth: true
                    Layout.fillHeight: false
                    Layout.bottomMargin: root.isProMode ? 0 : Math.max(1, Math.round(root.controlGapPx * 0.20))
                    Layout.preferredHeight: root.isProMode
                        ? visualRules.proWorkspaceHeaderHeightPx
                        : Math.max(
                            root.ratioPxH(root.scaleRatios.headerHeightPct * 0.58, 30),
                            headerTitleText.contentHeight
                                + Math.max(headerSubtitleText.contentHeight, root.ratioPxH(0.012, 9))
                                + headerInfoColumn.spacing
                                + root.ratioPxH(0.003, 2),
                            root.ratioPxH(0.038, 30)
                        )
                    spacing: root.isProMode ? 10 : root.ratioPx(root.scaleRatios.headerSpacingPct * 0.72, 5)

                    ColumnLayout {
                        id: headerInfoColumn
                        Layout.fillWidth: true
                        spacing: root.isProMode ? visualRules.proWorkspaceHeaderGapPx : root.ratioPx(0.0042, 2)
                        Text {
                            id: headerTitleText
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.isProMode ? 22 : root.ratioPxH(0.026, 19)
                            text: {
                                var titleStr = String(root.currentNode().title || "Placeholder")
                                if (root.activeIsNewMatterWizard() && root.matterEditMode) titleStr = "Edit Matter Profile"
                                else if (root.activeIsNewClientWizard() && root.clientEditMode) titleStr = "Edit Client Profile"
                                return root.isProMode ? titleStr : (root.titleText + " - " + titleStr)
                            }
                            color: root.isProMode ? root.proInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.98)
                            font.family: visualRules.textFontFamily
                            font.pixelSize: root.isProMode
                                ? visualRules.proWorkspaceTitleFontPx
                                : Math.max(14, Math.min(28, root.ratioPxH(0.024, 18)))
                            fontSizeMode: Text.Fit
                            minimumPixelSize: root.isProMode ? 12 : 10
                            maximumLineCount: 1
                            wrapMode: Text.NoWrap
                            elide: root.isProMode ? Text.ElideRight : Text.ElideNone
                            font.weight: Font.DemiBold
                        }
                        Text {
                            id: headerSubtitleText
                            Layout.fillWidth: true
                            text: root.summaryLineA()
                            color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.74)
                            font.family: visualRules.textFontFamily
                            font.pixelSize: root.isProMode
                                ? visualRules.proWorkspaceSubtitleFontPx
                                : Math.max(
                                    6,
                                    Math.min(
                                        root.ratioPxH(0.014, 10),
                                        Math.floor(Math.max(10, headerTitleText.fontInfo.pixelSize) * 0.54)
                                    )
                                )
                            maximumLineCount: 1
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                            font.weight: Font.Medium
                        }
                    }

                    Rectangle {
                        id: summaryCapsule
                        // A Statement of Account is a focused, client-facing report.
                        // The lane-level queue counter has no bearing on it.
                        visible: !root.activeIsStatementOfAccount()
                        readonly property bool activeClientsShortcut: root.tileIndex === 0
                        Layout.preferredWidth: root.ratioPxW(0.225, 210)
                        Layout.minimumWidth: root.ratioPxW(0.185, 170)
                        Layout.preferredHeight: root.ratioPxH(0.038, 30)
                        radius: root.isProMode ? visualRules.radiusPanel : height / 2
                        color: root.isProMode ? root.proSurface : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.78)
                        border.width: 1
                        border.color: root.isProMode ? root.proBorder : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.18)

                        Column {
                            id: summaryColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: root.ratioPx(0.008, 6)
                            anchors.rightMargin: root.ratioPx(0.008, 6)
                            spacing: 0
                            Text {
                                id: summaryHeadlineText
                                width: Math.max(1, summaryColumn.width)
                                text: root.summaryHeadline()
                                color: root.isProMode ? root.proInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.94)
                                font.family: visualRules.textFontFamily
                                font.pixelSize: root.isProMode
                                    ? visualRules.proLabelFontPx
                                    : Math.max(9, Math.min(22, root.ratioPxH(0.018, 12)))
                                fontSizeMode: Text.Fit
                                minimumPixelSize: 8
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                            Text {
                                width: Math.max(1, summaryColumn.width)
                                text: root.summaryLineB()
                                visible: false
                                color: root.isProMode ? root.proMutedInk : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.72)
                                font.family: visualRules.textFontFamily
                                font.pixelSize: root.isProMode
                                    ? visualRules.proCaptionFontPx
                                    : Math.max(8, Math.min(22, root.ratioPxH(0.016, 9)))
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                        }

                        HoverHandler {
                            id: summaryCapsuleHover
                            acceptedDevices: PointerDevice.Mouse
                        }
                        ToolTip.visible: summaryCapsuleHover.hovered
                        ToolTip.delay: 260
                        ToolTip.text: root.summaryHeadline()
                            + "\n" + root.summaryLineB()
                            + (summaryCapsule.activeClientsShortcut ? "\nOpen Client Directory (Active Clients)" : "")
                        TapHandler {
                            enabled: summaryCapsule.activeClientsShortcut
                            onTapped: {
                                root.clientDirectoryMode = "active"
                                root.clientDirectoryQuery = ""
                                root.clientDirectoryQuery = ""
                                root.refreshClientDirectory(true)
                                root.gotoNode("A01")
                            }
                        }
                    }
                }

                Rectangle {
                    id: proFormCard
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.isProMode ? root.sectionRadiusPx : 0
                    color: root.isProMode ? root.proCanvas : "transparent"
                    border.width: root.isProMode ? 1 : 0
                    border.color: root.isProMode ? root.proBorder : "transparent"
                    clip: true

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: root.isProMode ? 14 : 0
                        spacing: root.isProMode ? 14 : root.ratioPx(root.scaleRatios.pageSpacingPct * 0.52, 5)

                GridLayout {
                    id: compactFormGrid
                    visible: !root.activeIsNewClientWizard()
                        && !root.activeIsClientDirectory()
                        && !root.activeIsClientProfile360()
                        && !root.activeIsNewMatterWizard()
                        && !root.activeIsMatterDirectory()
                        && !root.activeIsMatterProfile360()
                        && !root.activeIsGlobalSearch()
                        && !root.activeIsFinancialDashboard()
                        && !root.activeIsARAgingReport()
                        && !root.activeIsDocketActivityReport()
                        && !root.activeIsProductivityDashboard()
                        && !root.activeIsLedgerReport()
                        && !root.activeIsStatementOfAccount()
                        && !root.activeIsTransactionsMaster()
                        && !root.activeIsPaymentEntry()
                        && !root.activeIsLegacyDocketsImport()
                        && !root.activeIsWipToBill()
                        && !root.activeIsInvoiceBuilder()
                        && !root.activeIsInvoiceDirectory()
                        && !root.activeIsInvoiceReversal()
                        && !root.activeIsAccountsPayable()
                    Layout.fillWidth: true
                    Layout.fillHeight: false
                    columns: root.formGridColumns(4, root.formGridLayoutWidth(compactFormGrid))
                    columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                    rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)

                    ModernTextField {
                        id: queryInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: root.activeIsGlobalSearch() ? "Global Search Query" : "Lookup / Filter"
                        text: ""
                        Layout.fillWidth: true
                        Layout.columnSpan: root.activeIsGlobalSearch()
                            ? compactFormGrid.columns
                            : root.formGridSpan(compactFormGrid.columns, 2)
                        Layout.preferredHeight: root.fieldHeightPx
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && root.activeIsGlobalSearch()) {
                                root.refreshGlobalSearchResults()
                            }
                        }
                    }

                    ModernTextField {
                        id: ownerInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Owner"
                        text: "Assigned User"
                        visible: !root.activeIsGlobalSearch()
                        Layout.fillWidth: true
                        Layout.columnSpan: root.formGridSpan(compactFormGrid.columns, 2)
                        Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernComboBox {
                        id: statusCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Status"
                        visible: !root.activeIsGlobalSearch()
                        Layout.fillWidth: true
                        Layout.columnSpan: root.formGridSpan(compactFormGrid.columns, 2)
                        Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                        fullModel: ["Placeholder", "In Design", "Ready for Wiring", "Live"]
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                        onActivated: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Node ID"
                        text: String(root.activeNodeId || "")
                        readOnly: true
                        visible: !root.activeIsGlobalSearch()
                        Layout.fillWidth: true
                        Layout.columnSpan: root.formGridSpan(compactFormGrid.columns, 2)
                        Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                    }
                }

                Item {
                    visible: root.activeIsClientDirectory()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ClientDirectoryPanel {
                        anchors.fill: parent
                        visible: parent.visible
                        root: root
                    }
                }

                Item {
                    visible: root.activeIsClientProfile360()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ClientProfilePanel {
                        anchors.fill: parent
                        visible: parent.visible
                        root: root
                    }
                }

                Item {
                    visible: root.activeIsGlobalSearch()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    GlobalSearchPanel {
                        anchors.fill: parent
                        visible: parent.visible
                        root: root
                    }
                }

                Rectangle {
                    visible: root.activeIsFinancialDashboard()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    FinancialDashboardPanel {
                        id: financialDashboardPanel
                        anchors.fill: parent
                        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                        t: root.t
                        metrics: root.responsiveMetrics
                        appRef: root.appRef
                        windowRef: root.windowRef
                        sfxBus: root.sfxBus
                        sectionRadiusPx: root.sectionRadiusPx
                        fieldHeightPx: root.fieldHeightPx
                        autoLoadOnVisible: true
                    }
                }

                Rectangle {
                    visible: root.activeIsARAgingReport()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    ARAgingReportPanel {
                        id: arAgingReportPanel
                        anchors.fill: parent
                        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                        t: root.t
                        metrics: root.responsiveMetrics
                        appRef: root.appRef
                        windowRef: root.windowRef
                        sfxBus: root.sfxBus
                        sectionRadiusPx: root.sectionRadiusPx
                        fieldHeightPx: root.fieldHeightPx
                        autoLoadOnVisible: true
                        onReportWindowRequested: function(reportDocument) {
                            root.reportWindowRequested(reportDocument)
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsDocketActivityReport()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    DocketActivityReportPanel {
                        id: docketActivityReportPanel
                        anchors.fill: parent
                        anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                        t: root.t
                        metrics: root.responsiveMetrics
                        appRef: root.appRef
                        windowRef: root.windowRef
                        sfxBus: root.sfxBus
                        sectionRadiusPx: root.sectionRadiusPx
                        fieldHeightPx: root.fieldHeightPx
                        autoLoadOnVisible: true
                        onEditRequested: function(row) {
                            root.openDocketReportEntryForEdit(row)
                        }
                        onReportWindowRequested: function(reportDocument) {
                            root.reportWindowRequested(reportDocument)
                        }
                    }
                }

                Loader {
                    id: clientLedgerReportLoader
                    active: root.activeIsClientLedgerReport()
                    visible: active
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    sourceComponent: Component {
                        Rectangle {
                            anchors.fill: parent
                            radius: root.sectionRadiusPx
                            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                            border.width: 1
                            border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                            ClientLedgerReportPanel {
                                onReportWindowRequested: function(reportDocument) { root.reportWindowRequested(reportDocument) }
                                onWorkspaceOpenRequested: function(tileIndex, nodeId, state) { root.workspaceOpenRequested(tileIndex, nodeId, state) }
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                windowRef: root.windowRef
                                sfxBus: root.sfxBus
                                sectionRadiusPx: root.sectionRadiusPx
                                fieldHeightPx: root.fieldHeightPx
                                autoLoadOnVisible: true
                            }
                        }
                    }
                }

                Loader {
                    id: matterTimeLedgerLoader
                    active: root.activeIsMatterTimeLedger()
                    visible: active
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    sourceComponent: Component {
                        Rectangle {
                            property alias reportPanel: matterTimeLedgerReportPanel
                            anchors.fill: parent
                            radius: root.sectionRadiusPx
                            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                            border.width: 1
                            border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                            MatterTimeLedgerReportPanel {
                                id: matterTimeLedgerReportPanel
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                windowRef: root.windowRef
                                sfxBus: root.sfxBus
                                startupState: root.initialState
                            }
                        }
                    }
                }

                Loader {
                    id: statementOfAccountLoader
                    // Do not construct a workbook-backed report view merely
                    // because the broad Finance workspace was loaded.  The
                    // previous hidden Rectangle still created the full
                    // Statement component (and triggered its data load).
                    active: root.activeIsStatementOfAccount()
                    visible: root.activeIsStatementOfAccount()
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    sourceComponent: Component {
                        Rectangle {
                            anchors.fill: parent
                            radius: root.sectionRadiusPx
                            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                            border.width: 1
                            border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                            StatementOfAccountView {
                                onReportWindowRequested: function(reportDocument) { root.reportWindowRequested(reportDocument) }
                                onWorkspaceOpenRequested: function(tileIndex, nodeId, state) {
                                    root.workspaceOpenRequested(tileIndex, nodeId, state)
                                }
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                sfxBus: root.sfxBus
                                selectedClientId: root.selectedClientId
                                selectedClientLabel: root.selectedClientName
                            }
                        }
                    }
                }

                Item {
                    visible: root.activeIsMatterDirectory()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    MatterDirectoryPanel {
                        anchors.fill: parent
                        visible: parent.visible
                        root: root
                    }
                }

                Item {
                    visible: root.activeIsMatterProfile360()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    MatterProfilePanel {
                        anchors.fill: parent
                        visible: parent.visible
                        root: root
                    }
                }

                Item {
                    visible: root.activeIsCorporateDirectory()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    CorporateDirectoryPanel {
                        anchors.fill: parent
                        visible: parent.visible
                        activeWorkspace: root
                    }
                }

                Item {
                    visible: root.activeIsCorporateProfile()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    CorporateProfilePanel {
                        anchors.fill: parent
                        visible: parent.visible
                        activeWorkspace: root
                        startupParams: root.initialState
                    }
                }

                Item {
                    visible: root.activeIsCorporateTransactionWizard()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    CorporateTransactionWizard {
                        anchors.fill: parent
                        visible: parent.visible
                        activeWorkspace: root
                    }
                }

                Rectangle {
                    visible: root.activeIsTransactionsMaster()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: transactionMasterLoader
                        anchors.fill: parent
                        active: parent.visible
                        onLoaded: {
                            if (item && item.applyState && root._pendingStateForLoader) {
                                item.applyState(root._pendingStateForLoader)
                            }
                        }
                        sourceComponent: Component {
                            TransactionsMasterView {
                                id: transactionMasterView
                                anchors.fill: parent
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                sfxBus: root.sfxBus
                                onFormDirtyChanged: function(isDirty) {
                                    if (!root._hydrating) root.dirty = !!isDirty
                                }
                                onSaveFinished: function(ok, message, transactionId) {
                                    root.lastSaveOk = !!ok
                                    root.saveMessage = String(message || "")
                                    root.lastSavedTransactionId = String(transactionId || "")
                                    if (ok) {
                                        root.dirty = false
                                        root.submitRequested(root.snapshotState())
                                    } else {
                                        root.dirty = true
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsPaymentEntry()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: paymentEntryLoader
                        anchors.fill: parent
                        active: parent.visible
                        onLoaded: {
                            if (item && item.applyState && root._pendingStateForLoader) {
                                item.applyState(root._pendingStateForLoader)
                            }
                        }
                        sourceComponent: Component {
                            PaymentEntryView {
                                id: paymentEntryView
                                anchors.fill: parent
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                sfxBus: root.sfxBus
                                currentNodeId: String(root.currentNode().id || "")
                                onFormDirtyChanged: function(isDirty) {
                                    if (!root._hydrating) root.dirty = !!isDirty
                                }
                                onSaveFinished: function(ok, message, paymentId) {
                                    root.lastSaveOk = !!ok
                                    root.saveMessage = String(message || "")
                                    root.lastSavedTransactionId = String(paymentId || "")
                                    if (ok) {
                                        root.dirty = false
                                        root.submitRequested(root.snapshotState())
                                    } else {
                                        root.dirty = true
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsProductivityDashboard()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "transparent"

                    Loader {
                        anchors.fill: parent
                        active: root.activeIsProductivityDashboard()
                        asynchronous: true
                        source: "../components/ProductivityReportPanel.qml"
                        onLoaded: {
                            item.t = Qt.binding(function() { return root.t })
                            item.metrics = Qt.binding(function() { return root.responsiveMetrics })
                            item.windowRef = Qt.binding(function() { return root.windowRef })
                            item.sfxBus = Qt.binding(function() { return root.sfxBus })
                            item.appRef = Qt.binding(function() { return root.appRef })
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsWipToBill()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: wipBillingLoader
                        anchors.fill: parent
                        active: parent.visible
                        onLoaded: {
                            if (item && item.applyInitialState && root._pendingStateForLoader) {
                                item.applyInitialState(root._pendingStateForLoader)
                            }
                        }
                        sourceComponent: Component {
                            WIPBillingWizardView {
                                id: wipBillingView
                                anchors.fill: parent
                                t: root.t
                                appRef: root.appRef
                                windowRef: root.windowRef
                                sfxBus: root.sfxBus
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsAccountsPayable()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: accountsPayableLoader
                        anchors.fill: parent
                        active: parent.visible
                        sourceComponent: Component {
                            AccountsPayableView {
                                id: accountsPayableView
                                anchors.fill: parent
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                sfxBus: root.sfxBus
                                startupState: root.initialState
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsInvoiceBuilder()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: invoiceBuilderLoader
                        anchors.fill: parent
                        active: parent.visible
                        onLoaded: {
                            if (item && root._pendingStateForLoader) {
                                var dn = root.initialInvoiceDraftNumber()
                                item._loadDrafts()
                                if (dn) {
                                    item.applyInitialState(root._pendingStateForLoader)
                                } else {
                                    item.applyInitialState(root._pendingStateForLoader)
                                }
                            }
                        }
                        sourceComponent: Component {
                            InvoiceBuilderView {
                                id: invoiceBuilderView
                                anchors.fill: parent
                                t: root.t
                                appRef: root.appRef
                                windowRef: root.windowRef
                                sfxBus: root.sfxBus
                                draftNum: root.initialInvoiceDraftNumber()
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsInvoiceDirectory()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: invoiceDirectoryLoader
                        anchors.fill: parent
                        active: parent.visible
                        onLoaded: {
                            if (item && item.applyJumpState && root._pendingStateForLoader) {
                                item.applyJumpState(root._pendingStateForLoader)
                            }
                        }
                        sourceComponent: Component {
                            InvoiceReversalView {
                                id: invoiceDirectoryView
                                anchors.fill: parent
                                directoryMode: true
                                t: root.t
                                appRef: root.appRef
                                appController: root.appRef
                                windowRef: root.windowRef
                                selectedInvoiceNum: root.initialInvoiceNumber()
                                onWorkspaceOpenRequested: function(tileIndex, nodeId, state) { root.workspaceOpenRequested(tileIndex, nodeId, state) }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsInvoiceReversal()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: invoiceReversalLoader
                        anchors.fill: parent
                        active: parent.visible
                        onLoaded: {
                            if (item && item.applyJumpState && root._pendingStateForLoader) {
                                item.applyJumpState(root._pendingStateForLoader)
                            }
                        }
                        sourceComponent: Component {
                            InvoiceReversalView {
                                id: invoiceReversalView
                                anchors.fill: parent
                                t: root.t
                                appRef: root.appRef
                                appController: root.appRef
                                windowRef: root.windowRef
                                selectedInvoiceNum: root.initialInvoiceNumber()
                                onWorkspaceOpenRequested: function(tileIndex, nodeId, state) { root.workspaceOpenRequested(tileIndex, nodeId, state) }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: root.activeIsLegacyDocketsImport()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.74)
                    border.width: 1
                    border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                    Loader {
                        id: legacyDocketsImportLoader
                        anchors.fill: parent
                        active: parent.visible
                        sourceComponent: Component {
                            LegacyDocketsImportView {
                                anchors.fill: parent
                                anchors.margins: root.ratioPx(root.scaleRatios.descPadPct * 1.15, 10)
                                t: root.t
                                metrics: root.responsiveMetrics
                                appRef: root.appRef
                                sfxBus: root.sfxBus
                            }
                        }
                    }
                }
                ScrollView {
                    visible: root.activeIsNewClientWizard()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    contentHeight: wizardColumn.implicitHeight + root.ratioPxH(0.020, 12)
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        id: wizardColumn
                        width: Math.max(1, parent.width - root.ratioPxW(0.026, 20))
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct * 0.72, 8)

                        // --- Section: Core Profile ---
                        Text {
                            text: "Core Profile"
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.9)
                            font.pixelSize: root.ratioPx(0.013, 13)
                            font.weight: Font.DemiBold
                            Layout.topMargin: root.ratioPxH(0.006, 5)
                            Layout.fillWidth: true
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.formGridColumns(2, wizardColumn.width)
                            columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                            rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)
                    ModernTextField {
                        id: clientNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Client Name"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) {
                                root.applyClientWizardAutoPopulate()
                            }
                            if (typeof appRef !== "undefined" && appRef && appRef.previewLegacyClientCode) {
                                legacyClientCodePreview.text = appRef.previewLegacyClientCode(clientNameInput.text)
                            }
                        }
                    }
                    ModernTextField {
                        id: legalNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "AKA"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                        }
                    }
                    ModernComboBox {
                        id: entityTypeCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Entity Type"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.entityTypeOptions
                        onActivated: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) {
                                root.refreshAutoSyncFlags()
                                root.applyClientWizardAutoPopulate()
                            }
                        }
                        onEditTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) {
                                root.refreshAutoSyncFlags()
                                root.applyClientWizardAutoPopulate()
                            }
                        }
                    }
                    ModernTextField {
                        id: firstNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "First Name"
                        visible: root.entityTypeIsIndividual()
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) {
                                root.syncIndividualDisplayFromParts()
                                root.refreshAutoSyncFlags()
                            }
                        }
                    }
                    ModernTextField {
                        id: middleNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Middle Name"
                        visible: root.entityTypeIsIndividual()
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) {
                                root.syncIndividualDisplayFromParts()
                                root.refreshAutoSyncFlags()
                            }
                        }
                    }
                    ModernTextField {
                        id: lastNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Last Name"
                        visible: root.entityTypeIsIndividual()
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: visible ? root.fieldHeightPx : 0
                        text: ""
                        Component.onCompleted: root.individualNameFieldsReady = true
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) {
                                root.syncIndividualDisplayFromParts()
                                root.refreshAutoSyncFlags()
                            }
                        }
                    }
                    ModernComboBox {
                        id: parentClientCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Client"
                        emptyOptionLabel: "No billing client"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.parentClientOptions
                        Component.onCompleted: root.refreshParentClientOptions()
                        onActiveFocusChanged: if (activeFocus) root.refreshParentClientOptions()
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: legacyClientCodePreview
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Legacy Code Preview"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        readOnly: true
                        enabled: false
                    }

                        }

                        // --- Section: Contact Information ---
                        Text {
                            text: "Contact Information"
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.9)
                            font.pixelSize: root.ratioPx(0.013, 13)
                            font.weight: Font.DemiBold
                            Layout.topMargin: root.ratioPxH(0.006, 5)
                            Layout.fillWidth: true
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.formGridColumns(2, wizardColumn.width)
                            columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                            rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)
                    ModernTextField {
                        id: principalNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Principal Name"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: principalPositionInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Principal Position"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: primaryEmailInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Primary Email"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: primaryPhoneInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Primary Phone"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: secondaryContactInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Secondary Contact"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: secondaryPositionInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Secondary Position"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: secondaryEmailInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Secondary Email"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: secondaryPhoneInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Secondary Phone"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: websiteInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Website"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                        }

                        // --- Section: Location ---
                        Text {
                            text: "Location"
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.9)
                            font.pixelSize: root.ratioPx(0.013, 13)
                            font.weight: Font.DemiBold
                            Layout.topMargin: root.ratioPxH(0.006, 5)
                            Layout.fillWidth: true
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.formGridColumns(2, wizardColumn.width)
                            columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                            rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)
                    ModernTextField {
                        id: addressLine1Input
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Address Line 1"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: addressLine2Input
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Address Line 2"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: cityInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "City"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: stateProvinceInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "State/Province"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: postalCodeInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Postal Code"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: countryInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Country"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                        }

                        // --- Section: Billing & Compliance ---
                        Text {
                            text: "Billing & Compliance"
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.9)
                            font.pixelSize: root.ratioPx(0.013, 13)
                            font.weight: Font.DemiBold
                            Layout.topMargin: root.ratioPxH(0.006, 5)
                            Layout.fillWidth: true
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.formGridColumns(2, wizardColumn.width)
                            columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                            rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)
                    ModernTextField {
                        id: taxIdInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Tax ID"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: industryInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Industry"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: billingEmailInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Email"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernComboBox {
                        id: clientStatusCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Client Status"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.clientStatusOptions
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernComboBox {
                        id: kycCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "KYC Status"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.kycOptions
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernComboBox {
                        id: onboardingCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Onboarding"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.onboardingOptions
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernComboBox {
                        id: retainerRequiredCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Retainer Required"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: ["Yes", "No"]
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: retainerAmountInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Retainer Amount"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                        }

                        // --- Section: Engagement Details ---
                        Text {
                            text: "Engagement Details"
                            color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.9)
                            font.pixelSize: root.ratioPx(0.013, 13)
                            font.weight: Font.DemiBold
                            Layout.topMargin: root.ratioPxH(0.006, 5)
                            Layout.fillWidth: true
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.formGridColumns(2, wizardColumn.width)
                            columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                            rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)
                    ModernTextField {
                        id: engagementStartInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Engagement Start"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: dateClientAddedInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Date Added"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: referralFromInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Referral From"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                    ModernTextField {
                        id: birthdayInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Birthday"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                        }

                        TextArea {
                            id: conflictNotesInput
                            visible: root.activeIsNewClientWizard()
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.ratioPxH(0.064, 56)
                            color: root._text
                            font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
                            wrapMode: Text.Wrap
                            placeholderText: "Conflict notes"
                            placeholderTextColor: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.50)
                            leftPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            topPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            onTextChanged: if (!root._hydrating) root.dirty = true
                            background: Rectangle {
                                color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.72)
                                radius: root.sectionRadiusPx
                                border.width: conflictNotesInput.activeFocus ? 2 : 1
                                border.color: conflictNotesInput.activeFocus
                                    ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.62)
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.18)
                            }
                        }

                        TextArea {
                            id: clientNotesInput
                            visible: root.activeIsNewClientWizard()
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.ratioPxH(0.074, 64)
                            color: root._text
                            font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
                            wrapMode: Text.Wrap
                            placeholderText: "Client notes"
                            placeholderTextColor: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.50)
                            leftPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            topPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                            onTextChanged: if (!root._hydrating) root.dirty = true
                            background: Rectangle {
                                color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.72)
                                radius: root.sectionRadiusPx
                                border.width: clientNotesInput.activeFocus ? 2 : 1
                                border.color: clientNotesInput.activeFocus
                                    ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.62)
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.18)
                            }
                        }

                    }
                }

                ScrollView {
                    visible: root.activeIsNewMatterWizard()
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    contentHeight: matterWizardColumn.implicitHeight + root.ratioPxH(0.020, 12)
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        id: matterWizardColumn
                        width: Math.max(1, parent.width - root.ratioPxW(0.026, 20))
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct * 0.72, 8)

                        GridLayout {
                            id: matterWizardGrid
                            Layout.fillWidth: true
                            columns: root.formGridColumns(4, matterWizardColumn.width)
                            columnSpacing: root.ratioPxW(root.scaleRatios.gridColumnSpacingPct, 8)
                            rowSpacing: root.ratioPxH(root.scaleRatios.gridRowSpacingPct, 8)

                    ModernComboBox {
                        id: matterClientCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Client"
                        emptyOptionLabel: "Select a client..."
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.matterClientOptions
                        Component.onCompleted: root.refreshMatterWizardClientOptions()
                        onActiveFocusChanged: if (activeFocus) root.refreshMatterWizardClientOptions()
                        onActivated: root.handleMatterClientActivated()
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    CheckBox {
                        id: matterJointRetainerCheck
                        text: "Joint retainer / multiple independent clients"
                        checked: false
                        Layout.fillWidth: true
                        Layout.columnSpan: root.formGridSpan(matterWizardGrid.columns, 2)
                        Layout.minimumHeight: root.fieldHeightPx
                        Layout.preferredHeight: root.fieldHeightPx
                        spacing: root.ratioPxW(0.008, 8)
                        indicator: Rectangle {
                            implicitWidth: root.ratioPx(0.018, 16)
                            implicitHeight: implicitWidth
                            x: root.ratioPx(0.006, 6)
                            y: Math.round((parent.height - height) / 2)
                            radius: 3
                            color: matterJointRetainerCheck.checked
                                ? root._accent : Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.78)
                            border.width: 1
                            border.color: matterJointRetainerCheck.checked
                                ? root._accent : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.34)
                            Text {
                                anchors.centerIn: parent
                                visible: matterJointRetainerCheck.checked
                                text: "✓"
                                color: SemanticTheme.readableInk(root._accent)
                                font.pixelSize: Math.max(10, Math.round(parent.height * 0.78))
                                font.weight: Font.Bold
                            }
                        }
                        contentItem: Text {
                            text: matterJointRetainerCheck.text
                            color: root._text
                            font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
                            font.weight: Font.Medium
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            leftPadding: matterJointRetainerCheck.indicator.width + root.ratioPxW(0.014, 12)
                            rightPadding: root.ratioPxW(0.010, 8)
                        }
                        background: Rectangle {
                            radius: Math.max(4, root.sectionRadiusPx - 3)
                            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.58)
                            border.width: 1
                            border.color: matterJointRetainerCheck.activeFocus
                                ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.70)
                                : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.18)
                        }
                        onToggled: {
                            if (!root._hydrating) root.setMatterJointRetainer(checked)
                        }
                    }

                    ColumnLayout {
                        visible: root.matterJointRetainer
                        Layout.fillWidth: true
                        Layout.columnSpan: matterWizardGrid.columns
                        spacing: root.ratioPxH(0.005, 5)

                        Text {
                            Layout.fillWidth: true
                            text: "Matter parties"
                            color: root._text
                            font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
                            font.weight: Font.DemiBold
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: root.ratioPxW(0.008, 8)

                            ModernComboBox {
                                id: matterPartyAddCombo
                                t: root.t
                                metrics: root.responsiveMetrics
                                label: "Add existing client"
                                emptyOptionLabel: "Select a client..."
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.fieldHeightPx
                                fullModel: root.matterClientOptions
                                onActivated: {
                                    var name = String(editText || "").trim()
                                    if (root._isNewClientOption(name)) {
                                        root.startNewClientFromMatterWizard("", true)
                                    } else if (root.addMatterParty(name, false)) {
                                        root.dirty = true
                                    }
                                    root._setComboBoxSilently(matterPartyAddCombo, "")
                                }
                            }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "New Client"
                                primary: false
                                Layout.preferredWidth: root.ratioPxW(0.112, 104)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.startNewClientFromMatterWizard("", true)
                            }
                        }

                        Repeater {
                            model: root.matterParties
                            delegate: Rectangle {
                                id: matterPartyRow
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: partyRowLayout.implicitHeight + root.ratioPxH(0.010, 8)
                                radius: root.sectionRadiusPx
                                color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.58)
                                border.width: 1
                                border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.16)

                                RowLayout {
                                    id: partyRowLayout
                                    anchors.fill: parent
                                    anchors.margins: root.ratioPx(0.006, 6)
                                    spacing: root.ratioPxW(0.006, 6)

                                    RadioButton {
                                        checked: !!matterPartyRow.modelData.isFileAnchor
                                        text: "File anchor"
                                        onToggled: if (checked) root.updateMatterParty(index, "isFileAnchor", true)
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: String(matterPartyRow.modelData.clientName || "")
                                        color: root._text
                                        font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorLabelPx", 8))
                                        elide: Text.ElideRight
                                    }

                                    ComboBox {
                                        id: matterPartyRoleCombo
                                        Layout.preferredWidth: root.ratioPxW(0.140, 140)
                                        model: root.matterPartyRoleOptions
                                        Component.onCompleted: {
                                            var role = String(matterPartyRow.modelData.role || "Joint client")
                                            var found = root.matterPartyRoleOptions.indexOf(role)
                                            currentIndex = found >= 0 ? found : 0
                                        }
                                        onActivated: root.updateMatterParty(index, "role", currentText)
                                    }

                                    CheckBox {
                                        checked: !!matterPartyRow.modelData.isBillingRecipient
                                        text: "Bill to"
                                        onToggled: root.updateMatterParty(index, "isBillingRecipient", checked)
                                    }

                                    ToolButton {
                                        text: "Remove"
                                        onClicked: root.removeMatterParty(index)
                                        ToolTip.visible: hovered
                                        ToolTip.text: "Remove this client from the matter"
                                    }
                                }
                            }
                        }

                        CheckBox {
                            id: jointNoConfidentialityCheck
                            text: "Joint clients acknowledge that material information may be shared among them"
                            checked: false
                            Layout.fillWidth: true
                            onToggled: if (!root._hydrating) {
                                root.matterJointNoConfidentialityConfirmed = checked
                                root.dirty = true
                            }
                        }

                        CheckBox {
                            id: jointInstructionsCheck
                            text: "Material instructions and approvals require all joint clients"
                            checked: true
                            Layout.fillWidth: true
                            onToggled: if (!root._hydrating) {
                                root.matterJointInstructionsRequireAll = checked
                                root.dirty = true
                            }
                        }

                        ModernTextField {
                            id: matterJointEngagementDocumentInput
                            t: root.t
                            metrics: root.responsiveMetrics
                            label: "Joint engagement document"
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.fieldHeightPx
                            text: ""
                            onTextChanged: if (!root._hydrating) root.dirty = true
                        }
                    }

                    ModernComboBox {
                        id: matterParentCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Client"
                        emptyOptionLabel: "No billing client"
                        visible: !root.matterJointRetainer
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.parentClientOptions
                        Component.onCompleted: root.refreshParentClientOptions()
                        onActiveFocusChanged: if (activeFocus) root.refreshParentClientOptions()
                        onEditTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            root.applyMatterWizardAutoPopulate()
                        }
                    }

                    ModernComboBox {
                        id: matterPracticeAreaCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Practice Area"
                        emptyOptionLabel: "Select practice area..."
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.practiceAreaOptions
                        onEditTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            root.matterTypeOptions = root.practiceAreaMatterTypes[editText] || [""]
                            if (!root._hydrating && root.matterTypeOptions.indexOf(matterTypeCombo.editText) === -1) {
                                matterTypeCombo.editText = ""
                            }
                        }
                    }

                    ModernComboBox {
                        id: matterTypeCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Matter Type"
                        emptyOptionLabel: "Select matter type..."
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.matterTypeOptions
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernComboBox {
                        id: matterStatusCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Status"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.matterStatusOptions
                        onEditTextChanged: {
                            if (root._hydrating) return
                            if (root.matterStatusSelectionIsBlocked(editText)) {
                                root._setComboBoxSilently(matterStatusCombo, root.matterPersistedStatus || "Open")
                                root.saveMessage = "Status cannot be changed while this matter has "
                                    + root.matterFinancialBlockerText()
                                    + ". Open the WIP ledger or unpaid invoice list below to resolve it first."
                                root.lastSaveOk = false
                                return
                            }
                            root.dirty = true
                        }
                    }

                    ModernComboBox {
                        id: matterResponsibleLawyerCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Responsible Lawyer"
                        emptyOptionLabel: "Select lawyer..."
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.lawyerOptions
                        Component.onCompleted: root.refreshLawyerOptions()
                        onActiveFocusChanged: if (activeFocus) root.refreshLawyerOptions()
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterNumberInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Matter Number"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) root.matterNumberAutoSync = false
                        }
                    }

                    ModernTextField {
                        id: matterNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Matter Name"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterDisplayNameInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Display Name"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) root.matterDisplayNameAutoSync = false
                        }
                    }

                    ModernComboBox {
                        id: matterBillingArrangementCombo
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Arrangement"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        fullModel: root.matterBillingArrangementOptions
                        onEditTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterBillingContactInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Contact"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterBillingEmailInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Billing Email"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) root.matterBillingEmailAutoSync = false
                        }
                    }

                    ModernTextField {
                        id: matterDefaultRateInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Initial Default Rate"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) root.matterDefaultRateAutoSync = false
                        }
                    }

                    ModernTextField {
                        id: matterDefaultShareInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Initial Default Share %"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                            if (!root._hydrating && !root._autoFieldMutation) root.matterDefaultShareAutoSync = false
                        }
                    }

                    ModernTextField {
                        id: matterRateHistoryInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Rate Epochs (JSON Array)"
                        visible: false
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: "[]"
                        onTextChanged: {
                            if (!root._hydrating) root.dirty = true
                        }
                    }

                    ModernTextField {
                        id: matterDateOfEngagementInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Date Of Engagement"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterDateOpenedInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Date Opened"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterDateClosedInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Date Closed"
                        datePickerEnabled: true
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterCourtFileInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Court File"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterOpposingPartyInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Opposing Party"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }

                    ModernTextField {
                        id: matterReferralFromInput
                        t: root.t
                        metrics: root.responsiveMetrics
                        label: "Referral From"
                        Layout.fillWidth: true
                        Layout.columnSpan: 1
                        Layout.preferredHeight: root.fieldHeightPx
                        text: ""
                        onTextChanged: if (!root._hydrating) root.dirty = true
                    }
                }

                Rectangle {
                    id: matterFinancialStatusCard
                    visible: root.matterEditMode && root.selectedMatterId.length > 0
                    Layout.fillWidth: true
                    Layout.topMargin: root.controlGapPx
                    Layout.preferredHeight: Math.max(
                        root.ratioPxH(0.115, 94),
                        matterFinancialStatusContent.implicitHeight + root.ratioPx(0.018, 14)
                    )
                    radius: root.sectionRadiusPx
                    color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.68)
                    border.width: 1
                    border.color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.34)

                    ColumnLayout {
                        id: matterFinancialStatusContent
                        anchors.fill: parent
                        anchors.margins: root.ratioPx(0.008, 8)
                        spacing: root.ratioPx(0.005, 4)

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: root.controlGapPx

                            Text {
                                text: "Financial status"
                                color: root._text
                                font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 10))
                                font.weight: Font.DemiBold
                            }

                            Item { Layout.fillWidth: true }

                            PillButton {
                                t: root.t
                                metrics: root.responsiveMetrics
                                sfxBus: root.sfxBus
                                text: "Open WIP Ledger"
                                primary: false
                                Layout.preferredWidth: root.ratioPxW(0.128, 126)
                                Layout.preferredHeight: root.fieldHeightPx
                                onClicked: root.openMatterWipLedger()
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: root.matterFinancialSummaryLoading
                            text: "Loading unbilled WIP and unpaid invoices…"
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.68)
                            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 8))
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: !root.matterFinancialSummaryLoading
                                && (!root.matterFinancialSummary || !root.matterFinancialSummary.ok)
                            text: root.matterFinancialSummary && root.matterFinancialSummary.message
                                ? String(root.matterFinancialSummary.message)
                                : "Financial status will load after this matter is saved."
                            color: Qt.rgba(0.90, 0.45, 0.25, 0.96)
                            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 8))
                            wrapMode: Text.WordWrap
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            visible: !root.matterFinancialSummaryLoading
                                && root.matterFinancialSummary && root.matterFinancialSummary.ok
                            spacing: root.ratioPx(0.016, 14)

                            Text {
                                text: "Unbilled WIP: "
                                    + Number(root.matterFinancialSummary.unbilledWipCount || 0)
                                    + " item(s) · " + root.matterFinancialMoney(root.matterFinancialSummary.unbilledWipAmount)
                                color: Number(root.matterFinancialSummary.unbilledWipCount || 0) > 0
                                    ? Qt.rgba(0.86, 0.55, 0.14, 0.98)
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.76)
                                font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 1.06, root.metricFloor("fontFloorLabelPx", 8))
                                font.weight: Font.DemiBold
                            }

                            Item { Layout.fillWidth: true }

                            Text {
                                text: "Unpaid invoices: "
                                    + Number(root.matterFinancialSummary.unpaidInvoiceCount || 0)
                                    + " · " + root.matterFinancialMoney(root.matterFinancialSummary.unpaidInvoiceAmount)
                                color: Number(root.matterFinancialSummary.unpaidInvoiceCount || 0) > 0
                                    ? Qt.rgba(0.80, 0.24, 0.20, 0.98)
                                    : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.76)
                                font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct * 1.06, root.metricFloor("fontFloorLabelPx", 8))
                                font.weight: Font.DemiBold
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: root.matterFinancialSummary && root.matterFinancialSummary.ok
                                && Number(root.matterFinancialSummary.unpaidInvoiceCount || 0) === 0
                            text: "No unpaid invoices are linked to this matter."
                            color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.68)
                            font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 8))
                        }

                        Column {
                            Layout.fillWidth: true
                            visible: root.matterFinancialSummary && root.matterFinancialSummary.ok
                                && Number(root.matterFinancialSummary.unpaidInvoiceCount || 0) > 0
                            spacing: 2

                            Repeater {
                                model: root.matterFinancialSummary && root.matterFinancialSummary.unpaidInvoices
                                    ? root.matterFinancialSummary.unpaidInvoices : []
                                delegate: Rectangle {
                                    required property var modelData
                                    width: parent ? parent.width : 0
                                    height: Math.max(root.ratioPxH(0.030, 25), invoiceLinkText.implicitHeight + 6)
                                    radius: Math.max(3, root.sectionRadiusPx - 4)
                                    color: invoiceLinkMouse.containsMouse
                                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.12)
                                        : Qt.rgba(root._bg.r, root._bg.g, root._bg.b, 0.20)
                                    border.width: 1
                                    border.color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.24)

                                    Text {
                                        id: invoiceLinkText
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.margins: 6
                                        text: "Invoice " + String(modelData.invoiceNum || "")
                                            + " · Amount due " + root.matterFinancialMoney(modelData.balanceDue)
                                            + " — open in Invoice Directory"
                                        color: root._accent
                                        font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 8))
                                        font.underline: invoiceLinkMouse.containsMouse
                                        elide: Text.ElideRight
                                    }

                                    MouseArea {
                                        id: invoiceLinkMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.openMatterInvoice(String(modelData.invoiceNum || ""))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }


        TextArea {
            id: notesInput
                    visible: !root.activeIsNewClientWizard()
                        && !root.activeIsClientDirectory()
                        && !root.activeIsClientProfile360()
                        && !root.activeIsMatterDirectory()
                        && !root.activeIsMatterProfile360()
                        && !root.activeIsGlobalSearch()
                        && !root.activeIsFinancialDashboard()
                        && !root.activeIsARAgingReport()
                        && !root.activeIsDocketActivityReport()
                        && !root.activeIsLedgerReport()
                        && !root.activeIsStatementOfAccount()
                        && !root.activeIsTransactionsMaster()
                        && !root.activeIsPaymentEntry()
                        && !root.activeIsWipToBill()
                        && !root.activeIsInvoiceBuilder()
                        && !root.activeIsInvoiceDirectory()
                        && !root.activeIsInvoiceReversal()
                        && !root.activeIsAccountsPayable()
                        && !root.activeIsLegacyDocketsImport()
                        && !root.activeIsProductivityDashboard()
                    Layout.fillWidth: true
                    Layout.maximumWidth: 700
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillHeight: false
                    Layout.preferredHeight: root.activeIsNewMatterWizard()
                        ? root.ratioPxH(0.094, 72)
                        : 140
                    color: root._text
                    font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorBodyPx", 9))
                    wrapMode: Text.Wrap
                    placeholderText: root.activeIsNewMatterWizard()
                        ? "Matter notes"
                        : ("Pathway placeholder for " + String(root.currentNode().title || "selected module") + ".")
                    placeholderTextColor: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.50)
                    leftPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                    topPadding: root.ratioPx(root.scaleRatios.descPadPct, 4)
                    onTextChanged: if (!root._hydrating) root.dirty = true
                    background: Rectangle {
                        color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.72)
                        radius: root.sectionRadiusPx
                        border.width: notesInput.activeFocus ? 2 : 1
                        border.color: notesInput.activeFocus
                            ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.62)
                            : Qt.rgba(root._text.r, root._text.g, root._text.b, 0.18)
                    }
                }

                RowLayout {
                    visible: !root.activeIsLedgerReport()
                        && !root.activeIsFinancialDashboard()
                        && !root.activeIsARAgingReport()
                        && !root.activeIsStatementOfAccount()
                        && !root.activeIsPaymentEntry()
                        && !root.activeIsWipToBill()
                        && !root.activeIsInvoiceBuilder()
                        && !root.activeIsInvoiceReversal()
                        && !root.activeIsAccountsPayable()
                        && !root.activeIsProductivityDashboard()
                    Layout.fillWidth: true
                    Layout.topMargin: root.controlGapPx
                    Layout.preferredHeight: root.ratioPxH(0.066, 48)
                    Layout.bottomMargin: root.ratioPx(0.0026, 2)
                    spacing: root.ratioPx(root.scaleRatios.footerSpacingPct, 8)

                    PillButton {
                        visible: !root.activeIsInvoiceBuilder()
                            && !root.activeIsInvoiceDirectory()
                            && !root.activeIsInvoiceReversal()
                            && !root.activeIsAccountsPayable()
                            && !root.activeIsLegacyDocketsImport()
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.activeIsNewClientWizard()
                            ? (root.saveInProgress ? "Saving..." : "Save Client")
                            : (root.activeIsNewMatterWizard()
                                ? (root.saveInProgress
                                    ? "Saving..."
                                    : (root.matterEditMode ? "Save Matter & Return" : "Save Matter"))
                                : (root.activeIsTransactionsMaster()
                                    ? "Save Transaction"
                                    : (root.activeIsDocketActivityReport()
                                        ? "Run Report"
                                        : (root.activeIsClientDirectory()
                                        ? "Refresh Directory"
                                        : (root.activeIsClientProfile360()
                                            ? "Load Profile"
                                            : (root.activeIsMatterDirectory()
                                                ? "Refresh Directory"
                                                : (root.activeIsMatterProfile360()
                                                    ? "Load Profile"
                                                    : (root.activeIsGlobalSearch() ? "Run Search" : "Open Placeholder"))))))))
                        primary: true
                        Layout.preferredWidth: root.ratioPxW(root.scaleRatios.submitBtnWidthPct, 142)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.requestPrimaryAction()
                    }

                    PillButton {
                        visible: root.activeIsDocketActivityReport()
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Export CSV"
                        primary: false
                        Layout.preferredWidth: root.ratioPxW(root.scaleRatios.cancelBtnWidthPct, 110)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: {
                            if (docketActivityReportPanel && docketActivityReportPanel.exportCsv) {
                                docketActivityReportPanel.exportCsv()
                            }
                        }
                    }

                    PillButton {
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Close" : "Cancel"
                        primary: false
                        Layout.preferredWidth: root.ratioPxW(root.scaleRatios.cancelBtnWidthPct, 106)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.requestCancelAction()
                    }

                    PillButton {
                        visible: root.activeIsNewMatterWizard() && root.matterEditMode
                            && String(root.matterPersistedStatus || "").trim().toLowerCase() !== "archived"
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Archive Matter"
                        primary: false
                        Layout.preferredWidth: root.ratioPxW(0.118, 124)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.requestMatterArchive()
                    }

                    PillButton {
                        visible: root.activeIsNewMatterWizard() && root.matterEditMode
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: "Delete Matter"
                        primary: false
                        accentColor: "#d32f2f"
                        Layout.preferredWidth: root.ratioPxW(0.110, 110)
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: {
                            deleteMatterConfirmPopup.open()
                        }
                    }

                    Item { Layout.fillWidth: true }

                    PillButton {
                        visible: !(root.externalNavigationShell && root.isProMode)
                        enabled: visible
                        t: root.t
                        metrics: root.responsiveMetrics
                        sfxBus: root.sfxBus
                        text: root.detachedWindow ? "Return to Dock" : "Undock"
                        primary: true
                        Layout.preferredWidth: visible
                            ? root.ratioPxW(root.detachedWindow ? root.scaleRatios.dockBtnWidthPct : root.scaleRatios.tearBtnWidthPct, 148)
                            : 0
                        Layout.preferredHeight: root.fieldHeightPx
                        onClicked: root.tearAwayRequested(root.snapshotState())
                    }
                }

                Text {
                    visible: (root.activeIsNewClientWizard() || root.activeIsNewMatterWizard() || root.activeIsTransactionsMaster() || root.activeIsPaymentEntry())
                        && String(root.saveMessage || "").length > 0
                    Layout.fillWidth: true
                    text: root.lastSaveOk
                        ? (
                            root.saveMessage
                            + (
                                root.activeIsNewClientWizard()
                                ? (root.lastSavedClientId.length > 0 ? ("  (" + root.lastSavedClientId + ")") : "")
                                : (
                                    root.activeIsNewMatterWizard()
                                    ? (root.lastSavedMatterId.length > 0 ? ("  (" + root.lastSavedMatterId + ")") : "")
                                    : (root.lastSavedTransactionId.length > 0 ? ("  (" + root.lastSavedTransactionId + ")") : "")
                                )
                            )
                        )
                        : root.saveMessage
                    color: root.lastSaveOk
                        ? Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.92)
                        : Qt.rgba(0.98, 0.42, 0.42, 0.96)
                    wrapMode: Text.WordWrap
                    font.pixelSize: root.ratioPx(root.scaleRatios.hintFontPct, root.metricFloor("fontFloorLabelPx", 8))
                }
                    }
                }
            }
        }
    }

    Popup {
        id: discardMatterEditPopup
        parent: root.Window.window ? root.Window.window.contentItem : root
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: parent
        padding: root.ratioPx(0.010, 10)
        width: Math.max(
            root.ratioPxW(0.34, 360),
            Math.min(root.ratioPxW(0.56, 680), (parent ? parent.width : root.width) - root.ratioPx(0.018, 18))
        )

        background: Rectangle {
            radius: root.sectionRadiusPx
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.96)
            border.width: 1
            border.color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.66)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Discard unsaved matter changes?"
                color: root._text
                font.pixelSize: root.ratioPx(
                    root.scaleRatios.headerTitleFontPct * 0.62,
                    root.metricFloor("fontFloorBodyPx", 10)
                )
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: "The Matter Name and Display Name will remain unchanged until you choose Save Matter & Return."
                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.86)
                font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorLabelPx", 8))
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.008, 8)

                Item { Layout.fillWidth: true }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Keep Editing"
                    primary: false
                    Layout.preferredWidth: root.ratioPxW(0.128, 128)
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: discardMatterEditPopup.close()
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Discard Changes"
                    primary: true
                    Layout.preferredWidth: root.ratioPxW(0.142, 142)
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: {
                        discardMatterEditPopup.close()
                        root.returnFromMatterEdit()
                        root.dirty = false
                        root.matterProfileLookupMessage = "Changes discarded. The saved matter profile was reloaded."
                    }
                }
            }
        }
    }

    Popup {
        id: clientSaveValidationPopup
        parent: root.Window.window ? root.Window.window.contentItem : root
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: parent
        padding: root.ratioPx(0.010, 10)
        width: Math.max(
            root.ratioPxW(0.34, 360),
            Math.min(root.ratioPxW(0.56, 680), (parent ? parent.width : root.width) - root.ratioPx(0.018, 18))
        )

        background: Rectangle {
            radius: root.sectionRadiusPx
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.96)
            border.width: 1
            border.color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.66)
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Check Phone/Email Formatting"
                color: root._text
                font.pixelSize: root.ratioPx(
                    root.scaleRatios.headerTitleFontPct * 0.62,
                    root.metricFloor("fontFloorBodyPx", 10)
                )
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: "The following entries look invalid. Save anyway, or review and fix them first."
                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.86)
                font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorLabelPx", 8))
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(root.ratioPxH(0.145, 120), validationIssueText.implicitHeight + root.ratioPx(0.018, 14))
                radius: root.sectionRadiusPx
                color: Qt.rgba(root._bg.r, root._bg.g, root._bg.b, 0.16)
                border.width: 1
                border.color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.18)

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: root.ratioPx(0.006, 6)
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Text {
                        id: validationIssueText
                        width: parent ? parent.width : implicitWidth
                        text: String(root.clientSaveValidationSummary || "")
                        color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.95)
                        font.pixelSize: root.ratioPx(root.scaleRatios.descFontPct, root.metricFloor("fontFloorLabelPx", 8))
                        wrapMode: Text.WordWrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: root.ratioPx(0.008, 8)

                Item { Layout.fillWidth: true }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Review"
                    primary: false
                    Layout.preferredWidth: root.ratioPxW(0.105, 108)
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: clientSaveValidationPopup.close()
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Save Anyway"
                    primary: true
                    Layout.preferredWidth: root.ratioPxW(0.130, 132)
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: {
                        clientSaveValidationPopup.close()
                        root.trySaveClientProfile(true)
                    }
                }
            }
        }
    }

    Timer {
        id: clientProfileAutoLoadRetryTimer
        interval: 220
        repeat: false
        onTriggered: {
            if (!root.activeIsClientProfile360()) return
            root.autoLoadSelectedClientProfile(root.pendingClientProfileAutoLoadKey)
        }
    }

    Component.onCompleted: {
        ensureActiveNode()
        refreshClientDirectory(false)
        refreshMatterDirectory(false)
        refreshMatterWizardClientOptions()
        if (root.activeIsNewClientWizard()) {
            refreshParentClientOptions()
        }
        if (root.activeIsNewMatterWizard()) {
            refreshParentClientOptions()
            refreshMatterWizardClientOptions()
        }
        if (initialState) {
            applyInitialState(initialState)
        } else {
            refreshAutoSyncFlags()
            refreshMatterAutoSyncFlags()
            applyClientWizardAutoPopulate()
            applyMatterWizardAutoPopulate()
            if (root.activeIsClientProfile360()) {
                autoLoadSelectedClientProfile("")
            }
            if (root.activeIsMatterProfile360()) {
                loadSelectedMatterProfile("")
            }
            if (root.activeIsGlobalSearch()) {
                refreshGlobalSearchResults()
            }
            if (root.activeIsTransactionsMaster() && transactionMasterView) {
                transactionMasterView.refreshLookupData()
            }
        }
    }

    onInitialStateChanged: {
        if (initialState) applyInitialState(initialState)
    }

    ReceivableEditorDialog {
        id: receivableEditorPopup
        root: root
    }

    Popup {
        id: archiveMatterConfirmPopup
        property string blockerMessage: ""
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        width: Math.max(root.ratioPxW(0.42, 360), 520)
        padding: root.ratioPx(0.010, 10)
        x: parent ? Math.round((parent.width - width) / 2) : 0
        y: parent ? Math.round((parent.height - height) / 2) : 0
        onOpened: blockerMessage = ""

        background: Rectangle {
            radius: root.isProMode ? 4 : root.ratioPx(0.012, 10)
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.98)
            border.width: 1
            border.color: "#a86212"
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "Archive matter"
                color: root._text
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Archive " + (root.selectedMatterName || root.selectedMatterId || "this matter")
                    + "? It will be removed from active worklists. Nothing is deleted. New time, fee, and client-disbursement entries will require CSPM's protected re-open flow and a separate final save confirmation."
                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.94)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            Text {
                Layout.fillWidth: true
                visible: archiveMatterConfirmPopup.blockerMessage.length > 0
                text: archiveMatterConfirmPopup.blockerMessage
                color: "#b42318"
                wrapMode: Text.WordWrap
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
                font.weight: Font.DemiBold
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.minimumHeight: root.fieldHeightPx
                Layout.preferredHeight: root.fieldHeightPx
                spacing: root.ratioPx(0.006, 6)

                Item { Layout.fillWidth: true }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Cancel"
                    primary: false
                    Layout.preferredWidth: root.ratioPxW(0.110, 106)
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: archiveMatterConfirmPopup.close()
                }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Archive Matter"
                    primary: true
                    accentColor: "#a86212"
                    Layout.preferredWidth: root.ratioPxW(0.142, 142)
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: root.archiveMatterAfterConfirmation()
                }
            }
        }
    }

    Popup {
        id: deleteMatterConfirmPopup
        property string blockerMessage: ""
        modal: true
        focus: true
        dim: true
        closePolicy: Popup.CloseOnEscape
        width: Math.max(root.ratioPxW(0.46, 360), 560)
        padding: root.ratioPx(0.010, 10)
        x: parent ? Math.round((parent.width - width) / 2) : 0
        y: parent ? Math.round((parent.height - height) / 2) : 0
        onOpened: blockerMessage = ""

        background: Rectangle {
            radius: root.isProMode ? 4 : root.ratioPx(0.012, 10)
            color: Qt.rgba(root._panel.r, root._panel.g, root._panel.b, 0.96)
            border.width: 1
            border.color: "#d32f2f"
        }

        contentItem: ColumnLayout {
            spacing: root.ratioPx(0.008, 8)

            Text {
                Layout.fillWidth: true
                text: "WARNING: DELETE MATTER"
                color: "#d32f2f"
                font.pixelSize: root.ratioPx(0.016, root.metricFloor("fontFloorTitlePx", 12))
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Deleting a matter is DESTRUCTIVE and IRREVERSIBLE. You will permanently lose all associated data. Use a non-active status instead whenever possible. Deletion is blocked when this matter has active unbilled WIP or unpaid invoices.\n\nAre you absolutely sure you want to permanently delete this matter?"
                color: Qt.rgba(root._text.r, root._text.g, root._text.b, 0.94)
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
            }

            Text {
                Layout.fillWidth: true
                visible: deleteMatterConfirmPopup.blockerMessage.length > 0
                text: deleteMatterConfirmPopup.blockerMessage
                color: "#d32f2f"
                wrapMode: Text.WordWrap
                font.pixelSize: root.ratioPx(0.011, root.metricFloor("fontFloorLabelPx", 9))
                font.weight: Font.DemiBold
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.minimumHeight: root.fieldHeightPx
                Layout.preferredHeight: root.fieldHeightPx
                spacing: root.ratioPx(0.006, 6)

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Permanently Delete"
                    primary: true
                    accentColor: "#d32f2f"
                    Layout.fillWidth: false
                    Layout.minimumWidth: root.ratioPxW(0.174, 174)
                    Layout.preferredWidth: root.ratioPxW(0.188, 188)
                    Layout.minimumHeight: root.fieldHeightPx
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: {
                        var pId = root.selectedMatterProfile && root.selectedMatterProfile.matterId
                            ? root.selectedMatterProfile.matterId : root.selectedMatterId
                        if (pId && root.appRef && root.appRef.deleteMatterProfile) {
                            var res = root.appRef.deleteMatterProfile(pId)
                            if (res && res.ok) {
                                deleteMatterConfirmPopup.close()
                                root.refreshMatterDirectory(true)
                                root.saveMessage = "Matter permanently deleted."
                                root.requestExternalWorkspaceFocus("A09")
                            } else {
                                var message = "Failed to delete matter: " + (res ? res.message : "Unknown error")
                                deleteMatterConfirmPopup.blockerMessage = message
                                root.saveMessage = message
                                root.lastSaveOk = false
                            }
                        } else {
                            deleteMatterConfirmPopup.blockerMessage = "No saved matter is selected for deletion."
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                PillButton {
                    t: root.t
                    metrics: root.responsiveMetrics
                    sfxBus: root.sfxBus
                    text: "Cancel"
                    primary: false
                    Layout.fillWidth: false
                    Layout.minimumWidth: root.ratioPxW(0.124, 124)
                    Layout.preferredWidth: root.ratioPxW(0.136, 136)
                    Layout.minimumHeight: root.fieldHeightPx
                    Layout.preferredHeight: root.fieldHeightPx
                    onClicked: {
                        deleteMatterConfirmPopup.close()
                    }
                }
            }
        }
    }
}
