"""Idempotent ~/.ssh/config Host blocks for forge identities."""

from __future__ import annotations

from pathlib import Path


def _markers(host: str) -> tuple[str, str]:
    h = host.strip().lower()
    return (
        f"# --- deepiri-weft begin {h} ---\n",
        f"# --- deepiri-weft end {h} ---\n",
    )


def _block(host: str, identity_file: str) -> str:
    path = str(Path(identity_file).expanduser())
    begin, end = _markers(host)
    inner = (
        f"Host {host}\n"
        f"    HostName {host}\n"
        f"    User git\n"
        f"    IdentityFile {path}\n"
        f"    IdentitiesOnly yes\n"
    )
    return begin + inner + end


def read_ssh_config() -> str:
    p = Path.home() / ".ssh" / "config"
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8")


def strip_managed_block(text: str, host: str) -> str:
    begin, end = _markers(host)
    if begin not in text or end not in text:
        return text
    out: list[str] = []
    skip = False
    for line in text.splitlines(keepends=True):
        if line == begin:
            skip = True
            continue
        if line == end:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "".join(out)


def apply_identity_block(host: str, identity_file: str) -> tuple[bool, str]:
    host = host.strip()
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.is_dir():
        return False, "~/.ssh does not exist. Create it with mkdir -m 700 ~/.ssh"
    cfg = ssh_dir / "config"
    body = read_ssh_config()
    body = strip_managed_block(body, host)
    block = _block(host, identity_file)
    new_body = (body.rstrip() + "\n\n" if body.strip() else "") + block
    cfg.write_text(new_body.lstrip(), encoding="utf-8")
    try:
        cfg.chmod(0o600)
    except OSError:
        pass
    return True, f"Wrote managed Host {host} block to {cfg}"
