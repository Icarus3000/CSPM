# CSPM Interface Rebuild Brief

## Strategic UI Roadmap Note
- The Option 3 (**Professional**) interface described in this brief is intended to remain permanently implemented in **Qt/QML**. 
- Once this Professional Qt/QML interface is perfected, a clone of it will be built in **Flutter / React Native** to serve as a separate, third layout tier called **"Expert"**.
- Do not migrate or re-architect the Option 3 implementation in this repository away from Qt/QML.

---

## Option 3: Compact Module Rail + Flyout Menus + Top Work Tabs + Full Workspace

The goal is to rebuild the application shell so that the user gets substantially more usable working space while preserving fast access to all major legal-practice-management functions.

The current interface uses too much permanent navigation space:

```text
Current structure:

Top application header
+ left major-module sidebar
+ second pathway-map sidebar
+ main work area
```

The new structure should be:

```text
New structure:

Compact left module rail
+ flyout menus for module tools
+ top work-tab bar
+ full-width central workspace
+ optional contextual drawers/panels
```

The second permanent **Pathway map** sidebar should be removed from the default layout.

---

# 1. Core Design Concept

The application should be organized around three distinct layers:

```text
Level 1: Major Modules
Examples:
- Clients & Matters
- Docket & Deadlines
- Billing & Invoicing
- Finance & Ledger
- Reports
- Settings / Admin

Level 2: Module Tools / Screens
Examples:
- Time Docket Entry
- Fee Docket Entry
- Deadline Master Calendar
- WIP-to-Bill Workbench
- Invoice Builder
- Payment Entry
- A/R Aging
- Client Profile 360
- Matter Profile 360

Level 3: Active Work
Examples:
- Client: Wild Bunch Beverages Inc.
- Matter: M-2025-001
- Invoice Draft #1042
- Time Docket Entry
- WIP Dashboard / Report
```

The key change is this:

```text
Major modules remain visible.
Module tools appear only when needed.
Active work appears as tabs.
The main workspace gets most of the screen.
```

---

# 2. High-Level Application Shell

The new shell should look conceptually like this:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CS  Cory Schneider Law Office Practice Management      Search...       ⚙ □ X │
├──────┬───────────────────────────────────────────────────────────────────────┤
│ 👥   │ [Time Docket Entry] [WIP-to-Bill] [Client: Wild Bunch] [+]           │
│ 📅   ├───────────────────────────────────────────────────────────────────────┤
│ 💵   │ Billing & Invoicing > WIP-to-Bill Workbench                          │
│ 📊   │                                                                       │
│ ⚙    │ Main working screen                                                   │
│      │                                                                       │
│      │                                                                       │
└──────┴───────────────────────────────────────────────────────────────────────┘
```

The permanent elements should be:

```text
1. Top app header
2. Compact left module rail
3. Work-tab bar
4. Breadcrumb / screen title area
5. Main workspace
```

The non-permanent elements should be:

```text
1. Module flyout menu
2. Contextual right drawer
3. Modal dialogs
4. Command/search palette
```

---

# 3. Replace the Current Two-Sidebar Layout

The current second sidebar, labelled **Pathway map**, should not be permanently visible.

For example, this should go away as a default screen element:

```text
Billing, Payments & Tax
Pathway map
- WIP-to-Bill Workbench
- Pre-Bill Editor
- Invoice Builder
- Invoice Reversal / Credit Memo
- Payment Entry
- Write-off / Adjustment Entry
- Collections Queue
- Transactions Master
- Vendor & Expense Category Manager
- Disbursement Rebill Queue
- HST/GST Remittance Center
- Tax Filing Register
- Payment Method & Reference Register
```

Instead, that same list should appear in a flyout when the user selects the Billing module from the compact rail.

---

# 4. Compact Left Module Rail

## Purpose

The left rail is for **major modules only**.

It should not contain every screen, tool, report, or subfunction.

## Suggested Modules

```text
Clients & Matters
Docket & Deadlines
Billing & Invoicing
Finance & Ledger
Reports
Admin / Settings
```

Potential icon choices:

```text
Clients & Matters       people / briefcase icon
Docket & Deadlines      calendar / clock icon
Billing & Invoicing     invoice / dollar icon
Finance & Ledger        ledger / chart icon
Reports                 bar chart icon
Settings                gear icon
```

## Width

Collapsed/default width:

```text
56px to 72px
```

Expanded/pinned width:

```text
200px to 240px
```

The default should be collapsed.

The user may optionally pin it open.

## Behaviour

The rail should support these states:

```text
collapsed
expanded
pinned
hover-preview
```

Recommended behaviour:

```text
Default:
- Rail is collapsed.
- Icons are visible.
- Labels are not visible, except possibly in tooltips.

