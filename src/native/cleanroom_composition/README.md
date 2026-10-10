# Integrated native motion bridge

The October 9 product decision accepts native motion as the integrated
candidate's default. This bridge is preserved from audited descendant
`340a823dd6a4a566bf84f225ae958d590e8e9154`; its implementation is unchanged
from the native experimental checkpoint. Historical qualification evidence
remains on the experiment and qualification branches, without rewritten results.

Build with `scripts/build_cleanroom_native.ps1 -OutputName cspm_native_motion.dll`.
The runtime uses ABI 1 and the Windows x64 C calling convention. Immutable GPU
source/target frames use the public Qt D3D11 renderer context; pixel data stays
on the GPU. Each host and every exported frame has one bounded cleanup owner.

Normal operation uses explicit source-band creation, deferred source visibility,
validated source attachment, native owner-thread ordering, a 350 ms trajectory,
the existing 240 ms cold target gate, and the unchanged 100 ms presentation-slot
gate. No collector, readback, observer, alternate QML surface, diagnostic selector,
or historical evidence constructor enters normal startup.

Before motion, failed source preparation uses legacy motion. After motion has
started, failures restore the live requested target and input and are recorded
as safe rejection, never as a successful native operation or legacy animation.
System reduced motion overrides the local preference. GPU/frame submission and
a Qt live-frame notification do not establish physical presentation continuity.

Source-band variability, cold Productivity readiness, retained Home/taskbar
pixel failures, repeated physical input, WebEngine and mixed-DPI/lifecycle
coverage remain under hardening. Sources or endpoints outside the source
monitor's work area are refused before motion and use the preserved legacy path.
