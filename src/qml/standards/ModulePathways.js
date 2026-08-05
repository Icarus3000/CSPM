// Shared navigation model for the current QML shell and the Option 3
// Professional shell. Keep the legacy lane helpers stable while exposing
// module/section/item metadata for flyouts and work tabs.

function cloneValue(src) {
    if (!src || typeof src !== "object") return src
    if (src.length !== undefined) return cloneArray(src)
    return cloneMap(src)
}

function cloneMap(src) {
    var out = {}
    if (!src) return out
    for (var k in src) {
        if (src.hasOwnProperty(k)) out[k] = cloneValue(src[k])
    }
    return out
}

function cloneArray(src) {
    if (!src || src.length === undefined) return []
    var out = []
    for (var i = 0; i < src.length; i++) out.push(cloneValue(src[i]))
    return out
}

function itemIdFromNodeId(nodeId, label) {
    var raw = String(label || nodeId || "item").toLowerCase()
    raw = raw.replace(/&/g, "and")
    raw = raw.replace(/[^a-z0-9]+/g, "-")
    raw = raw.replace(/^-+|-+$/g, "")
    return raw.length > 0 ? raw : String(nodeId || "item").toLowerCase()
}

function normalizeItem(moduleCfg, sectionCfg, rawItem, moduleTitle) {
    var nodeId = String(rawItem.nodeId || rawItem.id || "").trim()
    var label = String(rawItem.label || rawItem.title || nodeId).trim()
    var itemId = String(rawItem.itemId || itemIdFromNodeId(nodeId, label)).trim()
    var route = String(rawItem.route || ("/" + moduleCfg.moduleId + "/" + itemId)).trim()
    var singleInstance = rawItem.singleInstance !== undefined ? !!rawItem.singleInstance : true
    var tabType = String(rawItem.tabType || "screen").trim()

    var item = cloneMap(rawItem)
    item.id = nodeId
    item.nodeId = nodeId
    item.itemId = itemId
    item.label = label
    item.title = label
    item.route = route
    item.singleInstance = singleInstance
    item.singleInstanceKey = String(rawItem.singleInstanceKey || (moduleCfg.moduleId + ":" + itemId))
    item.tabType = tabType
    item.moduleId = moduleCfg.moduleId
    item.moduleTitle = String(moduleTitle || moduleCfg.shellTitle || moduleCfg.title || "")
    item.laneKey = moduleCfg.laneKey
    item.tileIndex = moduleCfg.tileIndex
    item.sectionId = sectionCfg.id
    item.sectionTitle = sectionCfg.title
    return item
}

function normalizedSections(moduleCfg, moduleTitle) {
    var sections = []
    var source = moduleCfg.sections || []
    for (var s = 0; s < source.length; s++) {
        var sectionCfg = source[s]
        var section = cloneMap(sectionCfg)
        section.items = []
        section.displayItems = []
        var items = sectionCfg.items || []
        for (var i = 0; i < items.length; i++) {
            var normItem = normalizeItem(moduleCfg, sectionCfg, items[i], moduleTitle)
            section.items.push(normItem)
            if (!normItem.hidden) {
                section.displayItems.push(normItem)
            }
        }
        sections.push(section)
    }
    return sections
}

function flattenedItems(moduleCfg, moduleTitle, onlyDisplay) {
    var out = []
    var sections = normalizedSections(moduleCfg, moduleTitle)
    for (var s = 0; s < sections.length; s++) {
        var items = onlyDisplay ? (sections[s].displayItems || []) : (sections[s].items || [])
        for (var i = 0; i < items.length; i++) out.push(items[i])
    }
    return out
}

