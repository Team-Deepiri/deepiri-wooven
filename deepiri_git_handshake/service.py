"""Install and manage the git-handshake background service."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from deepiri_git_handshake import cred_manager as cm
from deepiri_git_handshake.daemon import daemon_running, pid_path, run_daemon, socket_path
from deepiri_git_handshake.transport_prefs import install_state_path

PACKAGE_NAME = "deepiri-git-handshake"
SERVICE_LABEL = "com.deepiri.git-handshake"
SYSTEMD_UNIT = "deepiri-git-handshake.service"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _packaging_dir() -> Path:
    return _repo_root() / "packaging"


def _local_bin() -> Path:
    return Path.home() / ".local" / "bin"


def _local_lib() -> Path:
    return Path.home() / ".local" / "lib" / PACKAGE_NAME


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", encoding="utf-8", errors="ignore") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _platform_key() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if _is_wsl():
        return "wsl"
    return "linux"


def _python_exe() -> str:
    return sys.executable


def _git_handshake_exe() -> str:
    found = shutil.which("git-handshake")
    if found:
        return found
    return str(_local_bin() / "git-handshake")


def _daemon_cmd() -> list[str]:
    return [_python_exe(), "-m", "deepiri_git_handshake.daemon", "--foreground"]


def _find_real_git(exclude: Path | None = None) -> str | None:
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    shim_names = {"git-handshake-git", "git"}
    for entry in path_entries:
        if not entry:
            continue
        candidate = Path(entry) / "git"
        if exclude and candidate.resolve() == exclude.resolve():
            continue
        if candidate.is_file() and os.access(candidate, os.X_OK):
            if candidate.name in shim_names and "deepiri-git-handshake" in str(candidate):
                continue
            return str(candidate)
    return shutil.which("git")


def save_install_state(*, real_git: str, shim_path: str) -> None:
    state = {
        "real_git": real_git,
        "git_shim": shim_path,
        "platform": _platform_key(),
        "python": _python_exe(),
    }
    install_state_path().write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def install_git_shim() -> tuple[bool, str]:
    lib = _local_lib()
    bin_dir = _local_bin()
    lib.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    shim_target = bin_dir / "git"
    real_git = _find_real_git(exclude=shim_target)
    if not real_git:
        return False, "Could not locate real git binary."

    wrapper = shutil.which("git-handshake-git")
    if not wrapper:
        wrapper = str(bin_dir / "git-handshake-git")
    if not Path(wrapper).is_file():
        return False, "git-handshake-git not on PATH; run pip install first."

    script = f"""#!/usr/bin/env bash
