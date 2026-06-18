"""Parse git clone URLs into host, owner, repo, and transport."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class CloneTarget:
    host: str
    owner: str
    repo: str
    transport: str | None  # ssh, https, or None when unknown


_SCP_RE = re.compile(r"^git@([^:/]+)[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")
_HTTPS_RE = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def parse_clone_arg(arg: str) -> CloneTarget | None:
    """Parse a git clone source argument into structured parts."""
    raw = arg.strip().rstrip("/")
    if not raw:
        return None

    m = _SCP_RE.match(raw)
    if m:
        return CloneTarget(
            host=m.group(1).strip().lower(),
            owner=m.group("owner").strip(),
            repo=m.group("repo").strip().removesuffix(".git"),
            transport="ssh",
        )

    m = _HTTPS_RE.match(raw)
    if m:
        return CloneTarget(
            host=m.group("host").strip().lower(),
            owner=m.group("owner").strip(),
            repo=m.group("repo").strip().removesuffix(".git"),
            transport="https",
        )

    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) >= 2:
                return CloneTarget(
                    host=parsed.hostname.lower(),
                    owner=parts[0],
                    repo=parts[1].removesuffix(".git"),
                    transport="https",
                )
        return None

    if "/" in raw and "@" not in raw and ":" not in raw:
        owner, repo = raw.split("/", 1)
        owner = owner.strip()
        repo = repo.strip().removesuffix(".git")
        if owner and repo:
            return CloneTarget(
                host="github.com",
                owner=owner,
                repo=repo,
                transport=None,
            )

    return None
