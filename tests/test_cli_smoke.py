"""CLI entry smoke tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_version() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "deepiri_weft.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert r.stdout.strip()
    assert r.stdout.strip()[0].isdigit()


def test_cred_list_exits_zero(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    r = subprocess.run(
        [sys.executable, "-m", "deepiri_weft.cli", "cred", "list"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert r.returncode == 0
