"""Automate common git credential setup for SSH and HTTPS."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from deepiri_weft import cred_manager as cm


def _run(cmd: list[str], timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ensure_ssh_agent_keys(preferred_identity: str | None = None) -> list[str]:
    lines: list[str] = []
    if preferred_identity:
        key = Path(preferred_identity).expanduser()
        if key.is_file():
            add = _run(["ssh-add", str(key)], timeout=30)
            if add.returncode == 0:
                lines.append(f"Loaded preferred key {key.name} into ssh-agent.")
                return lines
            err = (add.stderr or add.stdout or "").strip()
            lines.append(f"Could not add preferred key {key}: {err or 'ssh-add failed'}")
    r = _run(["ssh-add", "-l"], timeout=10)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0 and "no identities" not in out.lower():
        lines.append("SSH agent already has keys loaded.")
        return lines
    if "could not open a connection" in out.lower():
        lines.append("SSH agent is not running. Try: eval \"$(ssh-agent -s)\" && ssh-add ~/.ssh/id_ed25519")
    for name in ("id_ed25519", "id_rsa", "id_ecdsa"):
        key = Path.home() / ".ssh" / name
        if not key.is_file():
            continue
        add = _run(["ssh-add", str(key)], timeout=30)
        if add.returncode == 0:
            lines.append(f"Loaded {key.name} into ssh-agent.")
        else:
            err = (add.stderr or add.stdout or "").strip()
            lines.append(f"Could not add {key.name}: {err or 'ssh-add failed'}")
    return lines


def github_ssh_probe(host: str = "github.com") -> tuple[bool, str]:
    r = _run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=5",
            "-T",
            f"git@{host}",
        ],
        timeout=20,
    )
    combined = f"{r.stdout or ''}\n{r.stderr or ''}"
    success = r.returncode == 1 and "successfully authenticated" in combined.lower()
    return success, combined.strip()


def setup_ssh_report(host: str) -> list[str]:
    report: list[str] = []
    host = host.strip().lower()
    meta = cm.get_profile(host)
    ident = meta.get("ssh_identity")
    if isinstance(ident, str) and ident.strip():
        ident = ident.strip()
    else:
        ident = None

    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.is_dir():
        report.append("~/.ssh is missing. Create it: mkdir -m 700 ~/.ssh")
        return report
    priv = [ssh_dir / n for n in ("id_ed25519", "id_rsa", "id_ecdsa") if (ssh_dir / n).is_file()]
    if not priv and not ident:
        report.append("No id_ed25519 / id_rsa / id_ecdsa private key found.")
        report.append('Create one: ssh-keygen -t ed25519 -C "you@example.com"')
        report.append(f"Add the .pub key at https://{host}/settings/keys (or your org).")
        return report
    if ident and not Path(ident).expanduser().is_file():
        report.append(f"Profile ssh_identity not found on disk: {ident}")
    report.extend(ensure_ssh_agent_keys(ident))
    ok, msg = github_ssh_probe(host)
    if ok:
        report.append(f"SSH to git@{host} is working.")
    else:
        report.append("SSH probe did not show a successful GitHub-style login yet.")
        if msg:
            report.append(msg[:800])
        pub = ssh_dir / "id_ed25519.pub"
        if not pub.is_file():
            pub = ssh_dir / "id_rsa.pub"
        if pub.is_file():
            report.append(f"Public key file: {pub}")
    return report


def setup_https_git(host: str = "github.com") -> list[str]:
    report: list[str] = []
    host = host.strip().lower()
    if cm.git_helper_registered():
        report.append("git credential helper 'weft' is enabled — HTTPS PATs load from the OS keyring.")
    if cm.get_pat(host):
        report.append(f"PAT for {host}: stored ({cm.pat_status_line(host)}).")
    else:
        report.append(f"No PAT in keyring for {host} yet — use the Vault tab or `weft cred pat --host`.")

    if shutil.which("gh"):
        st = _run(["gh", "auth", "status"], timeout=30)
        if st.returncode == 0:
            sg = _run(["gh", "auth", "setup-git"], timeout=30)
            if sg.returncode == 0:
                report.append("Ran `gh auth setup-git` — git can use GitHub CLI for HTTPS.")
            else:
                report.append(f"`gh auth setup-git` failed: {(sg.stderr or '').strip()}")
        else:
            report.append("GitHub CLI is installed but not authenticated.")
            report.append("Run: gh auth login --git-protocol https")
    else:
        helper: str
        if sys.platform == "darwin":
            helper = "osxkeychain"
        elif sys.platform == "win32":
            helper = "manager"
        else:
            helper = "cache --timeout=28800"
        if not cm.git_helper_registered():
            cfg = _run(["git", "config", "--global", "credential.helper", helper], timeout=10)
            if cfg.returncode == 0:
                report.append(f"Set `credential.helper` globally to: {helper}")
            else:
                report.append(f"Could not set credential.helper: {(cfg.stderr or '').strip()}")
        report.append("Tip: install GitHub CLI for smoother HTTPS auth: https://cli.github.com")
    return report


def setup_for_transport(transport: str, host: str = "github.com") -> list[str]:
    t = transport.lower()
    if t == "ssh":
        return setup_ssh_report(host)
    return setup_https_git(host)


def manager_summary(host: str) -> list[str]:
    host = host.strip().lower()
    lines = [
        f"[vault] {host}",
        f"  profile: {cm.get_profile(host) or '(none)'}",
        f"  PAT: {cm.pat_status_line(host)}",
        f"  git helper 'weft': {'yes' if cm.git_helper_registered() else 'no'}",
    ]
    return lines
