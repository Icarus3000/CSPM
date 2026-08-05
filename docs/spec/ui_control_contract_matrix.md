# UI Control Contract Matrix (NP-02)

Generated: 2026-02-27 21:29:14

Scope: high-priority interactive controls under src/qml/views (excluding shell chrome).

## Totals

- Contracts generated: 156

### By Current Status
- placeholder: 88
- unwired: 24
- wired: 44

### By Priority
- P0: 4
- P1: 137
- P2: 15

## Backend Slot Coverage

| Slot | Controls |
|---|---:|
| saveMatterProfile | 72 |
| saveClientProfile | 58 |
| saveTransaction | 29 |
| saveTimeDocketEntry | 22 |
| listMatterNames | 21 |
| getMatterProfile | 21 |
| listMatterDirectory | 21 |
| previewMatterNumber | 21 |
| getTimeDocketAggregate | 9 |
| getHomeDashboardSummary | 8 |
| listClientDirectory | 8 |
| getClientProfile | 6 |
| listClientNames | 6 |
| recordUndockRequest | 5 |
| searchGlobalEntities | 2 |
| listParentNames | 2 |
| handleOmniSearchCommand | 1 |

## P0 Queue (First 120)

| Contract | Lane | File | Line | Type | Label | Status | Slots |
|---|---|---|---:|---|---|---|---|
| NP02-0017 | Placeholder Host (multi-lane) | src\qml\views\PlaceholderSubmenuView.qml | 2844 | PillButton | "Load Profile" | placeholder | getClientProfile |
| NP02-0026 | Placeholder Host (multi-lane) | src\qml\views\PlaceholderSubmenuView.qml | 3427 | PillButton | "Load Profile" | placeholder | getMatterProfile |
| NP02-0092 | Placeholder Host (multi-lane) | src\qml\views\PlaceholderSubmenuView.qml | 4615 | PillButton | "Export CSV" | placeholder | saveClientProfile\|saveMatterProfile |
| NP02-0096 | Placeholder Host (multi-lane) | src\qml\views\PlaceholderSubmenuView.qml | 4770 | PillButton | "Save Anyway" | placeholder | saveClientProfile\|saveMatterProfile |

## Output Files

- CSV: docs\spec\ui_control_contract_matrix.csv
- Summary: docs\spec\ui_control_contract_matrix.md

