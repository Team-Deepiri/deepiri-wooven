"""Tests for clone URL parsing."""

from deepiri_git_handshake.clone_parser import parse_clone_arg


def test_parse_ssh_scp():
    t = parse_clone_arg("git@github.com:octocat/Hello-World.git")
    assert t is not None
    assert t.host == "github.com"
    assert t.owner == "octocat"
    assert t.repo == "Hello-World"
    assert t.transport == "ssh"


def test_parse_https():
    t = parse_clone_arg("https://github.com/octocat/Hello-World")
    assert t is not None
    assert t.transport == "https"
    assert t.repo == "Hello-World"


def test_parse_shorthand():
    t = parse_clone_arg("octocat/Hello-World")
    assert t is not None
    assert t.host == "github.com"
    assert t.owner == "octocat"
    assert t.transport is None
