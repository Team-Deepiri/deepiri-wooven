"""Background daemon for clone transport resolution."""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
from pathlib import Path
from typing import Any

from deepiri_git_handshake.clone_resolver import resolve_clone_url
from deepiri_git_handshake.transport_prefs import socket_path

LOG = logging.getLogger("deepiri_git_handshake.daemon")
PID_FILE_NAME = "daemon.pid"


def pid_path() -> Path:
    return socket_path().parent / PID_FILE_NAME


def _write_pid() -> None:
    pid_path().write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        pid_path().unlink(missing_ok=True)
    except OSError:
        pass


def _remove_socket() -> None:
    try:
        socket_path().unlink(missing_ok=True)
    except OSError:
        pass


def _handle_request(payload: dict[str, Any]) -> dict[str, Any]:
    cmd = payload.get("cmd")
    if cmd == "ping":
        return {"ok": True, "pong": True}
    if cmd == "resolve_clone":
        source = str(payload.get("url", "")).strip()
        interactive = bool(payload.get("interactive", False))
        if not source:
            return {"ok": False, "error": "missing url"}
        url, transport = resolve_clone_url(source, interactive=interactive)
        return {"ok": True, "url": url, "transport": transport}
    return {"ok": False, "error": f"unknown cmd: {cmd}"}


def _serve_client(conn: socket.socket) -> None:
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        line = data.split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
        if not line:
            return
        payload = json.loads(line)
        response = _handle_request(payload)
        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOG.debug("client error: %s", exc)
    finally:
        conn.close()


def run_daemon(*, foreground: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    sock_file = socket_path()
    _remove_socket()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_file))
    server.listen(8)
    _write_pid()

    def _shutdown(_signum: int, _frame: object) -> None:
        LOG.info("shutting down")
        server.close()
        _remove_socket()
        _remove_pid()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    LOG.info("daemon listening on %s", sock_file)
    if foreground:
        LOG.info("running in foreground")
    try:
        while True:
            conn, _ = server.accept()
            _serve_client(conn)
    finally:
        server.close()
        _remove_socket()
        _remove_pid()


def daemon_request(payload: dict[str, Any], timeout: float = 3.0) -> dict[str, Any] | None:
    path = socket_path()
    if not path.exists():
        return None
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(timeout)
        client.connect(str(path))
        client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk
        client.close()
        line = data.split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
        if not line:
            return None
        result = json.loads(line)
        if isinstance(result, dict):
            return result
    except (OSError, json.JSONDecodeError):
        return None
    return None


def daemon_running() -> bool:
    p = pid_path()
    if not p.is_file():
        return False
    try:
        pid = int(p.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return socket_path().exists()


def main() -> None:
    foreground = "--foreground" in sys.argv or "-f" in sys.argv
    run_daemon(foreground=foreground)


if __name__ == "__main__":
    main()
