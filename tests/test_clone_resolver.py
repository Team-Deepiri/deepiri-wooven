"""Tests for clone transport resolution."""

from deepiri_git_handshake.clone_resolver import resolve_clone_url


def test_resolve_explicit_https(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    url, transport = resolve_clone_url(
        "https://github.com/octocat/Hello-World.git",
        interactive=False,
    )
    assert transport == "https"
    assert url == "https://github.com/octocat/Hello-World.git"


def test_resolve_shorthand_uses_detect(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(
        "deepiri_git_handshake.clone_resolver.detect_transport",
        lambda _host: "https",
    )
    url, transport = resolve_clone_url("octocat/Hello-World", interactive=False)
    assert transport == "https"
    assert url == "https://github.com/octocat/Hello-World.git"
