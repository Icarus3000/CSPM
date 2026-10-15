#!/usr/bin/env bash
# Governed POSIX counterpart of qmllint.ps1; no Windows GUI tool is invoked.
set -euo pipefail
cspm_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cspm_python="${VIRTUAL_ENV:-$cspm_root/.venv-fedora}/bin/python"
exec "$cspm_python" "$cspm_root/scripts/qmllint_linux.py" "$@"
