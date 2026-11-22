# pyinfra inventory.
#
# Auth goes through the ssh-agent (`ssh-add -l`). We deliberately do NOT let
# pyinfra read ~/.ssh/config: its `Host *` IdentityFile points at an encrypted
# key, which paramiko tries to load directly and then prompts for a passphrase
# (it can't use the macOS keychain like OpenSSH does).
#
# Addresses come from ops/.env (gitignored; see .env.example) as <HOST>_IP,
# with an optional <HOST>_PORT for non-22 SSH.
# Real environment variables override the file.
#
# repo_path: where this host's stacks live in the repo, relative to repo root.

import os
from pathlib import Path


def _load_env(path: Path) -> dict[str, str]:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip().removeprefix("export ").strip()] = value.strip().strip("'\"")
    return env | {k: v for k, v in os.environ.items() if k.endswith(("_IP", "_PORT")) or k == "SSH_USER"}


ENV = _load_env(Path(__file__).resolve().parent / ".env")


def _env(key: str) -> str:
    try:
        value = ENV[key]
    except KeyError:
        raise SystemExit(f"inventory: {key} not set in ops/.env (see .env.example)") from None
    if not value:
        raise SystemExit(f"inventory: {key} is empty in ops/.env")
    return value


SSH = {
    "ssh_user": _env("SSH_USER"),
    "ssh_config_file": "/dev/null",
    "ssh_allow_agent": True,
    "ssh_look_for_keys": False,
}


def _host(name: str, repo_path: str):
    data = {**SSH, "ssh_hostname": _env(f"{name.upper()}_IP"), "repo_path": repo_path}
    if port := ENV.get(f"{name.upper()}_PORT"):
        data["ssh_port"] = int(port)
    return (name, data)


vms = [
    _host("mon", "vms/mon"),
    _host("torrr", "vms/torrr"),
    # _host("ved", "vms/ved"),
    _host("dorp", "vms/dorp"),
    _host("nubuntu", "vms/nubuntu"),
    _host("gateway", "vms/gateway"),
    _host("joule", "vms/joule"),
]

pis = [
    _host("ralph", "vms/raspi/ralph"),
    _host("ronald", "vms/raspi/ronald"),
]

vps = [
    _host("racknerd", "vms/racknerd"),
]
