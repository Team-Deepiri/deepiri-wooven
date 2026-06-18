"""Resolve SSH vs HTTPS from user choice or machine hints."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _ssh_probe_git_host(host: str, timeout: float = 5.0) -> bool:
    """Return True if SSH auth to git@host looks usable (GitHub-style probe)."""
    if not shutil.which("ssh"):
        return False
    try:
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "ConnectTimeout=3",
                "-T",
                f"git@{host}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    combined = f"{r.stdout or ''}\n{r.stderr or ''}".lower()
    if r.returncode == 1 and "successfully authenticated" in combined:
        return True
    if "permission denied" in combined and r.returncode != 0:
        return False
    return False


def _has_default_ssh_identity() -> bool:
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.is_dir():
        return False
    for pattern in ("id_ed25519", "id_rsa", "id_ecdsa"):
        if (ssh_dir / pattern).is_file():
            return True
    return any(p.suffix == "" and p.name.startswith("id_") for p in ssh_dir.glob("id_*"))


def detect_transport(host: str) -> str:
    """
    Pick a sensible default: probe git@host, else fall back to identity presence, else HTTPS.
    """
    if _ssh_probe_git_host(host):
        return "ssh"
    if _has_default_ssh_identity():
        return "ssh"
    return "https"


def clone_url(host: str, owner: str, repo: str, transport: str) -> str:
    owner = owner.strip().strip("/")
    repo = repo.strip().removesuffix(".git")
    if transport == "ssh":
        return f"git@{host}:{owner}/{repo}.git"
    return f"https://{host}/{owner}/{repo}.git"
