# PROJECT JELLY: Animation & Physics Specification (v2.1)

**STATUS: READ-ONLY REFERENCE DOCUMENT**

---

## 1. Global Physics Rules (The "Jelly" Standard)

Apply to all windows/modals.

- **Conservation of Volume**: If ScaleX > 1.0 (wider), ScaleY must be < 1.0 (shorter).
- **Internal Inertia (The Container Law)**: The Window (Background) moves first. The Content (Inputs/Buttons) moves second.
- **Constraint**: Contents must NEVER float outside the window borders. Use `Item.clip: true` or relative positioning to ensure they stay strictly inside the blue frame.

---

## 2. Opening Sequence: "The Mario Drop"

### A. Current State (DEPRECATE THIS)

**Old Logic: Translation** - Flies in from Left (800ms).
**Old Logic: Rotation** - Spins from -45° to 0°.
**Old Logic: Scale** - Complex multi-phase bounce (Squash/Stretch/Elastic).

**Status**: REMOVE all lateral movement and rotation logic. Keep the "Squash" logic but re-tune it.

### B. Target State (IMPLEMENT THIS)

**Concept**: Vertical drop from top → Heavy Impact → Internal Slide.

**Drop (Container)**:
- Start: Y: -500 (Off-screen Top)
- End: Y: Center
- Easing: OutBounce or OutExpo
- Duration: 600ms

**Impact (Squash)**:
- Trigger: On Y: Center
- Scale: 1.0 → 1.3 (Wide) / 0.7 (Flat) → 1.0
- Visual Cue: Flash border white for 50ms

**Internal Lag (The Contents)**:
- Trigger: 100ms after Drop begins
- Action: All contents start at Y: -30px (relative to window) and slide down to Y: 0
- Stagger: Header (0ms delay) → Input 1 (50ms) → Input 2 (100ms) → Button (150ms)

---

## 3. Closing Sequence: "The Slingshot Exit"

### A. Current State (DEPRECATE THIS)

**Old Logic: Translation** - Yanked to the Left with overshoot.
**Old Logic: Scale** - Uniform shrink to 0.0.
**Old Logic: Rotation** - -10° tilt.

**Status**: REMOVE lateral yank and uniform shrink.

### B. Target State (IMPLEMENT THIS)

**Concept**: Pull Back → Snap Down → High-Speed Stretch.

**Anticipation (Wind-Up)**:
- Duration: 250ms
- Action: Scale to 0.9 (Uniform) + Tilt -5° + Move Up 50px (Opposite to exit)

**Snap (Launch)**:
- Duration: 350ms
- Action: Move rapidly to Y: ScreenHeight + 500 (Off-screen Bottom)
- Easing: InBack (Vacuum effect)

**Shear (Speed Deformation)**:
- Trigger: During Snap
- Action: ScaleY: 1.5 (Long) + ScaleX: 0.6 (Thin)
- Note: Ensure contents fade out (Opacity: 0) fast enough (200ms) to avoid clipping during this stretch.

---

**Last Updated**: February 9, 2026
**Version**: 2.1
