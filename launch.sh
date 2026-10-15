#!/usr/bin/env bash
set -euo pipefail
cspm_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export CSPM_RUNTIME_DIR="${CSPM_RUNTIME_DIR:-$HOME/.cspm_data}"
export CSPM_DATA_DIR="${CSPM_DATA_DIR:-$CSPM_RUNTIME_DIR}"
export CSPM_LOCAL_DATA_DIR="${CSPM_LOCAL_DATA_DIR:-$CSPM_DATA_DIR/onedrive-replica}"
# This desktop has a capable GPU; its four-core CPU must not suppress the
# requested light effects. An explicit user override still takes precedence.
export CSPM_LOW_PERF="${CSPM_LOW_PERF:-0}"
# Existing cinematic light/flight surfaces require absolute desktop geometry.
# KWin still owns system resize/maximize animations for this XWayland client.
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
fi
if [[ -x "$cspm_root/dist/CSPM/CSPM" ]]; then
    exec "$cspm_root/dist/CSPM/CSPM" "$@"
fi
exec "$cspm_root/.venv-fedora/bin/python" "$cspm_root/src/python/main.py" "$@"
