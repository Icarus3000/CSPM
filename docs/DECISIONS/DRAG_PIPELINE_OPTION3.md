# Drag Pipeline Option 3 Roadmap

Status: `Option 2 active` (native OS move first, fallback drag only when native move is unavailable).

Purpose:
- Preserve silky native drag now.
- Keep architecture ready for Option 3 (proxy/shadow drag animation layer) without rewriting monitor geometry logic.

Current architecture contract (must remain stable):
1. `beginUserDrag()` starts drag and chooses strategy.
2. `updateUserDrag(dx, dy)` updates only fallback drag path.
3. `finishUserDrag()` finalizes geometry, monitor target, and canvas.

Files owning this contract:
- `src/qml/Main.qml`
- `src/qml/views/MainContent.qml`
- `src/python/main.py` (input mask coordination)

Required invariants:
1. Drag start, active, and end are represented explicitly by the pipeline methods above.
2. Monitor targeting is recomputed at drag end from final window geometry.
3. Green frame represents active monitor usable area.
4. Orange frame remains the interactive canvas region.
5. No clipping of visible window content during fallback drag.

Option 3 target architecture:
1. Keep content window on native move path.
2. Add a drag proxy/shadow layer for deformation effects while pointer moves.
3. Apply visual jelly/deformation to proxy during drag.
4. Commit final geometry to real window at drag end.

Migration checklist (Option 2 -> Option 3):
1. Keep `beginUserDrag/updateUserDrag/finishUserDrag` signatures unchanged.
2. Move drag visuals from content transform to proxy layer.
3. Keep monitor/frame computation in `Main.qml` geometry helpers.
4. Keep input mask logic independent from proxy visuals.
5. Add drag-end reconciliation test for multi-monitor transitions.

Validation checklist:
1. Native drag path chosen on supported systems.
2. Fallback path remains functional if native move fails.
3. No monitor-frame mismatch after dragging across monitors.
4. Closing animation still uses monitor-aware target after cross-monitor drag.
5. Chatpack dump includes this roadmap file.
