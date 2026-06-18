"""Profile persistence tests (isolated config dir)."""

from __future__ import annotations

from pathlib import Path

import deepiri_weft.cred_manager as cm


def test_profiles_roundtrip(tmp_path: Path, monkeypatch: object) -> None:
    cfg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    cm.upsert_profile("github.com", transport="ssh", ssh_identity="/tmp/k")
    loaded = cm.load_profiles()
    assert "github.com" in loaded
    assert loaded["github.com"]["transport"] == "ssh"
    cm.store_pat("github.com", "fake-token")
    assert cm.get_pat("github.com") == "fake-token"
    cm.clear_pat("github.com")
    assert cm.get_pat("github.com") is None
    p = Path(cm.profiles_path())
    assert p.is_file()
    assert p.parent.name == "deepiri-weft"
