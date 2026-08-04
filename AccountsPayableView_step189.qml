    readonly property real billColumnMargin: 12
    readonly property real billColumnSpacing: 6

    // ── Column model (data-driven, persisted) ────────────────────────
    readonly property var defaultBillColumns: [
        { key: "vendor",    label: "Vendor / Invoice", required: true,  visible: true,  width: 160, minWidth: 120, align: "left"  },
        { key: "notes",     label: "Notes",            required: false, visible: true,  width: 110, minWidth: 60,  align: "left"  },
        { key: "treatment", label: "Treatment",        required: false, visible: true,  width: 105, minWidth: 60,  align: "left"  },
        { key: "category",  label: "Category",         required: false, visible: true,  width: 95,  minWidth: 60,  align: "left"  },
        { key: "date",      label: "Date / Due",       required: true,  visible: true,  width: 92,  minWidth: 76,  align: "left"  },
        { key: "status",    label: "Status",           required: true,  visible: true,  width: 76,  minWidth: 56,  align: "left"  },
        { key: "balance",   label: "Balance",          required: true,  visible: true,  width: 92,  minWidth: 70,  align: "right" },
        { key: "account",   label: "Account",          required: false, visible: false, width: 105, minWidth: 60,  align: "left"  }
    ]
    property var billColumns: []   // live column config (mutated by user)
    property string sortColumn: ""
    property bool   sortAscending: true
    property int    dragSourceIndex: -1
    property bool   columnSettingsOpen: false

    function visibleBillColumns() {
        var out = []
        for (var i = 0; i < billColumns.length; i++)
            if (billColumns[i].visible) out.push(billColumns[i])
        return out
    }

    function totalFixedColumnWidth() {
        var cols = visibleBillColumns()
        var total = 0
        for (var i = 0; i < cols.length; i++)
            if (cols[i].key !== "vendor") total += cols[i].width
        return total + Math.max(0, cols.length - 1) * billColumnSpacing
    }

    function vendorColumnWidth(contentWidth) {
        var vc = null
        for (var i = 0; i < billColumns.length; i++)
            if (billColumns[i].key === "vendor" && billColumns[i].visible) { vc = billColumns[i]; break }
        if (!vc) return 0
        var avail = contentWidth - totalFixedColumnWidth()
        return Math.max(vc.minWidth, avail)
    }

    function columnWidthFor(col, contentWidth) {
        if (col.key === "vendor") return vendorColumnWidth(contentWidth)
        return col.width
    }

    // ── Sort ─────────────────────────────────────────────────────────
    function toggleSort(key) {
        if (sortColumn === key) {
            if (sortAscending) { sortAscending = false }
            else { sortColumn = ""; sortAscending = true }
        } else {
            sortColumn = key
            sortAscending = true
        }
        applySortToBillRows()
    }

    function billSortValue(row, key) {
        switch (key) {
        case "vendor":    return String(row.Vendor || "").toLowerCase()
        case "date":      return String(row.InvoiceDate || "")
        case "status":    return String(row.Status || "").toLowerCase()
        case "balance":   return Number(row.Balance || 0)
        case "notes":     return String(row.Notes || "").toLowerCase()
        case "treatment": return String(row.ExpenseTreatment || "").toLowerCase()
        case "category":  return String(row.CategoryName || row.CategoryCode || "").toLowerCase()
        case "account":   return String(row.SourceAccount || "").toLowerCase()
        }
        return ""
    }

    property var unsortedBillRows: []

    function applySortToBillRows() {
        if (!sortColumn) {
            root.billRows = root.unsortedBillRows.slice()
            return
        }
        var sorted = root.unsortedBillRows.slice()
        var key = root.sortColumn
        var asc = root.sortAscending
        sorted.sort(function(a, b) {
            var va = billSortValue(a, key)
            var vb = billSortValue(b, key)
            if (va < vb) return asc ? -1 : 1
            if (va > vb) return asc ? 1 : -1
            return 0
        })
        root.billRows = sorted
    }

    // ── Cell content ─────────────────────────────────────────────────
    function billCellText(key, data) {
        switch (key) {
        case "notes":     return String(data.Notes || "")
        case "treatment": return root.treatmentLabel(String(data.ExpenseTreatment || ""))
        case "category":  return String(data.CategoryName || data.CategoryCode || "")
        case "account":   return String(data.SourceAccount || "")
        case "status":    return String(data.Status || "")
        case "balance":   return root.moneyText(data.Balance)
        }
        return ""
    }

    function treatmentLabel(id) {
        for (var i = 0; i < root.expenseTreatments.length; i++)
            if (root.expenseTreatments[i].id === id) return root.expenseTreatments[i].label
        return id
    }

    // ── Persistence ──────────────────────────────────────────────────
    function saveBillColumnConfig() {
        var cfg = []
        for (var i = 0; i < billColumns.length; i++) {
            var c = billColumns[i]
            cfg.push({ key: c.key, visible: c.visible, width: c.width })
        }
        var ctrl = root.apController
        if (ctrl && typeof ctrl.saveAPColumnConfig === "function")
            ctrl.saveAPColumnConfig(JSON.stringify(cfg))
    }

    function loadBillColumnConfig() {
        var ctrl = root.apController
        var json = ""
        if (ctrl && typeof ctrl.loadAPColumnConfig === "function")
            json = ctrl.loadAPColumnConfig()
        if (json) {
            try {
                var saved = JSON.parse(json)
                if (Array.isArray(saved) && saved.length > 0) {
                    // Merge saved config with defaults (handles new columns added later)
                    var merged = []
                    var defaultMap = {}
                    for (var d = 0; d < defaultBillColumns.length; d++)
                        defaultMap[defaultBillColumns[d].key] = JSON.parse(JSON.stringify(defaultBillColumns[d]))
                    // Add saved columns in saved order
                    var seenKeys = {}
                    for (var s = 0; s < saved.length; s++) {
                        var sk = saved[s].key
                        if (defaultMap[sk]) {
                            var col = defaultMap[sk]
                            col.visible = !!saved[s].visible
                            col.width = Math.max(col.minWidth, saved[s].width || col.width)
                            // Required columns are always visible
                            if (col.required) col.visible = true
                            merged.push(col)
                            seenKeys[sk] = true
                        }
                    }
                    // Append any new default columns not in saved config
                    for (var n = 0; n < defaultBillColumns.length; n++) {
                        if (!seenKeys[defaultBillColumns[n].key])
                            merged.push(JSON.parse(JSON.stringify(defaultBillColumns[n])))
                    }
                    root.billColumns = merged
                    return
                }
            } catch (e) {
                console.warn("[AP] failed to parse column config:", e)
            }
        }
        // Fall back to defaults
        root.billColumns = JSON.parse(JSON.stringify(defaultBillColumns))
    }