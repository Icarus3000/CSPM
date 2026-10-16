# Fedora latest-main and calendar integration

The initial Fedora executable was based on `d1d6475`; the Microsoft 365 agenda
and device sign-in repair were added later on cloud main (`3efca16`, `3a65bee`).
The integration starts from freshly fetched `66a9cbe`, preserving those changes,
the newer resource/Recovery repairs and the shared invoice-header update, and
merges the existing Fedora desktop compatibility work in an isolated worktree.
The original dirty checkout and installed executable remain preserved.

## Calendar persistence on Linux

Windows retains current-user DPAPI. Linux uses authenticated Fernet ciphertext
in the profile's `calendar/Microsoft365/token_cache.secretservice` and stores
its random encryption key in the desktop's **persistent default Secret Service
wallet**. The wallet must be available and unlocked. Missing, locked, ambiguous
or temporary session wallets fail with a safe error; there is no plaintext or
alternate-backend fallback. Tokens and encryption keys are never logged.
Only a SHA-256 profile identifier enters key lookup metadata. Disconnect removes
ciphertext and preserves its durable disconnected marker. Atomic replacement,
cancellation rollback and silent-refresh/disconnect ownership remain shared.

The desktop wallet contains a retained encryption key after disconnect, allowing
existing atomic rollback semantics; it contains no calendar cache. Deleting that
CSPM encryption key invalidates the corresponding ciphertext and requires a new
calendar sign-in. Do not copy Windows DPAPI caches to Linux.

Microsoft registration IDs/preferences are non-secret, profile-local settings;
they were not copied from a Windows installation. Live account sign-in and
Outlook calendar coverage still require the user's Microsoft authentication.

## Build and verification

`requirements.txt` adds Linux-only SecretStorage. The Linux spec bundles MSAL,
SecretStorage, Fernet, holiday locale data and tzdata. Use the Fedora environment
and builder documented in README. `scripts/build_linux_app.py` validates approved
blank templates, records immutable source identity, builds main and Recovery,
and preserves previous local build output. It does not replace the installed
workspace's package when run in the isolated worktree without `--install`.

Sandbox-safe checks cover actual authenticated-encryption roundtrips, restart,
missing/locked/session wallets, key loss, ciphertext tampering, profile isolation,
cancellation rollback, durable disconnect and unchanged Windows cache selection,
plus calendar/controller/QML, Fedora paths/lifecycle/recovery, resource, invoice
navigation/header and usage-control regressions. Windows Recovery fixtures now
explicitly choose Windows; Linux terminal handoff preserves the active selector.
A broken core-path import fails closed rather than selecting fallback data.

Outside-sandbox desktop and actual packaged WebEngine verification are recorded
separately in local release evidence after packaging. Live Microsoft account
sign-in and foreground calendar acceptance are not established by synthetic tests.

Official storage references:
- https://secretstorage.readthedocs.io/en/latest/collection.html
- https://cryptography.io/en/latest/fernet/

Usage-aware pausing and its current manual-resume limitation are documented in
`WORKSPACE_USAGE_CONTROL.md`; private checkpoint/observations are excluded.

## Completed Fedora release October 16, 2026

The validated integration is published without force as cloud main and
`feature/fedora-calendar-integration-20261014` at
`202af1fb4acd21601dfbc8b557fd0be622090277`. A durable independent worktree
preserves that source; the original dirty working directory remains unchanged.
Main and Recovery are rebuilt from the clean commit, with source-tree hash
`31454e34f4f901e86e521f8f2e51a7584ec507dcb0ee23649e48fe01cf2d3e4f`
and build timestamp `2026-10-16T11:05:38.025407Z`.

Sandbox-safe validation passes 363 focused calendar/auth/QML, Linux desktop,
Recovery/resource/checkout/AP safety, invoice and usage-control tests. Governed
whole-tree Linux QML lint passes with existing warnings. The package audit
verifies all 5,866 runtime-manifest records and all 180 source QML-tree files.
The candidate and installed runtime manifests match exactly (manifest SHA-256
`41b20dcd433daad61b6739e438c62080c3d6339b1ab18a4c8979d684d35b5c80`).

Outside sandbox on the real Fedora desktop, both candidate and normal installed
launcher pass input-ready startup, visible restored calendar controls, native
KWin maximize/restore, Invoice Builder HTML/JavaScript, normal animated X-close,
tray cleanup and complete exit with unchanged synthetic workbooks. Separate
exact-bundled Qt WebEngine execution verifies HTML/JavaScript and a valid
14,100-byte PDF with Chromium sandbox enabled. The Chromium remote-debugging
`Page.printToPDF` command is unavailable in this build; that command is not
claimed as a passing PDF-export check. Actual in-app invoice export remains
covered by the earlier Fedora follow-up, not a new live-data invoice run.

A read-only desktop wallet probe confirms the persistent default Secret Service
collection is available and unlocked; it reads no credentials or tokens. Live
Microsoft account sign-in, tenant consent and Outlook calendar coverage remain
user acceptance items. No registration IDs, accounts or authentication caches
are copied from Windows.

The canonical Fedora package is installed under the existing `dist/CSPM` and
the existing desktop launcher still uses `launch.sh`. Every installed runtime
file matches the clean candidate. A read-only, SHA-256 verified rollback archive
and its complete file/symlink manifest preserve the previous runtime. Deployment
verifies unchanged original uncommitted source, settings and four configured
workbook files. There are no production financial/calendar writes or settings
changes. Private release evidence, screenshots, synthetic fixtures and rollback
artifacts remain under ignored `logs/calendar-integration-validation/`.
