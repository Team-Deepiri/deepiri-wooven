"""Textual TUI for Deepiri Weft."""

from __future__ import annotations

import subprocess
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from deepiri_weft import cred_manager as cm
from deepiri_weft.credentials import manager_summary, setup_for_transport
from deepiri_weft.ssh_config import apply_identity_block
from deepiri_weft.transport import clone_url, detect_transport


def _normalize_target(raw: str) -> str:
    s = raw.strip()
    if not s or s == ".":
        return "."
    return str(Path(s).expanduser())


class WeftApp(App[None]):
    CSS = """
    Screen { align: center middle; }
    TabbedContent { width: 92; max-width: 100%; height: auto; min-height: 28; }
    TabbedContent #clone-tab, TabbedContent #vault-tab { padding: 1 1; }
    #main-clone { width: 100%; height: auto; border: heavy $primary; padding: 1 2; }
    #main-vault { width: 100%; height: auto; border: heavy $accent; padding: 1 2; }
    #fields-clone Input, #fields-vault Input { margin-bottom: 1; }
    #log-clone, #log-vault { height: 10; min-height: 6; border: round $boost; margin-top: 1; }
    #hint-clone, #hint-vault { margin-top: 1; color: $text-muted; }
    #actions-clone, #actions-vault { margin-top: 1; height: auto; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="clone-tab"):
            with TabPane("Clone", id="clone-tab"):
                with Container(id="main-clone"):
                    yield Static("[b]Clone[/b] — owner, repo, directory", id="title-clone")
                    with Vertical(id="fields-clone"):
                        yield Label("Forge host")
                        yield Input(placeholder="github.com", id="host", value="github.com")
                        yield Label("Transport")
                        yield Select(
                            (
                                ("Auto (detect + profile)", "auto"),
                                ("SSH (git@host:…)", "ssh"),
                                ("HTTPS", "https"),
                            ),
                            id="transport",
                            allow_blank=False,
                            value="auto",
                        )
                        yield Label("Owner (user or organization)")
                        yield Input(placeholder="octocat", id="owner")
                        yield Label("Repository name")
                        yield Input(placeholder="Hello-World", id="repo")
                        yield Label("Target directory (empty or . = current directory)")
                        yield Input(placeholder=".", id="target")
                    yield Static(
                        "Auto uses saved Vault preference for this host when set, else machine probe.",
                        id="hint-clone",
                    )
                    yield RichLog(id="log-clone", highlight=True, markup=True)
                    with Horizontal(id="actions-clone"):
                        yield Button("Clone", variant="primary", id="clone_btn")
                        yield Button("Setup credentials", id="cred_btn")
                        yield Button("Detect transport now", id="detect_btn")
            with TabPane("Vault", id="vault-tab"):
                with Container(id="main-vault"):
                    yield Static("[b]Credential vault[/b] — profiles, PAT, git helper, SSH config", id="title-vault")
                    with Vertical(id="fields-vault"):
                        yield Label("Forge host")
                        yield Input(placeholder="github.com", id="vault_host", value="github.com")
                        yield Label("Preferred transport (saved to profile)")
                        yield Select(
                            (
                                ("auto", "auto"),
                                ("ssh", "ssh"),
                                ("https", "https"),
                            ),
                            id="vault_transport",
                            allow_blank=False,
                            value="auto",
                        )
                        yield Label("SSH private key path (optional)")
                        yield Input(placeholder="~/.ssh/id_ed25519", id="vault_ssh_identity")
                        yield Label("HTTPS username (optional; default git)")
                        yield Input(placeholder="git", id="vault_https_user")
                        yield Label("HTTPS PAT (stored in OS keyring; not echoed)")
                        yield Input(placeholder="paste token, then Store PAT", id="vault_pat", password=True)
                    yield Static(
                        "Register `git-credential-weft` so git can read PATs from the keyring for HTTPS.",
                        id="hint-vault",
                    )
                    yield RichLog(id="log-vault", highlight=True, markup=True)
                    with Horizontal(id="actions-vault"):
                        yield Button("Save profile", id="vault_save_profile", variant="primary")
                        yield Button("Store PAT", id="vault_store_pat")
                        yield Button("Clear PAT", id="vault_clear_pat")
                        yield Button("Register git helper", id="vault_reg_helper")
                        yield Button("Apply SSH config", id="vault_ssh_cfg")
                        yield Button("Run setup pass", id="vault_setup")
                        yield Button("List all", id="vault_list")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log-clone", RichLog)
        log.write("[dim]Clone tab: run Setup credentials or use the Vault tab.[/]")
        self.query_one("#log-vault", RichLog).write("[dim]Vault: save a profile and optional PAT.[/]")

    def action_quit(self) -> None:
        self.exit()

    def _host_clone(self) -> str:
        return self.query_one("#host", Input).value.strip() or "github.com"

    def _host_vault(self) -> str:
        return self.query_one("#vault_host", Input).value.strip() or "github.com"

    def _resolved_transport(self, host: str, select_id: str = "#transport") -> str:
        sel = self.query_one(select_id, Select).value
        if sel != "auto":
            assert isinstance(sel, str)
            return sel
        meta = cm.get_profile(host.strip().lower())
        pref = meta.get("transport")
        if pref in ("ssh", "https"):
            return pref
        return detect_transport(host)

    @on(Button.Pressed, "#detect_btn")
    def detect_now(self) -> None:
        host = self._host_clone()
        chosen = detect_transport(host)
        sel = self.query_one("#transport", Select)
        sel.value = "ssh" if chosen == "ssh" else "https"
        log = self.query_one("#log-clone", RichLog)
        log.write(f"[cyan]Detected machine transport:[/] [b]{chosen}[/] (for {host})")

    @on(Button.Pressed, "#cred_btn")
    def run_credentials(self) -> None:
        log = self.query_one("#log-clone", RichLog)
        host = self._host_clone()
        transport = self._resolved_transport(host)
        log.write(f"[yellow]Credential setup[/] ({transport.upper()} @ {host})")
        for line in setup_for_transport(transport, host):
            log.write(line)
        for line in manager_summary(host):
            log.write(line)
        log.write("[dim]Credential pass complete.[/]")

    @on(Button.Pressed, "#clone_btn")
    def run_clone(self) -> None:
        log = self.query_one("#log-clone", RichLog)
        host = self._host_clone()
        owner = self.query_one("#owner", Input).value.strip()
        repo = self.query_one("#repo", Input).value.strip()
        target = _normalize_target(self.query_one("#target", Input).value)

        if not owner or not repo:
            log.write("[red]Owner and repository name are required.[/]")
            self.bell()
            return

        transport = self._resolved_transport(host)
        url = clone_url(host, owner, repo, transport)
        log.write(f"[green]Using[/] {transport.upper()} [dim]{url}[/]")

        if target == ".":
            try:
                if any(Path(".").iterdir()):
                    log.write(
                        "[red]Current directory is not empty. "
                        "Use an empty folder or a new subdirectory name.[/]"
                    )
                    self.bell()
                    return
            except OSError as e:
                log.write(f"[red]Cannot read current directory: {e}[/]")
                return

        try:
            proc = subprocess.run(
                ["git", "clone", url, target],
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            log.write("[red]git not found on PATH.[/]")
            self.bell()
            return
        except subprocess.TimeoutExpired:
            log.write("[red]git clone timed out.[/]")
            self.bell()
            return

        if proc.stdout:
            log.write(proc.stdout.rstrip())
        if proc.stderr:
            log.write(proc.stderr.rstrip())
        if proc.returncode == 0:
            log.write(f"[bold green]Done.[/] Cloned into [cyan]{target}[/]")
            log.write("[yellow]Running credential helper pass for this transport…[/]")
            for line in setup_for_transport(transport, host):
                log.write(line)
            self._post_success_tips(log, transport)
        else:
            log.write(f"[red]git clone failed (exit {proc.returncode}).[/]")
            self.bell()

    def _post_success_tips(self, log: RichLog, transport: str) -> None:
        if transport == "https":
            log.write(
                "[dim]HTTPS: register git-credential-weft in Vault, or use `gh auth setup-git`.[/]"
            )
        else:
            log.write(
                "[dim]SSH: add your public key on the forge; `ssh -T git@github.com` to verify.[/]"
            )

    @on(Button.Pressed, "#vault_save_profile")
    def vault_save_profile(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        host = self._host_vault()
        vt = self.query_one("#vault_transport", Select).value
        assert isinstance(vt, str)
        ident = self.query_one("#vault_ssh_identity", Input).value.strip()
        hu = self.query_one("#vault_https_user", Input).value.strip()
        cm.upsert_profile(
            host,
            transport=vt,
            ssh_identity=ident,
            https_username=hu,
        )
        log.write(f"[green]Saved profile[/] for [cyan]{host}[/]")

    @on(Button.Pressed, "#vault_store_pat")
    def vault_store_pat(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        host = self._host_vault()
        token = self.query_one("#vault_pat", Input).value.strip()
        if not token:
            log.write("[red]Paste a PAT first.[/]")
            self.bell()
            return
        cm.store_pat(host, token)
        self.query_one("#vault_pat", Input).value = ""
        log.write(f"[green]Stored PAT[/] for [cyan]{host}[/] in OS keyring.")

    @on(Button.Pressed, "#vault_clear_pat")
    def vault_clear_pat(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        host = self._host_vault()
        ok = cm.clear_pat(host)
        log.write("[green]Cleared PAT.[/]" if ok else "[yellow]No PAT to clear.[/]")

    @on(Button.Pressed, "#vault_reg_helper")
    def vault_reg_helper(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        ok, msg = cm.register_git_credential_helper()
        log.write(msg if ok else f"[red]{msg}[/]")

    @on(Button.Pressed, "#vault_ssh_cfg")
    def vault_ssh_cfg(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        host = self._host_vault()
        ident = self.query_one("#vault_ssh_identity", Input).value.strip()
        if not ident:
            log.write("[red]Set SSH private key path first.[/]")
            self.bell()
            return
        ok, msg = apply_identity_block(host, ident)
        log.write(msg if ok else f"[red]{msg}[/]")

    @on(Button.Pressed, "#vault_setup")
    def vault_setup(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        host = self._host_vault()
        vt = self.query_one("#vault_transport", Select).value
        assert isinstance(vt, str)
        t = vt if vt in ("ssh", "https") else self._resolved_transport(host, "#vault_transport")
        log.write(f"[yellow]Setup[/] {t.upper()} @ {host}")
        for line in setup_for_transport(t, host):
            log.write(line)
        for line in manager_summary(host):
            log.write(line)

    @on(Button.Pressed, "#vault_list")
    def vault_list(self) -> None:
        log = self.query_one("#log-vault", RichLog)
        profiles = cm.load_profiles()
        if not profiles:
            log.write("[dim]No profiles saved.[/]")
        for h in sorted(profiles):
            log.write(f"[cyan]{h}[/] {profiles[h]} PAT:{cm.pat_status_line(h)}")
        log.write(f"git credential.helper: {', '.join(cm.list_registered_helpers()) or '(none)'}")