var HOME_MODULE_CONFIG = {
    "moduleId": "home",
    "tileIndex": -1,
    "laneKey": "home",
    "title": "Home",
    "shellTitle": "Home",
    "shortTitle": "Home",
    "railLabel": "Home",
    "icon": "\uE80F",
    "subtitle": "Today's priorities, deadlines, billing, and follow-ups",
    "defaultNodeId": "H01",
    "route": "/home",
    "sections": [
        {
            "id": "home",
            "title": "Home",
            "items": [
                {
                    "id": "H01",
                    "label": "Practice Briefing",
                    "route": "/home/practice-briefing",
                    "tabType": "home",
                    "singleInstanceKey": "home:practice-briefing",
                    "live": true
                }
            ]
        }
    ]
}

var MODULE_CONFIGS = [
    {
        "moduleId": "clients",
        "tileIndex": 0,
        "laneKey": "clients_matters",
        "title": "Clients & Matters",
        "shortTitle": "Clients",
        "railLabel": "Clients",
        "icon": "\uE77B",
        "subtitle": "Client lifecycle, matter setup, and relationship controls",
        "defaultNodeId": "A01",
        "route": "/clients",
        "sections": [
            {
                "id": "directory",
                "title": "Directory & Setup",
                "items": [
                    { "id": "A01", "label": "Client Directory", "route": "/clients/directory" },
                    { "id": "A09", "label": "Matter Directory", "route": "/matters/directory" },
                    { "id": "A02", "label": "New Client Wizard", "route": "/clients/new", "saveCommand": "client-profile" },
                    { "id": "A10", "label": "New Matter Wizard", "route": "/matters/new", "saveCommand": "matter-profile" },
                    { "id": "A03", "label": "Client Profile 360", "route": "/clients/profile", "tabType": "client", "singleInstance": false, "saveCommand": "client-profile", "hidden": true },
                    { "id": "A11", "label": "Matter Profile 360", "route": "/matters/profile", "tabType": "matter", "singleInstance": false, "saveCommand": "matter-profile", "hidden": true }
                ]
            },
            {
                "id": "corporate",
                "title": "Corporate Entities",
                "items": [
                    { "id": "A21", "label": "Corporate Directory", "route": "/corporate/directory" },
                    { "id": "A22", "label": "Corporate Profile", "route": "/corporate/profile", "tabType": "corporate", "singleInstance": false, "saveCommand": "corporate-entity", "hidden": true },
                    { "id": "A23", "label": "Transaction Wizard", "route": "/corporate/transaction-wizard" }
                ]
            }
        ]
    },
    {
        "moduleId": "docketing",
        "tileIndex": 1,
        "laneKey": "docketing_deadlines",
        "title": "Docketing & Deadlines",
        "shortTitle": "Docketing",
        "railLabel": "Dockets",
        "icon": "\uE823",
        "subtitle": "Time/fee capture, rules, ticklers, and deadline risk controls",
        "defaultNodeId": "B01",
        "route": "/docketing",
        "sections": [
            {
                "id": "time-docketing",
                "title": "Time & Activities",
                "items": [
                    { "id": "B01", "label": "Time Docket Entry", "route": "/docketing/time-entry", "live": true, "singleInstanceKey": "docketing:time-entry", "saveCommand": "time-docket" },
                    { "id": "B04", "label": "Docket Activity Report", "route": "/docketing/activity-report", "tabType": "report" }
                ]
            },
            {
                "id": "trademarks",
                "title": "Trademarks",
                "items": [
                    { "id": "B17", "label": "Trademark Directory", "route": "/docketing/trademark-directory" },
                    { "id": "B16", "label": "Trademark Filing", "route": "/docketing/trademark-filing", "saveCommand": "trademark-filing" }
                ]
            }
        ]
    },
    {
        "moduleId": "billing",
        "tileIndex": 2,
        "laneKey": "billing_tax",
        "title": "Billing, Payments & Tax",
        "shellTitle": "Billing & Invoicing",
        "shortTitle": "Billing",
        "railLabel": "Billing",
        "icon": "\uE8C7",
        "subtitle": "Billing pipeline, collections, disbursements, and remittances",
        "defaultNodeId": "C01",
        "route": "/billing",
        "sections": [
            {
                "id": "core-billing",
                "title": "Invoicing & Adjustments",
                "items": [
                    { "id": "C01", "label": "WIP-to-Bill Workbench", "route": "/billing/wip-to-bill" },
                    { "id": "C03", "label": "Invoice Builder", "route": "/billing/invoice-builder" },
                    { "id": "C07", "label": "Payment & Adjustment Entry", "route": "/billing/payment-entry", "saveCommand": "payment" },
                    { "id": "C08", "label": "Reverse an Invoice", "route": "/billing/reverse-invoice" },
                    { "id": "C05", "label": "WIP Billing Wizard", "route": "/billing/wip-wizard", "hidden": true },
                    { "id": "C06", "label": "Draft Review Workspace", "route": "/billing/draft-review", "hidden": true }
                ]
            },
            {
                "id": "transactions-setup",
                "title": "Accounts & Expenses",
                "items": [
                    { "id": "C18", "label": "Accounts Payable (Expenses)", "route": "/billing/accounts-payable" },
                    { "id": "C11", "label": "Transactions Master", "route": "/billing/transactions-master", "saveCommand": "transaction" }
                ]
            }
        ]
    },
    {
        "moduleId": "finance",
        "tileIndex": 3,
        "laneKey": "finance_ops",
        "title": "Finance, Reports & Operations",
        "shellTitle": "Finance & Ledger",
        "shortTitle": "Finance",
        "railLabel": "Finance",
        "icon": "\uE9D2",
        "subtitle": "Management reporting, controls, and operational governance",
        "defaultNodeId": "D01",
        "route": "/finance",
        "sections": [
            {
                "id": "dashboards",
                "title": "Dashboards & Ledgers",
                "items": [
                    { "id": "D01", "label": "Executive Dashboard", "route": "/finance/executive-dashboard", "tabType": "dashboard", "singleInstanceKey": "dashboard:D01" },
                    { "id": "D07", "label": "Client Ledger Report", "route": "/reports/client-ledger", "tabType": "report" },
                    { "id": "D17", "label": "Statement of Account", "route": "/reports/statement", "tabType": "report" },
                    { "id": "D06", "label": "A/R Aging & Detail", "route": "/reports/ar-aging", "tabType": "report" }
                ]
            },
            {
                "id": "operations",
                "title": "Operations",
                "items": [
                    { "id": "X13", "label": "Legacy Dockets Import", "route": "/operations/dockets-import", "tabType": "import" },
                    { "id": "X01", "label": "Global Search Results", "route": "/operations/global-search", "singleInstance": false, "hidden": true }
                ]
            }
        ]
    }
]

