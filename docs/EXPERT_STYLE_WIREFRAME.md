# Expert Style Wireframe

Updated: 2026-06-11

## Purpose

`Expert` is the first outside-QML client tier for CSPM. It is based on the
Professional Option 3 shell, but lives separately from the production Qt/QML app
so the team can prototype a future Flutter or React Native client without
forking backend logic.

## Current Framework Candidates

There are now two separate Expert candidates:

- `expert_client/`: React Native Web browser sketch.
- `expert_flutter/`: native Flutter Windows desktop sketch.

The React Native Web path remains useful for quick browser iteration. The
Flutter path is the native desktop candidate and uses the same general
Professional Option 3 wireframe.

This is still not a final framework decision. The durable question remains which
client stack gives CSPM the best desktop packaging, table/report UX, native
integration, performance, and backend bridge story.

## Shell Contract

The Expert wireframe follows the same Option 3 structure:

- 72px top header with global search / command entry.
- 56px compact module rail.
- Temporary module flyout menus.
- 38px top work-tab bar.
- 44px breadcrumb/orientation bar.
- Full-width workspace host.
- In-frame title/subtitle zone inside each workspace.
- Optional contextual right drawer.

## Run Locally

```powershell
cd expert_client
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Open:

```text
http://127.0.0.1:5174/
```

From the QML app, open Settings and choose:

```text
Expert Web Preview
```

This starts the local React Native Web preview server when needed and opens the
same URL. The ordinary `Style` segmented control intentionally remains only:

```text
Console | Pro
```

because those are the two persisted production QML styles today.

For the native Flutter candidate, choose this from Settings:

```text
Expert Flutter
```

or run from the repo root:

```powershell
.\launch.ps1 -ExpertFlutter
```

That path installs or uses the local Flutter SDK, enables Windows desktop
support, generates the Windows runner if needed, and launches the native Windows
Flutter preview instead of the browser-based web sketch. To prepare Flutter
without launching the preview, run:

```powershell
.\launch.ps1 -SetupFlutter
```

## Next Integration Step

Connect the Client Directory/Profile sample surface to the explicit-start
loopback HTTP JSON boundary:

- `src/python/services/professional_client_service.py`
- `src/python/services/professional_client_loopback_host.py`
- `scripts/run_professional_client_http_poc.py`

The QML app remains the working production application while Expert matures.
