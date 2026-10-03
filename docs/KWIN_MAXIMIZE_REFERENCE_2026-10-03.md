# KWin maximize/restore reference — 2026-10-03

Research checkpoint for CSPM's independent experimental engine. This document
records upstream observations and architectural implications. It contains no
KWin implementation, translated implementation, or close adaptation. No KWin
source or binary is included in CSPM or its package.

## Provenance and scope

Canonical upstream: [KDE Plasma / KWin](https://invent.kde.org/plasma/kwin).
A non-destructive `git ls-remote` and shallow bare fetch of that upstream
established master revision **ee272a4d33c4d7966ee342e051313f2cb5813ee0**,
committed **2026-10-03 02:01:18 UTC**. Sources were inspected from a separate
temporary bare reference repository, outside CSPM. The links below pin KDE's
official GitHub mirror to that exact canonical revision.

The latest final release tag observed in the fetched refs was **v6.7.5**,
peeled commit **ab7df7ccb7c6af20f4b279cd6220f7cd3d2267d7** (2026-09-08).
Master also advertises v6.7.90/v6.7.91 prereleases. A direct comparison confirms
that the maximize script and timeline are unchanged between v6.7.5 and this
master; offscreen rendering has newer GPU allocation, fencing, color handling
and error propagation. Current development head and final release are distinct.
Neither identifies the exact Fedora/KDE version, settings, hardware, or effect
Cory previously saw. That remains **STILL UNKNOWN**.

No KWin runtime was executed. Behavioral claims below are **SUPPORTED BY
OBSERVATION** of current source, rather than desktop motion measurements.

## Actual effect and presentation path

The ordinary default effect has plugin ID `maximize`, display name **Stretch**,
is enabled by default, and belongs to the exclusive maximize category. It is
a JavaScript effect over KWin's C++ compositor animation machinery. It is not
a wave, spring, wobble, or application layout animation. [Metadata](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/plugins/maximize/package/metadata.json).

Before the requested state changes, the effect records the old frame geometry
and requests retention of its rendered appearance. When the actual maximize
state changes, it animates compositor **Size** and **Translation** using
**OutCubic**, with a nominal **250 ms** duration. An old-appearance crossfade
uses the same curve and is retargeted so the animations finish together. A
forced blur role remains through the transition. These are compositor
transformations, not repeated client resizing. [Effect script](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/plugins/maximize/package/contents/code/main.js).

The C++ painter interpolates desired dimensions relative to the current final
frame size, applies centered size compensation, then translation. Geometry
effects mark the window transformed; the appearance transfer marks it
translucent. The result is a changing compositor representation of one window,
without rebuilding the application's workspace. There is no separate
header-preservation mechanism in this path: decorations and content can scale.
[Animation painter](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/effect/animationeffect.cpp).

## Duration, clock and continuity

The nominal duration is multiplied by the configured animation-duration factor
and clamped to a minimum of 1 ms. The factor is obtained from KWin options and
the KDE settings entry, whose default is 1. Thus 250 ms is not a universal
measured transaction time. [Duration scaling](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/effect/effect.cpp),
[options](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/options.cpp),
[settings](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/kwin.kcfg).

**DISPROVEN:** the assumption that current KWin uses uncapped absolute
wall-clock progress for this effect. Its `TimeLine` accumulates elapsed
**predicted presentation timestamp deltas** through `AnimationClock`. The first
tick contributes zero. Backward timestamps contribute zero. Deltas use
millisecond granularity and are capped to an interval calculated from the
smaller of the output refresh rate and 60 Hz. Missed frames therefore do not
cause a large progress catch-up; real duration can extend. The accumulated
progress is eased by Qt's curve. This favors bounded displacement over a
strict wall-clock deadline. [Timeline and clock](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/effect/timeline.cpp).

The render loop predicts presentation against vblank using a steady clock,
measured rendering cost and safety margin. It supports multiple pending
frames, uses hysteresis when switching buffering behavior, and revises the
schedule using actual completion timestamps. Animation repaint requests
continue until the timeline ends; damaged/transformed regions are tracked.
This is desktop-compositor scheduling, not an application 16 ms timer.
[Render loop](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/core/renderloop.cpp).

There is no demonstrated guarantee here of continuous acceleration/jerk on
interruption. The maximize script cancels existing geometry animation,
retargets appearance transfer, and cancels both when an unexpected dimension
change occurs. General animation machinery also supports reversal; retargeting
preserves the current interpolated value and resets the timeline. Value
continuity alone does not prove velocity continuity. Do not claim KWin's
interrupt semantics satisfy CSPM's stricter perceptual contract.

## GPU surfaces, target availability and handoff

The previous appearance is rendered once into compositor-owned GPU storage.
During appearance transfer, KWin paints current live content underneath and
the retained old appearance above with progressively reduced opacity.
Snapshot margins are corrected to align its frame when source/target sizes
differ. Current master uses EGL swapchain storage and native fences; it
preserves the output blending color space and requests higher precision where
supported. Pixel-grid snapping and physical-scale texture dimensions are
explicit. No full-window CPU screenshot/readback/reupload or second target
snapshot is required by this path. At completion the retained representation
is released and ordinary painting continues. [Offscreen and crossfade renderer](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/effect/offscreeneffect.cpp).

On Wayland, configure acknowledgment and a committed client buffer lead to
geometry/state adoption. Shape movement is started by the actual state signal;
this does not manufacture a finished responsive client layout before the
application renders it. The upstream test supplies the new client-sized buffer
before asserting that the effect is active. [Wayland state handling](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/src/xdgshellwindow.cpp),
[maximize/restore integration test](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/autotests/integration/effects/maximize_animation_test.cpp).

**DISPROVEN:** treating this source as evidence that CSPM's previously measured
roughly 552 ms target-layout/readiness work automatically fits a 300 ms complete
transaction. KWin controls window presentation outside the client process;
it does not eliminate arbitrary application layout/render latency. Its test
verifies activation/completion, not mouse-to-photon duration, jerk, stable
header proportions or a matching frozen/live pixel handoff.

## Transferable lessons and Windows adaptations

**WORKING HYPOTHESIS:** the useful architectural lesson is ownership of a
stable previous GPU appearance, independently transformed presentation, and
current live target pixels, all scheduled coherently. CSPM still needs fixed
header geometry, exact native physical endpoints, prompt cold-request behavior,
and a bounded complete transaction. Its one absolute clock is an independent
choice required by this experiment, not a transcription of KWin's clock.

The closest supported Windows facilities are:

- **DirectComposition / Windows composition visuals:** retained GPU content,
  clipping, transforms, opacity, and compositor-thread animation. One commit
  applies its visual changes in one frame. Content still has to be supplied;
  these APIs do not compute QML layout or expose a general arbitrary top-level
  window texture. [Composition model](https://learn.microsoft.com/en-us/windows/win32/directcomp/basic-concepts),
  [independent animation](https://learn.microsoft.com/en-us/windows/win32/directcomp/animation).
- **DXGI composition swapchains:** supported Direct3D content for a visual;
  the documented API requires flip-sequential presentation and stretch scaling.
  A native presentation host and resource synchronization remain application
  responsibilities. [Composition swapchain API](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/nf-dxgi1_2-idxgifactory2-createswapchainforcomposition).
- **Layered HWND composition wrappers:** the documented example and cloak
  guidance use a layered child window. Resizing updates its composed content;
  moving offscreen or making it zero-sized stops composition. This is not
  evidence of a drop-in, stable old/new surface API for CSPM's existing
  top-level Qt swapchain. [HWND surface wrapper](https://learn.microsoft.com/en-us/windows/win32/api/dcomp/nf-dcomp-idcompositiondevice-createsurfacefromhwnd).
- **DWM thumbnails:** live two-dimensional source/destination relationships,
  rather than owned endpoint textures. They offer no documented programmable
  texture import or retention primitive that fixes CSPM's prior clipping and
  source/live handoff failures. [Thumbnail model](https://learn.microsoft.com/en-us/windows/win32/dwm/thumbnail-ovw).
- **Windows Graphics Capture:** public HWND capture exists from Windows 10
  1903 and supplies asynchronous Direct3D frames. It is a capture facility,
  not atomic scene/presentation ownership; availability and latency require
  measurement. [Window capture interop](https://learn.microsoft.com/en-us/windows/win32/api/windows.graphics.capture.interop/nf-windows-graphics-capture-interop-igraphicscaptureiteminterop-createforwindow),
  [frame-pool model](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture).

Direct3D shared handles can open one allocation on another compatible device,
but descriptor flags, lifetime and synchronization are still mandatory.
Sharing memory alone does not establish a rendered-frame fence or eliminate
client layout time. [Shared handle](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/nf-dxgi1_2-idxgiresource1-createsharedhandle),
[opening a shared resource](https://learn.microsoft.com/en-us/windows/win32/api/d3d11_1/nf-d3d11_1-id3d11device1-opensharedresource1).

Unsupported compositor hooks, private DWM window-texture extraction, changing
the global Qt renderer to imitate Linux, and copying KWin internals are
**unsafe or impractical premises** for this scoped independent experiment.

## Qt/PySide feasibility checkpoint

Qt C++ documents native D3D texture import and redirected Qt Quick rendering.
Native resources must belong to a compatible device/context and native
interfaces have version compatibility limits. [Qt native texture import](https://doc.qt.io/qt-6/qnativeinterface-qsgd3d11texture.html),
[render control](https://doc.qt.io/qt-6/qquickrendercontrol.html),
[QRhi import contract](https://doc.qt.io/qt-6/qrhitexture.html).

**PROVEN BY MEASUREMENT — static API availability only:** importing the
installed **PySide6 6.10.3** modules without constructing a window establishes:

| Available binding | Missing binding |
| --- | --- |
| `QQuickWindow.createTextureFromRhiTexture` | `QRhiTexture.createFrom` |
| `QSGTexture.rhiTexture` | `QRhiTexture.nativeTexture` / `NativeTexture` |
| `QQuickRenderTarget.fromD3D11Texture` | exposed `QNativeInterface.QSGD3D11Texture` |
| `QQuickTextureFactory.createTexture` | direct native-pointer texture-factory entry point |

The official Python documentation agrees with the exposed API surface.
The render-target factory accepts a destination attachment; it is not itself
a sampler texture import into an existing shader. **DISPROVEN:** assuming the
bound Python API directly supplies the proposed native sampler import.
The experiment subsequently selected an independently authored Windows SDK
C++ DirectComposition bridge, outside Qt's private ABI. That route has its own
GPU synchronization, render-thread access and lifetime requirements; this
KWin/API research does not validate its runtime behavior. Runtime evidence is
recorded separately in the clean-room learning checkpoint. Do not assume C++
API availability proves a bound Python implementation.
[Python texture API](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QRhiTexture.html),
[Python texture factory](https://doc.qt.io/qtforpython-6/PySide6/QtQuick/QQuickTextureFactory.html),
[Python render targets](https://doc.qt.io/qtforpython-6/PySide6/QtQuick/QQuickRenderTarget.html).

## Per-file licensing record

Every source file below was inspected at the pinned revision. All listed C++
and JavaScript files declare **SPDX-License-Identifier: GPL-2.0-or-later**.
The two metadata/settings exceptions are recorded without inventing an SPDX
declaration. Additional files used for evidence are included so that this is
not a repository-wide license inference.

| Exact upstream path | Role / observed license |
| --- | --- |
| `src/plugins/maximize/package/contents/code/main.js` | effect; GPL-2.0-or-later |
| `src/plugins/maximize/package/metadata.json` | effect identity/default; no SPDX header, KPlugin license field `GPL` |
| `src/effect/animationeffect.cpp` | painter, repaint, cancellation/retarget; GPL-2.0-or-later |
| `src/effect/animationeffect.h` | animation clock/API; GPL-2.0-or-later |
| `src/effect/anidata.cpp` | animation start/activity; GPL-2.0-or-later |
| `src/effect/anidata_p.h` | animation data; GPL-2.0-or-later |
| `src/effect/timeline.cpp` | clock/progress/reversal; GPL-2.0-or-later |
| `src/effect/timeline.h` | timeline API; GPL-2.0-or-later |
| `src/effect/offscreeneffect.cpp` | GPU snapshots/live appearance transfer; GPL-2.0-or-later |
| `src/effect/offscreeneffect.h` | compositor redirection API; GPL-2.0-or-later |
| `src/effect/effect.cpp` | duration scaling; GPL-2.0-or-later |
| `src/effect/effecthandler.cpp` | factor delegation; GPL-2.0-or-later |
| `src/effect/effectwindow.cpp` | window-to-effect signal mapping; GPL-2.0-or-later |
| `src/scripting/scriptedeffect.cpp` | JavaScript duration delegation; GPL-2.0-or-later |
| `src/options.cpp` | configuration factor; GPL-2.0-or-later |
| `src/kwin.kcfg` | default factor; no in-file SPDX declaration observed |
| `src/xdgshellwindow.cpp` | configure/commit/geometry/state boundary; GPL-2.0-or-later |
| `src/core/renderloop.cpp` | presentation scheduling; GPL-2.0-or-later |
| `src/scene/surfaceitem_wayland.cpp` | committed client buffer/frame callbacks; GPL-2.0-or-later |
| `autotests/integration/effects/maximize_animation_test.cpp` | upstream maximize/restore test; GPL-2.0-or-later |

Each exact path resolves under this
[revision-pinned source tree](https://github.com/KDE/kwin/tree/ee272a4d33c4d7966ee342e051313f2cb5813ee0).
The reviewed license text is
[LICENSES/GPL-2.0-or-later.txt](https://github.com/KDE/kwin/blob/ee272a4d33c4d7966ee342e051313f2cb5813ee0/LICENSES/GPL-2.0-or-later.txt).
Commercial sale is permitted by that license; distribution of covered code
or a covered derivative brings notice, licensing and corresponding-source
obligations. Translation is expressly within its modification scope.
Reading this source does not grant permission to make a proprietary close
adaptation. CSPM's experiment uses abstract architectural observations and
independently authored code; no GPL integration is proposed or approved.
This checkpoint does not certify the legal status of any future derivative.

## Next evidence checkpoint

**WORKING HYPOTHESIS:** GPU ownership could remove avoidable screenshot
roundtrips, while one independent presentation clock removes the production
preparation/settlement boundary. **STILL UNKNOWN:** the candidate's complete
speed, cold target readiness, header/pixel fidelity, DPI safety and physical
frame continuity. Those require populated-app measurement; this research
does not pass any of the candidate's motion acceptance gates.

Validation here is sandbox-safe source/API inspection only. No desktop GPU,
KWin execution, WebEngine e2e, or CSPM transition validation was performed.