function moduleConfigById(moduleId) {
    var wanted = String(moduleId || "")
    for (var i = 0; i < MODULE_CONFIGS.length; i++) {
        if (String(MODULE_CONFIGS[i].moduleId || "") === wanted) return MODULE_CONFIGS[i]
    }
    return null
}

function sectionById(moduleCfg, sectionId) {
    var wanted = String(sectionId || "")
    var sections = moduleCfg && moduleCfg.sections ? moduleCfg.sections : []
    for (var i = 0; i < sections.length; i++) {
        if (String(sections[i].id || "") === wanted) return cloneMap(sections[i])
    }
    return null
}

function option3ModuleConfigs() {
    var out = [cloneMap(HOME_MODULE_CONFIG)]
    for (var i = 0; i < MODULE_CONFIGS.length; i++) {
        var cfg = MODULE_CONFIGS[i]
        if (String(cfg.moduleId || "") !== "finance") {
            out.push(cfg)
            continue
        }

        var financeDashboards = sectionById(cfg, "dashboards")
        var reports = sectionById(cfg, "reports")
        var operations = sectionById(cfg, "operations")

        var financeModule = cloneMap(cfg)
        financeModule.sections = financeDashboards ? [financeDashboards] : []
        out.push(financeModule)

        if (reports) {
            var reportsModuleSections = []
            if (financeDashboards) reportsModuleSections.push(cloneMap(financeDashboards))
            reportsModuleSections.push(reports)

            out.push({
                "moduleId": "reports",
                "tileIndex": cfg.tileIndex,
                "laneKey": cfg.laneKey,
                "title": "Reports",
                "shellTitle": "Reports",
                "shortTitle": "Reports",
                "railLabel": "Reports",
                "icon": "\uE9D9",
                "subtitle": "Ledgers, A/R, WIP, productivity, and packaged exports",
                "defaultNodeId": financeDashboards ? "D01" : "D06",
                "route": "/reports",
                "sections": reportsModuleSections
            })
        }

        if (operations) {
            out.push({
                "moduleId": "admin",
                "tileIndex": cfg.tileIndex,
                "laneKey": cfg.laneKey,
                "title": "Admin / Settings",
                "shellTitle": "Admin / Settings",
                "shortTitle": "Admin",
                "railLabel": "Admin",
                "icon": "\uE713",
                "subtitle": "Search, governance, templates, integrations, and retention controls",
                "defaultNodeId": "X01",
                "route": "/admin",
                "sections": [operations]
            })
        }
    }
    return out
}

