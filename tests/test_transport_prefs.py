"""Tests for transport preference storage."""

from deepiri_git_handshake.transport_prefs import get_last_transport, record_transport


def test_record_and_read_last_transport(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    record_transport("github.com", "ssh")
    assert get_last_transport("github.com") == "ssh"
    record_transport("github.com", "https")
    assert get_last_transport("github.com") == "https"
