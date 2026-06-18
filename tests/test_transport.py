"""Smoke tests for transport helpers."""

from deepiri_weft.transport import clone_url


def test_clone_url_ssh():
    assert clone_url("github.com", "Team-Deepiri", "deepiri-weft", "ssh") == (
        "git@github.com:Team-Deepiri/deepiri-weft.git"
    )


def test_clone_url_https():
    u = clone_url("github.com", "a", "b", "https")
    assert u == "https://github.com/a/b.git"


def test_clone_url_strips_git_suffix():
    assert clone_url("github.com", "o", "r.git", "ssh") == "git@github.com:o/r.git"
