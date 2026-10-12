# Normal-launch delay and stale header repair

After canonical main finalization, Cory reported a long normal launch and an
October 2 diagnostic label in the Professional header. The latest actual launch
report began at 11:06:50 Eastern on October 12; the executable process/runtime
started around 11:07:28 and reached input-ready 14.464 seconds later. The normal
launcher read and hashed every one of the 4,252 runtime files (677,625,745 bytes)
before starting the application. The approximately 38-second pre-application
interval was not individually instrumented, so it cannot all be attributed to
one filesystem or antivirus cause. It establishes a distinct launcher/pre-boot
delay beyond the existing Qt startup.

The Professional header contained a literal
`[BUILD 2026-10-02 PIXEL ALIGNED HANDOFF]`; it was an old diagnostic marker,
not packaging metadata. The header now displays only the ordinary application
name. About remains the source of actual version, full source SHA, source status,
build invocation timestamp, executable hash and motion preference.

## Launcher and verification scope

The generic `scripts/launch_governed_readonly.py` is versioned and included in the
ordinary package with no private settings or paths. Deployment still validates
the complete immutable runtime manifest. Ordinary launches verify the executable,
native DLL and exact clean ordinary-release provenance, then hash the governed
manifest and both local/shared workbook pairs. The supported selectors, pair
identity, checkout/recovery/Excel-marker rejection, concurrent-session guard,
local protection handles and inherited CLI/environment read-only policy remain.
No workbook identity is inferred from timestamps or cached hashes. Shared handles
are released before the manual session so OneDrive refresh remains possible.

A full runtime resource audit is available explicitly:

```powershell
python scripts/launch_governed_readonly.py --check-only --audit-runtime --configuration <private-deployment-json>
```

Routine launch does not claim a fresh audit of every ancillary runtime asset.
Its private launch report identifies its verification scope and records separate
monotonic timings for runtime identity, governed data, full audit when requested,
preflight, replica protection and process spawn. A measured preflight on the
unchanged installed package takes 0.086 seconds in the current warm-cache check;
this excludes Python startup, frozen initialization and Qt startup, and is not a
cold-launch guarantee. Frozen and real normal-launch measurements are recorded
privately after installation.

## Validation and release boundary

Eighteen focused synthetic launcher tests pass, including real byte-hash checks,
same-size/same-timestamp workbook divergence, critical identity mismatch,
modified build policy, marker conflicts, inherited read-only policy, concurrent
session refusal, explicit full-audit verification and truthful scope/timing reports.
Changed Python compiles in memory and governed header QML lint passes. Complete
package provenance/assets/privacy, frozen About/header/lifecycle, actual packaged
WebEngine and normal Start-menu checks precede final release reporting. Actual
desktop/WebEngine checks run unrestricted without disabling its sandbox.

Build from clean committed canonical main, push normally, verify its full live
remote SHA and package the exact checkpoint. Install through the governed helper,
preserving the installed runtime/configuration until the new package passes.
Update the existing durable private launcher/deployment metadata and verify the
one normal Start-menu entry. Retire temporary build/rollback/deployment EXE copies
after installation passes, maintaining one main application executable.
Final source/build hashes and measurements live in the workstation evidence and
dashboard so post-build reporting does not alter the embedded source SHA.

The application still performs its accepted Qt/QML/data startup and opening
sequence. This repair does not change accepted motion, readiness deadlines,
legacy fallback or reduced-motion behavior. Governed identity `0E9EAFA287B6`
remains read-only with cloud freshness unverified. No financial edits,
reconciliation or cross-computer synchronization acceptance is included.
