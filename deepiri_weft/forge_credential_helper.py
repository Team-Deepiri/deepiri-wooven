"""Git credential helper: git-credential-weft — reads HTTPS PAT from OS keyring."""

from __future__ import annotations

import sys

from deepiri_weft.cred_manager import get_pat, https_username_for


def _read_credential_input() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in sys.stdin.read().splitlines():
        line = line.strip()
        if not line:
            break
        if "=" in line:
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip()
    return data


def _emit(**pairs: str) -> None:
    for k, v in pairs.items():
        print(f"{k}={v}")


def run_git_credential(op: str) -> int:
    data = _read_credential_input()
    proto = data.get("protocol", "")
    host = (data.get("host") or "").strip().lower()
    if proto != "https" or not host:
        return 0

    if op == "get":
        token = get_pat(host)
        if not token:
            return 0
        user = https_username_for(host)
        _emit(username=user, password=token)
        return 0

    if op == "store":
        password = data.get("password", "").strip()
        username = data.get("username", "").strip()
        if password and host:
            from deepiri_weft.cred_manager import store_pat, upsert_profile

            store_pat(host, password)
            if username and username != "git":
                upsert_profile(host, https_username=username)
        return 0

    if op == "erase":
        from deepiri_weft.cred_manager import clear_pat

        clear_pat(host)
        return 0

    return 0


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(2)
    op = sys.argv[1]
    if op not in ("get", "store", "erase"):
        sys.exit(2)
    raise SystemExit(run_git_credential(op))


if __name__ == "__main__":
    main()
