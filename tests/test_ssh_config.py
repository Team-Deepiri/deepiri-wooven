"""Tests for managed SSH config blocks."""

from __future__ import annotations

from pathlib import Path

from deepiri_weft.ssh_config import apply_identity_block, strip_managed_block


def test_strip_managed_block_roundtrip(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ssh = tmp_path / ".ssh"
    ssh.mkdir(mode=0o700)
    (ssh / "id_ed25519").write_text("k", encoding="utf-8")
    cfg = ssh / "config"
    cfg.write_text("Host foo\n  HostName foo\n", encoding="utf-8")
    ok, msg = apply_identity_block("github.com", str(ssh / "id_ed25519"))
    assert ok
    body = cfg.read_text(encoding="utf-8")
    assert "deepiri-weft begin github.com" in body
    assert "IdentityFile" in body
    stripped = strip_managed_block(body, "github.com")
    assert "deepiri-weft" not in stripped
    assert "Host foo" in stripped
