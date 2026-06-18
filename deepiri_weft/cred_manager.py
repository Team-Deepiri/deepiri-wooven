"""Forge credential profiles, OS keychain PAT storage, and git helper registration."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import keyring

APP_KEYRING = "deepiri-weft"
PAT_SERVICE = "https-pat"
HELPER_NAME = "weft"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    d = Path(base) / "deepiri-weft"
    d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_path() -> Path:
    return config_dir() / "profiles.json"


def _pat_account(host: str) -> str:
    return host.strip().lower()


def load_profiles() -> dict[str, dict[str, Any]]:
    p = profiles_path()
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


def save_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    profiles_path().write_text(json.dumps(profiles, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_profile(host: str) -> dict[str, Any]:
    return dict(load_profiles().get(host.strip().lower(), {}))


def upsert_profile(
    host: str,
    *,
    transport: str | None = None,
    ssh_identity: str | None = None,
    https_username: str | None = None,
) -> dict[str, Any]:
    host = host.strip().lower()
    profiles = load_profiles()
    cur = dict(profiles.get(host, {}))
    if transport is not None:
        cur["transport"] = transport
    if ssh_identity is not None:
        if not str(ssh_identity).strip():
            cur.pop("ssh_identity", None)
        else:
            cur["ssh_identity"] = str(ssh_identity).strip()
    if https_username is not None:
        if not str(https_username).strip():
            cur.pop("https_username", None)
        else:
            cur["https_username"] = str(https_username).strip()
    profiles[host] = {k: v for k, v in cur.items() if v is not None}
    save_profiles(profiles)
    return profiles[host]


def delete_profile(host: str) -> bool:
    host = host.strip().lower()
    profiles = load_profiles()
    if host not in profiles:
        return False
    del profiles[host]
    save_profiles(profiles)
    return True


def store_pat(host: str, token: str) -> None:
    keyring.set_password(APP_KEYRING, f"{PAT_SERVICE}:{_pat_account(host)}", token.strip())


def get_pat(host: str) -> str | None:
    return keyring.get_password(APP_KEYRING, f"{PAT_SERVICE}:{_pat_account(host)}")


def clear_pat(host: str) -> bool:
    try:
        keyring.delete_password(APP_KEYRING, f"{PAT_SERVICE}:{_pat_account(host)}")
        return True
    except keyring.errors.PasswordDeleteError:
        return False


def https_username_for(host: str) -> str:
    u = get_profile(host).get("https_username")
    if isinstance(u, str) and u.strip():
        return u.strip()
    return "git"


def list_registered_helpers() -> list[str]:
    r = subprocess.run(
        ["git", "config", "--global", "--get-all", "credential.helper"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode != 0:
        return []
    return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]


def git_helper_registered() -> bool:
    return HELPER_NAME in list_registered_helpers()


def register_git_credential_helper() -> tuple[bool, str]:
    if git_helper_registered():
        return True, f"Git credential helper '{HELPER_NAME}' already in global config."
    r = subprocess.run(
        ["git", "config", "--global", "--add", "credential.helper", HELPER_NAME],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "git config failed").strip()
    return True, f"Added credential.helper={HELPER_NAME} (runs git-credential-weft from PATH)."


def unregister_git_credential_helper() -> tuple[bool, str]:
    helpers = list_registered_helpers()
    if HELPER_NAME not in helpers:
        return True, "Helper not present."
    rest = [h for h in helpers if h != HELPER_NAME]
    while (
        subprocess.run(
            ["git", "config", "--global", "--unset", "credential.helper"],
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode
        == 0
    ):
        pass
    for h in rest:
        subprocess.run(
            ["git", "config", "--global", "--add", "credential.helper", h],
            capture_output=True,
            text=True,
            timeout=10,
        )
    return True, f"Removed credential.helper entries and re-registered {len(rest)} helper(s) (weft dropped)."


def pat_status_line(host: str) -> str:
    return "stored in OS keyring" if get_pat(host) else "not set"
