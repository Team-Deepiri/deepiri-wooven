#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x .venv/bin/python ]]; then PY=.venv/bin/python
else PY=python3
fi
$PY -c "from deepiri_weft.transport import clone_url; print(clone_url('github.com','x','y','ssh'))"
$PY -c "from deepiri_weft import __version__; print('deepiri-weft', __version__)"
$PY -c "from deepiri_weft.cred_manager import config_dir; print('config', config_dir())"
if [[ -x .venv/bin/pytest ]]; then .venv/bin/pytest -q tests/
elif command -v pytest >/dev/null 2>&1; then pytest -q tests/
else echo "(skip pytest: not installed)"
fi
