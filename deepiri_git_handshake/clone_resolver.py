"""Resolve SSH vs HTTPS for git clone with profile, history, and one-time prompts."""

from __future__ import annotations

import shutil
import sys

from deepiri_git_handshake import cred_manager as cm
from deepiri_git_handshake.clone_parser import CloneTarget, parse_clone_arg
from deepiri_git_handshake.transport import clone_url, detect_transport
from deepiri_git_handshake.transport_prefs import get_last_transport, record_transport


def _ssh_available(host: str) -> bool:
    return detect_transport(host) == "ssh"


def _https_available(host: str) -> bool:
    if cm.get_pat(host):
        return True
    if shutil.which("gh"):
        import subprocess

        r = subprocess.run(
            ["gh", "auth", "status", "--hostname", host],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            return True
    return True


def _prompt_transport(host: str, ssh_ok: bool, https_ok: bool) -> str:
    if sys.stdin.isatty() and sys.stdout.isatty():
        print(f"\nDeepiri Git Handshake: choose transport for {host}", file=sys.stderr)
        if ssh_ok:
            print("  [1] SSH", file=sys.stderr)
        if https_ok:
            print("  [2] HTTPS", file=sys.stderr)
        while True:
            try:
                choice = input("Enter 1 or 2: ").strip()
            except (EOFError, KeyboardInterrupt):
                print(file=sys.stderr)
                break
            if choice == "1" and ssh_ok:
                return "ssh"
            if choice == "2" and https_ok:
                return "https"
            print("Invalid choice.", file=sys.stderr)
    if ssh_ok and not https_ok:
        return "ssh"
    if https_ok and not ssh_ok:
        return "https"
    return detect_transport(host)


def resolve_transport(
    host: str,
    *,
    explicit: str | None = None,
    interactive: bool = True,
) -> str:
    host = host.strip().lower()
    if explicit in ("ssh", "https"):
        record_transport(host, explicit)
        return explicit

    profile = cm.get_profile(host)
    pref = profile.get("transport")
    if pref in ("ssh", "https"):
        record_transport(host, pref)
        return pref

    last = get_last_transport(host)
    ssh_ok = _ssh_available(host)
    https_ok = _https_available(host)

    if last in ("ssh", "https"):
        if last == "ssh" and ssh_ok:
            return "ssh"
        if last == "https" and https_ok:
            return "https"

    if ssh_ok and https_ok:
        if interactive:
            chosen = _prompt_transport(host, ssh_ok, https_ok)
            record_transport(host, chosen)
            return chosen
        chosen = detect_transport(host)
        record_transport(host, chosen)
        return chosen

    if ssh_ok:
        record_transport(host, "ssh")
        return "ssh"
    if https_ok:
        record_transport(host, "https")
        return "https"

    chosen = detect_transport(host)
    record_transport(host, chosen)
    return chosen


def resolve_clone_url(source: str, *, interactive: bool = True) -> tuple[str, str]:
    """Return (resolved_url, transport) for a git clone source argument."""
    target = parse_clone_arg(source)
    if target is None:
        return source, "unknown"

    if target.transport in ("ssh", "https"):
        record_transport(target.host, target.transport)
        url = clone_url(target.host, target.owner, target.repo, target.transport)
        return url, target.transport

    transport = resolve_transport(target.host, interactive=interactive)
    url = clone_url(target.host, target.owner, target.repo, transport)
    return url, transport


def resolve_clone_target(target: CloneTarget, *, interactive: bool = True) -> tuple[str, str]:
    if target.transport in ("ssh", "https"):
        record_transport(target.host, target.transport)
        return (
            clone_url(target.host, target.owner, target.repo, target.transport),
            target.transport,
        )
    transport = resolve_transport(target.host, interactive=interactive)
    return clone_url(target.host, target.owner, target.repo, transport), transport
