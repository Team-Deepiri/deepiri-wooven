"""git-credential helper protocol smoke test."""

from __future__ import annotations

import io
import sys
from unittest.mock import patch

from deepiri_weft.forge_credential_helper import run_git_credential


def test_get_emits_pat(monkeypatch: object) -> None:
    from deepiri_weft import cred_manager as cm

    cm.store_pat("github.com", "tok")
    cm.upsert_profile("github.com", https_username="u")
    stdin = io.StringIO("protocol=https\nhost=github.com\n\n")
    fake_out = io.StringIO()
    with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", fake_out):
        assert run_git_credential("get") == 0
    out = fake_out.getvalue()
    assert "password=tok" in out
    assert "username=u" in out
    cm.clear_pat("github.com")