On hover:
- Show tooltip with module name.
- Optional: show flyout after short delay.

On click:
- Open module flyout.

On pin:
- Rail expands and stays expanded.
- Labels become visible.
```

Do not rely on hover only. A click interaction should always exist because hover-only navigation can be annoying and unreliable.

---

# 5. Module Flyout Menus

## Purpose

The flyout replaces the permanent Pathway map sidebar.

When the user clicks a major module, show a floating panel beside the left rail.

Example:

```text
┌──────┐
│ 👥   │
│ 📅   │
│ 💵 ──┼────┐
│ 📊   │    │ Billing & Invoicing
│ ⚙    │    │ ─────────────────────────
└──────┘    │ WIP-to-Bill Workbench
            │ Pre-Bill Editor
            │ Invoice Builder
            │ Invoice Reversal / Credit Memo
            │ Payment Entry
            │ Write-off / Adjustment Entry
            │ Collections Queue
            │ Transactions Master
            │ Vendor & Expense Category Manager
            │ Disbursement Rebill Queue
            │ HST/GST Remittance Center
            │ Tax Filing Register
            │ Payment Method & Reference Register
            └──────────────────────────
```

## Flyout Width

Suggested width:

```text
280px to 360px
```

It should overlay the workspace temporarily. It should not push the workspace sideways unless the user pins it.

## Flyout Sections

Long module menus should be grouped.

### Billing & Invoicing

```text
Billing & Invoicing

Core Billing
- WIP-to-Bill Workbench
- Pre-Bill Editor
- Invoice Builder
- Invoice Reversal / Credit Memo

Payments & Adjustments
- Payment Entry
- Write-off / Adjustment Entry
- Collections Queue

Transactions & Setup
- Transactions Master
- Vendor & Expense Category Manager
- Disbursement Rebill Queue
- Payment Method & Reference Register

Tax
- HST/GST Remittance Center
- Tax Filing Register
```

### Finance & Ledger

```text
Finance & Ledger

Dashboards
- Executive Dashboard
- Revenue Dashboard
- Expense Dashboard
- Net Income & Cash Increase
- WIP Dashboard / Report

Reports
- A/R Aging & Detail
- Client Ledger Report
- Matter Ledger Report
- Parent Ledger Report
- Productivity & Utilization Report
- Earnings Report
- Top Client Concentration
- Quarterly Performance Pack
```

### Docketing & Deadlines

```text
Docketing & Deadlines

Time & Docketing
- Time Docket Entry
- Fee Docket Entry
- Timer Console
- Docket Activity Report
- Docket Adjustment / Void
- Batch Docket Entry

Deadlines
- Deadline Master Calendar
- Deadline Entry Editor
- Deadline Rules Library
- Jurisdiction Profiles
- Tickler Scheduler
- Reminder Escalation Center
- Filing Checklist
```

### Clients & Matters

```text
Clients & Matters

Clients
- Client Directory
- New Client Wizard
- Client Profile 360
- Client Contacts & Roles
- Client ID/KYC Record
- Conflict Check

Relationships
- Parent-Child Link Manager
- Duplicate Merge Tool

