# CSPM Preferences (Authoritative)

Updated: 2026-03-04

## 1) Chatpack Dump (Default Rules)
Chatpack MUST always include current code + UI context:
- src/python/**/*.py
- src/qml/**/*.qml
- src/qml/**/*.json
- src/qml/**/*.svg
- Future-proof QML text assets (auto-include when present):
  - src/qml/**/*.js
  - src/qml/**/*.mjs
  - src/qml/**/*.qmltypes
  - src/qml/**/qmldir
- schema/**
- docs/BIBLE.md
- docs/PREFERENCES.md
- docs/DECISIONS/**/*.md (includes drag pipeline roadmap)

Hard excluded:
- scripts/**
- dumps/**
- archive/**
- outputs/**
- backups/**
- data/state/**

## 2) Implementation Standards


<!-- CSPM_CONSOLE_TILES_START -->
### Console Grid Standard — Canonical Tile Set

**Canonical 8-Tile Layout (Order Locked):**
1) Time & Dockets
2) Fee Entries
3) Disbursements & Expenses
4) Clients & Matters
5) Deadlines & Ticklers
6) Billing & Invoices
7) Payments & Receivables (A/R)
8) Reports & Productivity

(If any other file states a different tile count, this block controls.)
<!-- CSPM_CONSOLE_TILES_END -->

- UI interactions follow "Electric Bubble Gum" physics (elastic, organic).
- Support hybrid multi-instance "tear away" concurrency (two timers concurrently).
- Ghost indicators are informational only (never disable tiles).
- Theme engine: 7 themes, instant switching, SVG recolor-friendly.
