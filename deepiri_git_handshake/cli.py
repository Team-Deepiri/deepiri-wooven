"""CLI entry for Deepiri Git Handshake."""

from __future__ import annotations

import argparse
import sys

from deepiri_git_handshake import __version__
from deepiri_git_handshake import cred_manager as cm
from deepiri_git_handshake import service as svc
from deepiri_git_handshake.credentials import manager_summary, setup_for_transport
from deepiri_git_handshake.ssh_config import apply_identity_block


def _cmd_cred_list(_: argparse.Namespace) -> int:
    profiles = cm.load_profiles()
    if not profiles and not cm.list_registered_helpers():
        print("(no profiles; git credential.helper not using dgh)")
        return 0
    for host in sorted(profiles):
        meta = profiles[host]
        print(f"{host}\t{meta}\tPAT:{cm.pat_status_line(host)}")
    print("git credential.helper:", ", ".join(cm.list_registered_helpers()) or "(none)")
    return 0


def _cmd_cred_show(args: argparse.Namespace) -> int:
    for line in manager_summary(args.host):
        print(line)
    return 0


def _cmd_cred_set(args: argparse.Namespace) -> int:
    kw: dict = {}
    if hasattr(args, "transport"):
        kw["transport"] = args.transport
    if hasattr(args, "ssh_identity"):
        kw["ssh_identity"] = args.ssh_identity
    if hasattr(args, "https_user"):
        kw["https_username"] = args.https_user
    cm.upsert_profile(args.host, **kw)
    print(f"Updated profile for {args.host.strip().lower()}")
    return 0


def _cmd_cred_pat(args: argparse.Namespace) -> int:
    host = args.host.strip().lower()
    if args.clear:
        ok = cm.clear_pat(host)
        print("Cleared PAT." if ok else "No PAT to clear.")
        return 0
    token = sys.stdin.read().strip()
    if not token:
        print("No token on stdin.", file=sys.stderr)
        return 1
    cm.store_pat(host, token)
    print(f"Stored PAT for {host} in OS keyring.")
    return 0


def _cmd_cred_helper(args: argparse.Namespace) -> int:
    if args.unregister:
        ok, msg = cm.unregister_git_credential_helper()
        print(msg)
        return 0 if ok else 1
    ok, msg = cm.register_git_credential_helper()
    print(msg)
    return 0 if ok else 1


def _cmd_cred_ssh_config(args: argparse.Namespace) -> int:
    ok, msg = apply_identity_block(args.host, args.identity)
    print(msg)
    return 0 if ok else 1


def _cmd_cred_setup(args: argparse.Namespace) -> int:
    for line in setup_for_transport(args.transport, args.host.strip().lower()):
        print(line)
    return 0


def _cmd_service_status(_: argparse.Namespace) -> int:
    for line in svc.service_status():
        print(line)
    return 0


def _cmd_service_start(args: argparse.Namespace) -> int:
    ok, msg = svc.start_service(foreground=args.foreground)
    print(msg)
    return 0 if ok else 1


def _cmd_service_stop(_: argparse.Namespace) -> int:
    ok, msg = svc.stop_service()
    print(msg)
    return 0 if ok else 1


def _cmd_service_install(args: argparse.Namespace) -> int:
    return svc.run_install(skip_service=args.skip_service)


def _cmd_service_uninstall(_: argparse.Namespace) -> int:
    svc.stop_service()
    ok, msg = svc.uninstall_platform_service()
    print(msg)
    return 0 if ok else 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deepiri Git Handshake — TUI clone + credential vault (dgh).",
    )
    p.add_argument("--version", action="store_true", help="Print version and exit")
    sub = p.add_subparsers(dest="command")

    cred = sub.add_parser("cred", help="Credential manager (profiles, PAT, git helper)")
    csub = cred.add_subparsers(dest="cred_action", required=True)

    c_list = csub.add_parser("list", help="List saved profiles and PAT status")
    c_list.set_defaults(func=_cmd_cred_list)

    c_show = csub.add_parser("show", help="Show vault summary for a host")
    c_show.add_argument("--host", required=True)
    c_show.set_defaults(func=_cmd_cred_show)

    c_set = csub.add_parser("set", help="Create or merge-update a host profile")
    c_set.add_argument("--host", required=True)
    c_set.add_argument(
        "--transport",
        choices=("auto", "ssh", "https"),
        default=argparse.SUPPRESS,
    )
    c_set.add_argument(
        "--ssh-identity",
        dest="ssh_identity",
        metavar="PATH",
        default=argparse.SUPPRESS,
    )
    c_set.add_argument(
        "--https-user",
        dest="https_user",
        metavar="USER",
        default=argparse.SUPPRESS,
    )
    c_set.set_defaults(func=_cmd_cred_set)

    c_pat = csub.add_parser(
        "pat",
        help="Store or clear HTTPS PAT in OS keyring (--store reads token from stdin)",
    )
    c_pat.add_argument("--host", required=True)
    g = c_pat.add_mutually_exclusive_group(required=True)
    g.add_argument("--store", action="store_true")
    g.add_argument("--clear", action="store_true")
    c_pat.set_defaults(func=_cmd_cred_pat)

    c_helper = csub.add_parser("helper", help="Register or unregister git-credential-dgh")
    c_helper.add_argument("--unregister", action="store_true")
    c_helper.set_defaults(func=_cmd_cred_helper)

    c_ssh = csub.add_parser("ssh-config", help="Write managed Host block to ~/.ssh/config")
    c_ssh.add_argument("--host", required=True)
    c_ssh.add_argument("--identity", required=True, metavar="PATH")
    c_ssh.set_defaults(func=_cmd_cred_ssh_config)

    c_setup = csub.add_parser("setup", help="Run setup pass for transport (like TUI)")
    c_setup.add_argument("--host", default="github.com")
    c_setup.add_argument("--transport", choices=("ssh", "https"), required=True)
    c_setup.set_defaults(func=_cmd_cred_setup)

    service = sub.add_parser("service", help="Background daemon and platform service")
    ssub = service.add_subparsers(dest="service_action", required=True)

    s_status = ssub.add_parser("status", help="Show daemon and install status")
    s_status.set_defaults(func=_cmd_service_status)

    s_start = ssub.add_parser("start", help="Start daemon (via platform service or foreground)")
    s_start.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Run daemon in foreground instead of platform service",
    )
    s_start.set_defaults(func=_cmd_service_start)

    s_stop = ssub.add_parser("stop", help="Stop running daemon")
    s_stop.set_defaults(func=_cmd_service_stop)

    s_install = ssub.add_parser("install", help="Install git shim, helper, and platform service")
    s_install.add_argument(
        "--skip-service",
        action="store_true",
        help="Install shim and helper only; do not register platform service",
    )
    s_install.set_defaults(func=_cmd_service_install)

    s_uninstall = ssub.add_parser("uninstall", help="Remove platform service")
    s_uninstall.set_defaults(func=_cmd_service_uninstall)

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.version:
        print(__version__)
        raise SystemExit(0)
    if args.command == "cred":
        raise SystemExit(args.func(args))
    if args.command == "service":
        raise SystemExit(args.func(args))
    from deepiri_git_handshake.tui import GitHandshakeApp

    GitHandshakeApp().run()


if __name__ == "__main__":
    main()
