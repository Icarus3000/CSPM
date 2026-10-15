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