Matters
- Matter Directory
- New Matter Wizard
- Matter Profile 360
- Matter Reassignment
```

## Flyout Behaviour

When user clicks a menu item:

```text
1. Open selected screen in a work tab.
2. Make that tab active.
3. Close the flyout.
4. Update breadcrumb and page title.
```

If the selected screen is already open:

```text
1. Activate the existing tab.
2. Do not create a duplicate tab unless user expressly asks to open another instance.
```

For screens that can have multiple records open, duplicates may be allowed.

Examples:

```text
Client: Cory Schneider
Client: Wild Bunch Beverages Inc.
Matter: M-2025-001
Matter: M-2026-004
```

But generic tools should usually be single-instance:

```text
Time Docket Entry
WIP-to-Bill Workbench
Deadline Master Calendar
Invoice Builder
```

---

# 6. Top Work-Tab Bar

## Purpose

The top tab bar represents **active work**, not module navigation.

This is very important.

The tabs should not be:

```text
Clients | Docket | Billing | Finance
```

Those are modules.

The tabs should be:

```text
[Time Docket Entry] [WIP-to-Bill Workbench] [Client: Wild Bunch] [Invoice Draft #1042]
```

## Location

The tab row should sit below the top application header and to the right of the compact rail.

Example:

```text
┌────────────────────────────────────────────────────────────────────┐
│ App Header                                                         │
├──────┬─────────────────────────────────────────────────────────────┤
│ Rail │ [Time Docket] [WIP-to-Bill] [Client: Wild Bunch] [+]        │
│      ├─────────────────────────────────────────────────────────────┤
│      │ Breadcrumb / title                                          │
│      │ Main workspace                                              │
└──────┴─────────────────────────────────────────────────────────────┘
```

## Tab Types

The system should support different tab types:

```text
screen tab
client tab
matter tab
invoice tab
report tab
dashboard tab
calendar tab
draft/work item tab
```

Examples:

```text
[Time Docket Entry]
[Deadline Master Calendar]
[Client: Cory Schneider]
[Matter: M-2025-001]
[Invoice Draft #1042]
[WIP Dashboard]
[A/R Aging]
```

## Tab Behaviour

Each tab should support:

```text
Activate
Close
Close others
Close tabs to the right
Pin
Duplicate where applicable
Undock
```

Suggested right-click context menu:

```text
Close
Close Other Tabs
Close Tabs to the Right
Pin Tab
Duplicate Tab
Undock
```

Pinned tabs should stay at the left of the tab bar.

Example:

```text
[📌 Time Docket Entry] [📌 Client Directory] [Wild Bunch] [Invoice Draft #1042]
```

Pinned tabs could be daily-use workstations.

## Duplicate Tab Rules

Generic screens should generally be single-instance:

```text
Time Docket Entry
WIP-to-Bill Workbench
Deadline Master Calendar
Invoice Builder
Payment Entry
```

Record screens can have multiple instances:

```text
Client: Deborah Spivak
Client: Wild Bunch Beverages Inc.
Matter: M-2025-001
Matter: M-2025-002
Invoice Draft #1042
Invoice Draft #1043
```

## Unsaved Changes

If a tab has unsaved changes, show a visual indicator.

Example:

```text
[Time Docket Entry ●]
```

When user closes a dirty tab:

```text
You have unsaved changes.

[Save] [Discard] [Cancel]
```

For legal/accounting software, unsaved changes must be handled very carefully.

---

# 7. Top Application Header

The header should be simpler and shorter than the current one.

Suggested structure:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ CS  Cory Schneider Law Office Practice Management   Search / Command   ⚙ □ X │
└────────────────────────────────────────────────────────────────────────────┘
```

The header should include:

```text
Logo / app identity
Global search / command bar
Settings icon
Window controls
Optional user/account indicator
```

## Header Height

Suggested height:

```text
56px to 72px
```

The current header feels a bit tall. Reducing it will give more vertical room.

## Global Search / Command Bar

The search bar should eventually support:

```text
Search clients
Search matters
Search invoices
Search deadlines
Search reports
Search commands
```

Examples:

```text
"Wild Bunch"
"new client"
"time docket"
"HST remittance"
"invoice 1042"
"deadline rules"
```

This will reduce reliance on visible menus.

---

# 8. Breadcrumb and Screen Title Area

Each active tab should display a clear location above the workspace.

Examples:

```text
Billing & Invoicing > WIP-to-Bill Workbench
```

```text
Docketing & Deadlines > Time Docket Entry
```

```text
Clients & Matters > Client Profile 360 > Wild Bunch Beverages Inc.
```

This gives the user orientation after the second sidebar is removed.

The breadcrumb/title area should include:

```text
Module name
Screen name
Record name where applicable
Status badge where applicable
Primary page-level actions where appropriate
```

Example:

```text
Docketing & Deadlines > Time Docket Entry       Draft     00:00:00  [Start] [Reset]
```

For screens like Time Docket Entry, the timer/status controls could move into the page header area.

---

# 9. Main Workspace

The main workspace should use nearly all available width.

The target layout should be:

```text
Compact rail:       56px to 72px
Flyout:             temporary overlay only
Work area:          remaining width
```

The main workspace should not be constrained by a permanent secondary sidebar.

For example, Time Docket Entry should become much wider:

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Docketing & Deadlines > Time Docket Entry       Draft 00:00:00 Start │
├──────────────────────────────────────────────────────────────────────┤
│ Date                         Time                                   │
│ Matter                       Client                                 │
│ Task / Activity                                                     │
│ Description                                                          │
│ Rate                         Bill %                 Total Fees       │
│                                                                      │
│ [Set Draft] [Mark Ready] [Mark Billed] [Save Docket] [Cancel]        │
└──────────────────────────────────────────────────────────────────────┘
```

For billing/report screens, this gives room for tables, queues, filters, and dashboards.

---

# 10. Contextual Right Drawer

For detail panels, use a right-side drawer instead of another permanent left sidebar.

Example: user selects a client, invoice, matter, docket entry, or WIP item.

A right drawer can slide out:

```text
┌──────────────────────────────────────────────────────────────┬───────────────┐
│ Main workspace                                               │ Client Summary│
│                                                              │───────────────│
│ Table/list/workbench                                         │ Name          │
│                                                              │ Active Matters│
│                                                              │ Balance       │
│                                                              │ Actions       │
└──────────────────────────────────────────────────────────────┴───────────────┘
```

Suggested drawer width:

```text
320px to 420px
```

The drawer should be optional and dismissible.

Use it for:

```text
Client summary
Matter summary
Invoice summary
WIP item details
Deadline detail
Contact details
Recent activity
Quick actions
```

Do not use it for permanent navigation.

---

# 11. Local Tabs Inside Complex Screens

Some screens need their own internal tabs.

These are different from work tabs.

Example: Client Profile 360

```text
Work tab:
[Client: Wild Bunch Beverages Inc.]

Inside the screen:
Overview | Contacts | Matters | Billing | Ledger | Documents | KYC | Notes
```

Example: Matter Profile 360

```text
Overview | Parties | Dockets | Deadlines | Billing | Documents | Notes
```

Example: Finance dashboard

```text
Summary | A/R | WIP | Revenue | Expenses | Forecasting
```

Rule:

```text
Top work tabs = open workspaces.
Local tabs = sections inside one workspace.
```

Do not mix these concepts.

---

# 12. Suggested Component Architecture

The coder should probably implement the application shell as reusable components.

Suggested components:

```text
AppShell
TopHeader
ModuleRail
ModuleFlyout
WorkTabBar
WorkspaceHost
BreadcrumbBar
RightDrawer
CommandPalette
DirtyTabGuard
```

Conceptual structure:

```text
AppShell
 ├── TopHeader
 │    ├── LogoArea
 │    ├── GlobalCommandSearch
 │    └── HeaderActions
 │
 ├── Body
 │    ├── ModuleRail
 │    ├── ModuleFlyout
 │    └── MainColumn
 │         ├── WorkTabBar
 │         ├── BreadcrumbBar
 │         └── WorkspaceHost
 │
 └── RightDrawer
```

---

# 13. Suggested State Model

The application should track:

```text
activeModule
activeFlyoutModule
openTabs
activeTabId
pinnedTabs
dirtyTabs
rightDrawerState
railPinned
railExpanded
```

Example data model:

```javascript
const navigationModules = [
  {
    id: "clients",
    label: "Clients & Matters",
    icon: "users",
    sections: [
      {
        label: "Clients",
        items: [
          { id: "client-directory", label: "Client Directory", route: "/clients/directory", singleInstance: true },
          { id: "new-client", label: "New Client Wizard", route: "/clients/new", singleInstance: true },
          { id: "client-profile", label: "Client Profile 360", route: "/clients/profile", singleInstance: false },
          { id: "client-contacts", label: "Client Contacts & Roles", route: "/clients/contacts", singleInstance: true },
          { id: "client-kyc", label: "Client ID/KYC Record", route: "/clients/kyc", singleInstance: true },
          { id: "conflict-check", label: "Conflict Check", route: "/clients/conflict-check", singleInstance: true }
        ]
      },
      {
        label: "Matters",
        items: [
          { id: "matter-directory", label: "Matter Directory", route: "/matters/directory", singleInstance: true },
          { id: "new-matter", label: "New Matter Wizard", route: "/matters/new", singleInstance: true },
          { id: "matter-profile", label: "Matter Profile 360", route: "/matters/profile", singleInstance: false },
          { id: "matter-reassignment", label: "Matter Reassignment", route: "/matters/reassignment", singleInstance: true }
        ]
      }
    ]
  }
];
```

Example tab model:

```javascript
const openTabs = [
  {
    id: "tab-time-docket-entry",
    type: "screen",
    title: "Time Docket Entry",
    moduleId: "docket",
    route: "/docket/time-entry",
    icon: "clock",
    pinned: true,
    dirty: false,
    singleInstanceKey: "time-docket-entry"
  },
  {
    id: "tab-client-wild-bunch",
    type: "client",
    title: "Client: Wild Bunch",
    moduleId: "clients",
    route: "/clients/profile/wild-bunch",
    icon: "building",
    pinned: false,
    dirty: false,
    entityId: "client-004"
  },
  {
    id: "tab-invoice-1042",
    type: "invoice",
    title: "Invoice Draft #1042",
    moduleId: "billing",
    route: "/billing/invoice/1042",
    icon: "file-invoice",
    pinned: false,
    dirty: true,
    entityId: "invoice-1042"
  }
];
```

---

# 14. Routing and Tab Opening Logic

When the user selects an item from a flyout, the application should not simply navigate away from the current screen. It should open or activate a work tab.

Pseudo-logic:

```javascript
function openWorkspace(item, params = {}) {
  const singleInstanceKey = item.singleInstance
    ? item.id
    : `${item.id}:${params.entityId || createUniqueId()}`;

  const existingTab = openTabs.find(tab => tab.singleInstanceKey === singleInstanceKey);

  if (existingTab) {
    setActiveTab(existingTab.id);
    closeFlyout();
    return;
  }

  const newTab = createTabFromNavigationItem(item, params);

  setOpenTabs([...openTabs, newTab]);
  setActiveTab(newTab.id);
  closeFlyout();
}
```

Record-specific tabs should use entity IDs:

```text
Client Profile 360 + clientId
Matter Profile 360 + matterId
Invoice Builder + invoiceId
Report + reportParameters
```

Generic workbench tabs should usually use a single-instance key:

```text
time-docket-entry
wip-to-bill-workbench
deadline-master-calendar
payment-entry
ar-aging
```

---

# 15. Suggested Screen Header Pattern

Each workspace should have a standardized header:

```text
Module > Screen Name                              Status / Actions
Subtitle or explanatory line
```

Examples:

```text
Docketing & Deadlines > Time Docket Entry        Draft  00:00:00  [Start] [Reset]
Integrated docket capture with live timer and exact-save tracking
```

```text
Billing & Invoicing > WIP-to-Bill Workbench      Unbilled Drafts: 2
Invoices, payments, expenses, and HST lines staged
```

```text
Finance & Ledger > WIP Dashboard / Report        Queue Items: 6
Dashboards, ledgers, A/R, WIP, forecasting
```

This replaces the orientation previously provided by the pathway sidebar.

---

# 16. Treatment of the Current “Undock” Button

The current screens have an Undock button at the bottom. In the new interface, undocking should be a tab-level command.

Better:

```text
Right-click tab > Undock
```

or:

```text
Tab menu ⋯ > Undock
```

The bottom-right **Undock** button can eventually be removed from most screens.

Reason:

```text
Undock applies to the workspace/tab, not to the form itself.
```

This makes the system feel more coherent.

---

# 17. Suggested Keyboard Shortcuts

For power users, add keyboard shortcuts.

```text
Ctrl+K or Ctrl+Space       Open command palette
Ctrl+Tab                   Next work tab
Ctrl+Shift+Tab             Previous work tab
Ctrl+W                     Close active tab
Ctrl+S                     Save current workspace
Ctrl+N                     New item, contextual
Alt+1                      Clients & Matters flyout
Alt+2                      Docket & Deadlines flyout
Alt+3                      Billing & Invoicing flyout
Alt+4                      Finance & Ledger flyout
Alt+5                      Reports flyout
Esc                        Close flyout / drawer / palette
```

These should not be required for use, but they will make the application feel much faster.

---

# 18. Responsive / Window-Size Behaviour

The layout should respond to window width.

## Large Desktop

```text
Rail collapsed or pinned
Flyout overlay
Work tabs visible
Breadcrumb visible
Right drawer available
```

## Medium Width

```text
Rail collapsed only
Flyout overlay
Tabs may scroll horizontally
Right drawer overlays instead of shrinking workspace
```

## Small Width

```text
Rail becomes hamburger/menu button
Tabs become dropdown or horizontally scrollable
Right drawer becomes full-height overlay
```

Because this appears to be desktop-first software, the large and medium layouts matter most.

---

# 19. Visual Style Guidance

The existing visual style is conservative and professional, which is appropriate. The new layout should not become flashy.

Keep:

```text
Muted blue/grey palette
Strong but not harsh borders
Clear active states
Large readable text
Professional spacing
```

Improve:

```text
Reduce heavy side panels
Use more whitespace in work area
Make active tab obvious
Make active module obvious
Use clearer section grouping in flyouts
Use consistent button placement
```

Suggested style rules:

```text
Rail background: slightly darker/lighter than main canvas
Active module: clear indicator bar or filled icon background
Flyout: white or very light panel with subtle shadow
Active tab: connected visually to workspace
Inactive tabs: muted
Dirty tab: small dot indicator
Pinned tab: small pin icon
Main workspace: full-width cards/forms/tables
```

---

# 20. Important Distinction: Top Modules vs. Top Work Tabs

The top row should be used primarily for **work tabs**, not major module tabs.

Recommended:

```text
Left rail:
Clients | Docket | Billing | Finance | Reports

Top tab row:
[Time Docket Entry] [WIP-to-Bill] [Client: Wild Bunch] [Invoice Draft #1042]
```

Not recommended:

```text
Top module tabs:
Clients | Docket | Billing | Finance
```

Reason:

The major modules are navigation categories. The work tabs are the user’s current work. In legal software, preserving active work is more valuable than repeating module navigation across the top.

That said, the header can include a small optional **Modules** menu or command search. But the main top tab bar should be for open workspaces.

---

# 21. Example: Time Docket Entry Under New Structure

Current screen has:

```text
Left major sidebar
Pathway map sidebar
Time Docket Entry form
```

New screen should have:

```text
Compact rail
Top work tab: [Time Docket Entry]
Breadcrumb/title: Docketing & Deadlines > Time Docket Entry
Full-width form
```

Conceptual layout:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ CS Cory Schneider Law Office                         Search...        ⚙    │
├──────┬─────────────────────────────────────────────────────────────────────┤
│ 👥   │ [Time Docket Entry] [Deadline Calendar] [WIP-to-Bill]               │
│ 📅   ├─────────────────────────────────────────────────────────────────────┤
│ 💵   │ Docketing & Deadlines > Time Docket Entry       Draft 00:00:00      │
│ 📊   │ Integrated docket capture with live timer and exact-save tracking   │
│ ⚙    │                                                                     │
│      │ Date                         Time                                   │
│      │ Matter                       Client                                 │
│      │ Task / Activity                                                     │
│      │ Description                                                          │
│      │ Rate                         Bill %                 Total Fees       │
│      │                                                                     │
│      │ [Set Draft] [Mark Ready] [Mark Billed] [Save Docket] [Cancel]       │
└──────┴─────────────────────────────────────────────────────────────────────┘
```

---

# 22. Example: Billing Screen Under New Structure

When user clicks Billing rail icon, show flyout:

```text
Billing & Invoicing

Core Billing
- WIP-to-Bill Workbench
- Pre-Bill Editor
- Invoice Builder
- Invoice Reversal / Credit Memo

Payments & Adjustments
- Payment Entry
- Write-off / Adjustment Entry
- Collections Queue

Tax
- HST/GST Remittance Center
- Tax Filing Register
```

If user selects WIP-to-Bill Workbench:

```text
[WIP-to-Bill Workbench]
Billing & Invoicing > WIP-to-Bill Workbench
```

The main area should then use the full width for filters, staged WIP, invoice queues, and action buttons.

---

# 23. Example: Finance Screen Under New Structure

When user clicks Finance rail icon, show flyout:

```text
Finance & Ledger

Dashboards
- Executive Dashboard
- Revenue Dashboard
- Expense Dashboard
- Net Income & Cash Increase
- WIP Dashboard / Report

Reports
- A/R Aging & Detail
- Client Ledger Report
- Matter Ledger Report
- Parent Ledger Report
- Productivity & Utilization Report
- Earnings Report
- Top Client Concentration
- Quarterly Performance Pack
```

If user selects WIP Dashboard / Report:

```text
[WIP Dashboard / Report]
Finance & Ledger > WIP Dashboard / Report
```

No second sidebar should remain on screen.

---

# 24. Migration Plan

The coder can migrate in stages.

## Phase 1 — Build New Shell

Create:

```text
AppShell
TopHeader
ModuleRail
ModuleFlyout
WorkTabBar
WorkspaceHost
BreadcrumbBar
```

Keep existing screens mostly unchanged inside the new workspace area.

## Phase 2 — Move Pathway Maps Into Flyouts

Convert each current pathway-map list into module flyout configuration.

Do not delete functionality. Only move navigation.

## Phase 3 — Add Work-Tab Behavior

Implement:

```text
Open screen in tab
Activate existing tab if single-instance
Close tab
Dirty tab indicator
Pinned tabs
```

## Phase 4 — Refactor Screen Headers

Move screen titles, status badges, timers, and major actions into consistent workspace headers.

## Phase 5 — Add Command Palette and Right Drawers

Add after the core shell works.

---

# 25. Acceptance Criteria

The rebuild should be considered successful when:

```text
1. The second permanent Pathway map sidebar is gone.
2. The left navigation defaults to a compact rail.
3. Clicking a major module opens a flyout menu.
4. Selecting a flyout item opens or activates a work tab.
5. Multiple work tabs can remain open.
6. Generic screens are not duplicated unnecessarily.
7. Record-specific screens can open as separate tabs.
8. The active workspace gets most of the window width.
9. Breadcrumbs clearly show where the user is.
10. Unsaved tab changes are visibly indicated and protected.
11. The interface still feels professional and conservative.
12. Existing screens can be progressively migrated without rewriting all business logic at once.
```

---

# 26. Blunt Implementation Instruction

Do not rebuild this as:

```text
Top modules + left sidebar + pathway sidebar + tabs
```

That would recreate the same space problem with more complexity.

The target is:

```text
Compact module rail
+ temporary flyout menus
+ top work tabs
+ full-width workspace
```

The permanent interface should be lean. The detailed navigation should appear only when requested. The user’s active work should occupy the screen.