function normalizedModule(moduleCfg, useShellTitle) {
    var module = cloneMap(moduleCfg)
    var displayTitle = (useShellTitle && moduleCfg.shellTitle)
        ? String(moduleCfg.shellTitle || "")
        : String(moduleCfg.title || "")
    module.legacyTitle = String(moduleCfg.title || "")
    module.title = displayTitle
    module.label = displayTitle
    module.sections = normalizedSections(moduleCfg, displayTitle)
    module.navItems = flattenedItems(moduleCfg, displayTitle, false)
    module.displayNavItems = flattenedItems(moduleCfg, displayTitle, true)
    return module
}

function navigationModules() {
    var out = []
    var configs = option3ModuleConfigs()
    for (var i = 0; i < configs.length; i++) {
        out.push(normalizedModule(configs[i], true))
    }
    return out
}

function laneTitles() {
    var out = []
    for (var i = 0; i < MODULE_CONFIGS.length; i++) {
        out.push(String(MODULE_CONFIGS[i].title || ""))
    }
    return out
}

function laneConfigs() {
    var out = []
    for (var i = 0; i < MODULE_CONFIGS.length; i++) {
        out.push(normalizedModule(MODULE_CONFIGS[i], false))
    }
    return out
}

function laneConfig(index) {
    var idx = Math.round(index)
    if (idx < 0 || idx >= MODULE_CONFIGS.length) return null
    return normalizedModule(MODULE_CONFIGS[idx], false)
}

function moduleForTile(tileIndex) {
    var idx = Math.round(tileIndex)
    for (var i = 0; i < MODULE_CONFIGS.length; i++) {
        if (Math.round(MODULE_CONFIGS[i].tileIndex) === idx) return normalizedModule(MODULE_CONFIGS[i], true)
    }
    return null
}

function moduleForId(moduleId) {
    var wanted = String(moduleId || "").trim()
    if (wanted === "home") return normalizedModule(HOME_MODULE_CONFIG, true)
    var configs = option3ModuleConfigs()
    for (var i = 0; i < configs.length; i++) {
        if (String(configs[i].moduleId || "") === wanted) return normalizedModule(configs[i], true)
    }
    return null
}

function homeModule() {
    return normalizedModule(HOME_MODULE_CONFIG, true)
}

function findNavigationItem(tileIndex, nodeId) {
    var module = moduleForTile(tileIndex)
    if (!module) return null
    var wanted = String(nodeId || module.defaultNodeId || "").trim()
    var items = module.navItems || []
    for (var i = 0; i < items.length; i++) {
        if (String(items[i].nodeId || items[i].id || "") === wanted) return cloneMap(items[i])
    }
    if (items.length > 0) return cloneMap(items[0])
    return null
}

function defaultNavigationItem(tileIndex) {
    var module = moduleForTile(tileIndex)
    if (!module) return null
    return findNavigationItem(tileIndex, module.defaultNodeId)
}
