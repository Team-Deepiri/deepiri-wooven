"""Git shim that intercepts clone and resolves SSH/HTTPS transport."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from deepiri_git_handshake.clone_parser import parse_clone_arg
from deepiri_git_handshake.clone_resolver import resolve_clone_url
from deepiri_git_handshake.daemon import daemon_request
from deepiri_git_handshake.transport_prefs import install_state_path


def _real_git() -> str:
    env_path = os.environ.get("DGH_REAL_GIT", "").strip()
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path
    state = install_state_path()
    if state.is_file():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
            saved = str(data.get("real_git", "")).strip()
            if saved and os.path.isfile(saved) and os.access(saved, os.X_OK):
                return saved
        except (OSError, json.JSONDecodeError):
            pass
    found = shutil.which("git")
    if found:
        return found
    raise SystemExit("git-handshake: real git binary not found")


def _resolve_via_daemon(source: str, *, interactive: bool) -> tuple[str, str] | None:
    resp = daemon_request(
        {"cmd": "resolve_clone", "url": source, "interactive": interactive},
        timeout=5.0,
    )
    if not resp or not resp.get("ok"):
        return None
    url = str(resp.get("url", "")).strip()
    transport = str(resp.get("transport", "unknown")).strip()
    if not url:
        return None
    return url, transport


def _maybe_rewrite_clone(argv: list[str]) -> list[str]:
    if len(argv) < 3 or argv[1] != "clone":
        return argv

    source_idx = 2
    while source_idx < len(argv) and argv[source_idx].startswith("-"):
        if argv[source_idx] in ("--",):
            source_idx += 1
            break
        if argv[source_idx] in ("--branch", "-b") and source_idx + 1 < len(argv):
            source_idx += 2
            continue
        source_idx += 1

    if source_idx >= len(argv):
        return argv

    source = argv[source_idx]
    if parse_clone_arg(source) is None:
        return argv

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    resolved = _resolve_via_daemon(source, interactive=interactive)
    if resolved is None:
        url, transport = resolve_clone_url(source, interactive=interactive)
    else:
        url, transport = resolved

    if url != source:
        print(
            f"git-handshake: using {transport.upper()} → {url}",
            file=sys.stderr,
        )
    new_argv = list(argv)
    new_argv[source_idx] = url
    return new_argv


def main() -> None:
    real = _real_git()
    argv = _maybe_rewrite_clone(sys.argv)
    os.execv(real, [real, *argv[1:]])


if __name__ == "__main__":
    main()