# Deepiri Git Handshake git shim — prepended to PATH by install.sh
export DGH_REAL_GIT={json.dumps(real_git)}
exec {json.dumps(wrapper)} "$@"
"""
    shim_target.write_text(script, encoding="utf-8")
    shim_target.chmod(shim_target.stat().st_mode | 0o111)
    save_install_state(real_git=real_git, shim_path=str(shim_target))
    return True, f"Installed git shim at {shim_target} (real git: {real_git})"


def _systemd_user_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def install_systemd_unit() -> tuple[bool, str]:
    src = _packaging_dir() / "systemd" / SYSTEMD_UNIT
    if not src.is_file():
        return False, f"Missing unit file: {src}"
    dest_dir = _systemd_user_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / SYSTEMD_UNIT
    content = src.read_text(encoding="utf-8")
    content = content.replace("@PYTHON@", _python_exe())
    dest.write_text(content, encoding="utf-8")

    cmds = [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "systemctl failed").strip()
            return False, err
    return True, f"Enabled user systemd service {SYSTEMD_UNIT}"


def install_launchd_agent() -> tuple[bool, str]:
    src = _packaging_dir() / "launchd" / f"{SERVICE_LABEL}.plist"
    if not src.is_file():
        return False, f"Missing plist: {src}"
    dest_dir = Path.home() / "Library" / "LaunchAgents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{SERVICE_LABEL}.plist"
    content = src.read_text(encoding="utf-8")
    content = content.replace("@PYTHON@", _python_exe())
    content = content.replace("@HOME@", str(Path.home()))
    dest.write_text(content, encoding="utf-8")

    uid = str(os.getuid())
    for cmd in (
        ["launchctl", "bootout", f"gui/{uid}", str(dest)],
        ["launchctl", "bootstrap", f"gui/{uid}", str(dest)],
        ["launchctl", "kickstart", "-k", f"gui/{uid}/{SERVICE_LABEL}"],
    ):
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return True, f"Installed launchd agent {dest.name}"


def install_windows_task() -> tuple[bool, str]:
    ps1 = _packaging_dir() / "windows" / "install-service.ps1"
    if not ps1.is_file():
        return False, f"Missing script: {ps1}"
    r = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-Python",
            _python_exe(),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        return False, (r.stderr or r.stdout or "PowerShell install failed").strip()
    return True, (r.stdout or "Installed Windows scheduled task.").strip()


def install_platform_service() -> tuple[bool, str]:
    key = _platform_key()
    if key in ("linux", "wsl"):
        return install_systemd_unit()
    if key == "macos":
        return install_launchd_agent()
    return install_windows_task()


def uninstall_platform_service() -> tuple[bool, str]:
    key = _platform_key()
    if key in ("linux", "wsl"):
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT],
            capture_output=True,
            text=True,
            timeout=30,
        )
        unit = _systemd_user_dir() / SYSTEMD_UNIT
        if unit.is_file():
            unit.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, text=True, timeout=30)
        return True, "Removed systemd user service."
    if key == "macos":
        dest = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"
        uid = str(os.getuid())
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(dest)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if dest.is_file():
            dest.unlink()
        return True, "Removed launchd agent."
    ps1 = _packaging_dir() / "windows" / "uninstall-service.ps1"
    if ps1.is_file():
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    return True, "Removed Windows scheduled task."


def service_status() -> list[str]:
    lines = [
        f"platform: {_platform_key()} ({platform.platform()})",
        f"daemon running: {'yes' if daemon_running() else 'no'}",
        f"socket: {socket_path()} ({'present' if socket_path().exists() else 'missing'})",
        f"pid file: {pid_path()} ({'present' if pid_path().exists() else 'missing'})",
        f"config: {cm.config_dir()}",
    ]
    state = install_state_path()
    if state.is_file():
        try:
            meta = json.loads(state.read_text(encoding="utf-8"))
            lines.append(f"real git: {meta.get('real_git', '(unknown)')}")
            lines.append(f"git shim: {meta.get('git_shim', '(unknown)')}")
        except (OSError, json.JSONDecodeError):
            lines.append("install state: unreadable")
    return lines


def start_service(*, foreground: bool = False) -> tuple[bool, str]:
    if daemon_running() and not foreground:
        return True, "Daemon already running."
    if foreground:
        run_daemon(foreground=True)
        return True, "Daemon exited."
    ok, msg = install_platform_service()
    if ok:
        return True, msg
    run_daemon(foreground=True)
    return True, "Started daemon in foreground (service install failed)."


def stop_service() -> tuple[bool, str]:
    if not pid_path().is_file():
        return True, "Daemon not running."
    try:
        pid = int(pid_path().read_text(encoding="utf-8").strip())
        os.kill(pid, 15)
        return True, f"Sent SIGTERM to daemon (pid {pid})."
    except (OSError, ValueError) as exc:
        return False, str(exc)


def run_install(*, skip_service: bool = False) -> int:
    msgs: list[str] = []
    ok, msg = cm.register_git_credential_helper()
    msgs.append(msg if ok else f"[warn] {msg}")

    ok, msg = install_git_shim()
    msgs.append(msg)
    if not ok:
        for line in msgs:
            print(line)
        return 1

    if not skip_service:
        ok, msg = install_platform_service()
        msgs.append(msg if ok else f"[warn] service: {msg}")

    local_bin = _local_bin()
    path_hint = f'export PATH="{local_bin}:$PATH"'
    msgs.append(f"Add to your shell profile if needed: {path_hint}")
    msgs.append(f"Commands: git-handshake, dgh, git clone (via shim)")
    for line in msgs:
        print(line)
    return 0
