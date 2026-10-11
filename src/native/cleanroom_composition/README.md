# CSPM native motion bridge

This bridge is the visually accepted maximize/restore implementation from
19d030d9516ef026da158e610db432a434335966. Its trajectory, readiness deadlines,
ownership and safe recovery contracts are preserved for promotion.

Build from the repository root with an existing x64 MSVC C++ toolchain and
Windows SDK:

    ./scripts/build_cleanroom_native.ps1 -ValidateContracts

The governed release builder load-checks the ABI and includes
outputs/native_cleanroom/cspm_native_motion.dll. Native is the ordinary default;
legacy fallback and authoritative Windows reduced-motion preferences remain.
Use CSPM.exe --set-motion-engine legacy while CSPM is closed to select legacy
for the next launch. --motion-settings provides the same local choice.

Visual product acceptance does not eliminate intermittent target-readiness/GPU
deadline misses or establish historical qualification gates. Recovery retains
live visibility and input. Multi-monitor and mixed-DPI coverage remains limited.
