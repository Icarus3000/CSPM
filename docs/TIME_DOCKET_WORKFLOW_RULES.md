# Time Docket Workflow Rules (Proposed)

## 1. Goal
Use one combined daily docket per matter so time is accurate and never over-rounded.

Primary user rule:
- One docket row per `Timekeeper + WorkDate + Matter` whenever possible.
- If work is done in multiple short segments, combine by raw seconds first, then round once.

Example:
- 5 min + 5 min + 2 min = 12 min total = 0.2 hours (not 0.1 + 0.1 + 0.1).

## 2. Canonical Data Rules

### 2.1 Source of truth
- `RawSeconds` is authoritative.
- `Hours` is a derived display/billing value from `RawSeconds`.

### 2.2 Unique draft bucket key
- Primary key for active draft accumulation:
  - `TimekeeperId + WorkDate(YYYY-MM-DD) + MatterId`
- Fallback only when no matter is available:
  - `TimekeeperId + WorkDate + ClientId + MatterId=UNASSIGNED`

### 2.3 Save behavior
- Always `upsert` into the matching draft bucket.
- Do not append a new row for each timer stop.
- If duplicate draft rows exist for same key, merge automatically.

## 3. Timer + Docket State Machine

States:
1. `Idle` (no running timer)
2. `Running`
3. `Paused` (same draft bucket retained)
4. `Finalized` (locked from timer accrual)

Rules:
1. Only one running timer per user across the app.
2. Starting a timer on a different matter auto-stops current timer, accrues elapsed seconds, then starts new matter.
3. A finalized docket cannot accrue more time; user must reopen or create a new day/matter bucket.

## 4. Rounding and Billing Rules

1. Accrual math:
   - `RawSecondsTotal = existingRawSeconds + elapsedSegmentSeconds`
2. Hours display:
   - `ActualHours = RawSecondsTotal / 3600`
3. Billable tenth (default policy):
   - `BillableHours = ceil(ActualHours * 10) / 10`
4. Important:
   - Never round per segment.
   - Round only once on combined total.

## 5. Matter Requirement Rules

1. Matter is required by default for finalizable/billable docket.
2. If user selects client with no matter:
   - Prompt with:
     1. `Create Matter Now` (recommended)
     2. `Select Existing Matter`
     3. `Use Temporary Client-Only Docket` (allowed but not finalizable until matter assigned)
3. If temporary client-only docket is used, enforce resolution before finalization.

## 6. Auto-Merge Rules for Existing Duplicates

When loading a draft bucket:
1. Find all draft rows matching same key.
2. Keep oldest row as survivor.
3. Sum `RawSeconds`.
4. Recalculate `Hours`.
5. Move merged row IDs to audit note (or merged marker).
6. Mark merged duplicates as void/merged (never silently delete).

## 7. Hard Edge Cases

1. Midnight crossover:
   - Split elapsed time at 23:59:59 into prior day bucket and new day bucket.
2. Crash/app close with running timer:
   - Recover with checkpointed timer state and prompt user to confirm recovered elapsed segment.
3. Clock changes / DST:
   - Use monotonic timer for elapsed duration; use wall clock only for date assignment.
4. Closed/inactive matter:
   - Block timer start and require matter reassignment.
5. Multi-window conflict:
   - Enforce single active timer lock (second start request must prompt to switch).
6. Manual hour edit while timer running:
   - Require pause first; log manual adjustment reason.

## 8. Normal Workflow Scenarios

1. Same matter, multiple short sessions:
   - All sessions upsert to same row; one combined draft docket shown for edit/finalize.
2. Save button clicked repeatedly:
   - Idempotent upsert to same row; no duplicates.
3. User revisits same matter later same day:
   - Existing draft bucket loads, timer can resume.
4. User finalizes end of day:
   - Status changes to finalized/review-ready and timer accrual is blocked.

## 9. Proposed Prompt Copy

No matter found for selected client:
- Title: `Matter Required`
- Body: `This docket should be tied to a matter. Create one now or choose an existing matter.`
- Actions:
  1. `Create Matter`
  2. `Choose Matter`
  3. `Use Temporary Client-Only Docket`
  4. `Cancel`

Detected duplicate draft dockets:
- Title: `Duplicate Drafts Merged`
- Body: `Multiple draft entries were found for the same day/matter and merged to preserve accurate time.`
- Action: `Review Combined Docket`

## 10. Decisions To Confirm Before Implementation

Confirmed:
1. Billable rounding mode:
   - `ceil to 0.1` on aggregate daily total only.
2. Temporary client-only docket:
   - Allowed as explicit override, with prompt each time when matter is blank.
3. Working statuses:
   - `Draft` / `Ready for Billing` / `Billed`.
4. Edit policy:
   - Editable until `Billed`; billed entries are locked.
