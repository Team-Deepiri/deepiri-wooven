"""Track last-used transport per forge host."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deepiri_git_handshake import cred_manager as cm


def _prefs_path() -> Path:
    d = cm.config_dir()
    return d / "transport_prefs.json"


def load_prefs() -> dict[str, dict[str, Any]]:
    p = _prefs_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for host, meta in data.items():
        if isinstance(meta, dict):
            out[str(host).strip().lower()] = dict(meta)
    return out


def save_prefs(prefs: dict[str, dict[str, Any]]) -> None:
    _prefs_path().write_text(json.dumps(prefs, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_last_transport(host: str) -> str | None:
    host = host.strip().lower()
    meta = load_prefs().get(host, {})
    transport = meta.get("last_transport")
    if transport in ("ssh", "https"):
        return transport
    return None


def record_transport(host: str, transport: str) -> None:
    host = host.strip().lower()
    if transport not in ("ssh", "https"):
        return
    prefs = load_prefs()
    prefs[host] = {
        "last_transport": transport,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    save_prefs(prefs)
    cm.upsert_profile(host, transport=transport)


def socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        d = Path(runtime) / "deepiri-git-handshake"
    else:
        d = Path.home() / ".local" / "share" / "deepiri-git-handshake"
    d.mkdir(parents=True, exist_ok=True)
    return d / "daemon.sock"


def install_state_path() -> Path:
    return cm.config_dir() / "install.json"
