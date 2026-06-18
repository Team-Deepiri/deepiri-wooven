# deepiri-git-handshake

TUI and CLI tool to **clone Git repos by owner/name**, pick **SSH or HTTPS** (with sensible defaults), and manage a small **credential vault**: per-host profiles, **HTTPS personal access tokens (PATs) in the OS keyring**, and a **`git-credential-dgh`** helper so plain `git` can authenticate over HTTPS without pasting tokens every time.

Licensed under **Apache-2.0** (see `LICENSE` and `NOTICE`).

## Requirements

- Python **3.10+**
- `git` on your `PATH`
- For HTTPS via PAT: a working **keyring** backend on your OS (most desktops have one; minimal Linux images may need extra packages—see [keyring](https://pypi.org/project/keyring/) docs).

## Install

One-line install (recommended):

```bash
git clone https://github.com/Team-Deepiri/deepiri-git-handshake.git
cd deepiri-git-handshake
./install.sh
source ~/.config/deepiri-git-handshake/path.sh
```

`./install.sh` creates a venv, installs the package, registers `git-credential-dgh`, installs a **git shim** on `~/.local/bin/git` (prepended via `path.sh`) that intercepts `git clone` and auto-picks **SSH or HTTPS**, and enables a **background service**:

| Platform | Service |
|----------|---------|
| Linux | systemd user unit `deepiri-git-handshake.service` |
| WSL | same systemd user unit |
| macOS | launchd agent `com.deepiri.git-handshake` |
| Windows | Scheduled task `DeepiriGitHandshake` at logon |

When you clone, transport is chosen from your saved profile, **last-used transport** for that host, or a **one-time prompt** if both SSH and HTTPS look available. Plain `git clone owner/repo` defaults to `github.com`.

Manual install:

```bash
cd deepiri-git-handshake
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
git-handshake service install
```

Entry points:

| Command | Purpose |
|--------|---------|
| `git-handshake` | TUI + `cred` + `service` subcommands |
| `dgh` | Same as `git-handshake` |
| `deepiri-git-handshake` | Same as `dgh` |
| `git-handshake-git` | Git shim (normally via `~/.local/bin/git`) |
| `git-credential-dgh` | Git credential helper (normally invoked by git, not by hand) |

Service management:

```bash
git-handshake service status
git-handshake service start
git-handshake service stop
git-handshake service uninstall
```

Check the version:

```bash
dgh --version
```

## TUI (`dgh`)

Run with no arguments:

```bash
dgh
```

Two tabs:

### Clone

1. Set **Forge host** (default `github.com`).
2. Choose **Transport**: *Auto* uses your saved **Vault** preference for that host when it is `ssh` or `https`; otherwise it probes the machine (SSH to `git@host`, then keys, then HTTPS).
3. Enter **Owner** (user or org) and **Repository** name.
4. **Target directory**: leave empty or `.` to clone into the **current directory** (must be empty).
5. **Setup credentials** — runs the same checks as the Vault “setup” flow for the current transport.
6. **Clone** — runs `git clone` and then a short credential pass.

### Vault (credential manager)

1. **Forge host** — same idea as on the Clone tab.
2. **Preferred transport** — stored in your profile (`auto` / `ssh` / `https`). Clone *Auto* respects `ssh` or `https` when set.
3. **SSH private key path** — optional; used for agent loading hints and for **Apply SSH config**.
4. **HTTPS username** — optional; default for git over HTTPS is often `git`; use your username if your host expects it.
5. **HTTPS PAT** — paste a token and click **Store PAT**; it is stored in the **OS keyring**, not in the project files.
6. **Register git helper** — adds `dgh` to `credential.helper` globally so `git` can call `git-credential-dgh` for HTTPS.
7. **Apply SSH config** — writes a **marked** `Host` block to `~/.ssh/config` for this host (re-running replaces only that managed block).
8. **Run setup pass** — SSH or HTTPS diagnostics (agent, probe, `gh`, PAT status).
9. **List all** — prints profiles, PAT presence, and current `credential.helper` values.

Quit the TUI with **q** or standard terminal exit.

## CLI (`dgh cred …`)

Non-interactive vault and setup commands:

```bash
# List profiles and git credential helpers
dgh cred list

# Summary for one host
dgh cred show --host github.com

# Merge-update a profile (only include flags you want to change)
dgh cred set --host github.com --transport ssh --ssh-identity ~/.ssh/id_ed25519
dgh cred set --host github.com --https-user myuser

# Store PAT from stdin (avoid putting the token in shell history)
printf '%s' "ghp_xxxxxxxx" | dgh cred pat --host github.com --store
dgh cred pat --host github.com --clear

# Register / unregister git-credential-dgh (helper name "dgh")
dgh cred helper
dgh cred helper --unregister

# Write managed ~/.ssh/config Host block
dgh cred ssh-config --host github.com --identity ~/.ssh/id_ed25519

# Run SSH or HTTPS setup messages (like the TUI)
dgh cred setup --host github.com --transport ssh
dgh cred setup --host github.com --transport https
```

## HTTPS flow (PAT + git)

1. Create a PAT on your forge (e.g. GitHub fine-grained or classic token).
2. `dgh cred set --host github.com --https-user YOUR_USERNAME` if needed.
3. Pipe the token into `dgh cred pat --host github.com --store`.
4. Run `dgh cred helper` so git’s global config includes `credential.helper = dgh`.
5. Clone or fetch over `https://…`; git invokes `git-credential-dgh`, which reads the PAT from the keyring.

If you use **GitHub CLI**, `gh auth login` plus `gh auth setup-git` remains a good alternative; this tool complements that for hosts or workflows where you want an explicit PAT in the vault.

## Where data is stored

| Data | Location |
|------|----------|
| Profiles (transport, paths, HTTPS username) | `$XDG_CONFIG_HOME/deepiri-git-handshake/profiles.json` (fallback: `~/.config/...`) |
| PATs | OS keyring under service `deepiri-git-handshake` |
| Managed SSH snippet | `~/.ssh/config` (between `deepiri-git-handshake begin/end` markers per host) |

## Troubleshooting

- **`NoKeyringError` when storing a PAT** — Your environment has no keyring backend (common on minimal Linux or some CI images). Install a backend (for example `keyrings.alt`, or your distro’s Secret Service / KWallet integration) per the [keyring documentation](https://pypi.org/project/keyring/).
- **`git-credential-dgh` not found** — Install the package so the `git-credential-dgh` script is on your `PATH`, or activate the same venv you used for `pip install -e .`.
- **WSL** — Use the same guidance as Linux; ensure a D-Bus secret service is available if you expect the freedesktop backend.

## Development

```bash
pip install -e '.[dev]'
pytest
```

Quick local check (imports + optional pytest):

```bash
./scripts/smoke.sh
```

## Unregistering the git helper

`dgh cred helper --unregister` removes the `dgh` helper by **rewriting** all global `credential.helper` entries: it unsets every value, then re-adds every helper **except** `dgh`. If you rely on a custom helper string, re-check `git config --global --get-all credential.helper` afterward.
