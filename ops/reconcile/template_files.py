"""Reconcile pass 1c: secrets in non-compose files -> 1Password templates.

Each entry names a file, the 1Password item, and regexes whose group(1) is the
secret value. The value goes into the item (created or extended), and is
replaced in the file by `{{ op://Homelab/<item>/<field> }}` (or `${FIELD}` for
compose files, with the field added to the stack's .env.tpl).

mode "tpl":     <file> -> <file>.tpl, and <file> is gitignored (rendered on deploy).
mode "inline":  replaced in place (docs/notes, never rendered).
mode "compose": replaced with ${FIELD}; .env.tpl gets FIELD={{ op://... }}.

    uv run --no-env-file python reconcile/template_files.py [--apply]
"""

import argparse
import re
import shutil
import tempfile
from pathlib import Path

from secrets import REPO, VAULT, Stack, create_item, existing_items, op, update_item  # noqa: F401

FILES = [
    ("vms/torrr/recyclarr/config/secrets.yml", "torrr-recyclarr", "tpl", {
        "SONARR_APIKEY": r"^sonarr_apikey:\s*(\S+)",
        "RADARR_APIKEY": r"^radarr_apikey:\s*(\S+)",
    }),
    ("vms/nubuntu/pve-exporter/config/pve.yaml", "nubuntu-pve-exporter", "tpl", {
        "PVE_PASSWORD": r"^\s*password:\s*(\S+)",
    }),
    ("vms/mon/grafana/docker-compose.yaml.auth", "mon-grafana", "compose", {
        "GF_AUTH_GENERIC_OAUTH_CLIENT_ID": r"GF_AUTH_GENERIC_OAUTH_CLIENT_ID:\s*\"?([^\"\s]+)\"?",
        "GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET": r"GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET:\s*\"?([^\"\s]+)\"?",
    }),
    # data migration stage 1 (2026-11-22): host-only configs pulled from the collect snapshot
    ("vms/mon/prometheus/config/prometheus.yaml", "mon-prometheus", "tpl", {
        "HASS_TOKEN": r"(?s)job_name: hass\b.*?credentials:\s*(\S+)",
        "MINIO_CLUSTER_TOKEN": r"(?s)job_name: minio-cluster\b.*?bearer_token:\s*(\S+)",
        "MINIO_BUCKET_TOKEN": r"(?s)job_name: minio-bucket\b.*?bearer_token:\s*(\S+)",
    }),
    # mon alertmanager: done by hand (Go {{ }} templates clash with op inject) ->
    # api_url_file: /config/slack_api_url, rendered from config/slack_api_url.tpl
    ("vms/mon/loki/config/loki.yaml", "mon-loki", "tpl", {
        "S3_ACCESS_KEY_ID": r"access_key_id:\s*(\S+)",
        "S3_SECRET_ACCESS_KEY": r"secret_access_key:\s*(\S+)",
    }),
    ("vms/mon/mimir/config/mimir.yaml", "mon-mimir", "tpl", {
        "S3_ACCESS_KEY_ID": r"access_key_id:\s*(\S+)",
        "S3_SECRET_ACCESS_KEY": r"secret_access_key:\s*(\S+)",
    }),
    ("vms/mon/tempo/config/tempo.yaml", "mon-tempo", "tpl", {
        "S3_ACCESS_KEY": r"access_key:\s*(\S+)",
        "S3_SECRET_KEY": r"secret_key:\s*(\S+)",
    }),
    ("vms/raspi/ralph/keepalived/data/keepalived.conf", "ralph-keepalived", "tpl", {
        "AUTH_PASS": r"auth_pass\s+(\S+)",
    }),
    ("vms/raspi/ronald/keepalived/data/keepalived.conf", "ronald-keepalived", "tpl", {
        "AUTH_PASS": r"auth_pass\s+(\S+)",
    }),
    ("vms/nubuntu/gitea/mirror-script.txt", "nubuntu-gitea", "inline", {
        "GITEA_TOKEN": r"GITEA_TOKEN=(\S+)",
    }),
]


def ref(item: str, key: str) -> str:
    return f"{{{{ op://{VAULT}/{item}/{key} }}}}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    have = existing_items()
    scratch = Path(tempfile.mkdtemp(prefix="slacknet-tpl-"))
    scratch.chmod(0o700)
    gitignore = REPO / ".gitignore"
    try:
        for rel, item, mode, patterns in FILES:
            path = REPO / rel
            if not path.exists():
                print(f"{rel}: missing (already converted?)")
                continue
            text = path.read_text()
            if "op://" in text and mode == "inline":
                print(f"{rel}: already templated")
                continue
            secrets = {}
            for key, pat in patterns.items():
                m = re.search(pat, text, re.M)
                if not m:
                    raise SystemExit(f"{rel}: pattern for {key} not found")
                if "{{" in m.group(1) or "op://" in m.group(1) or "${" in m.group(1):
                    raise SystemExit(f"{rel}: {key} is already a reference, not a secret")
                secrets[key] = m.group(1)
            new = text
            for key, value in secrets.items():
                repl = f"${{{key}}}" if mode == "compose" else ref(item, key)
                new = new.replace(value, repl)
            print(f"{rel:48} {mode:8} [{item}] {', '.join(secrets)}")
            if not a.apply:
                continue
            stack = Stack(dir=str(Path(rel).parent), compose_files=[], item=item, secrets=secrets)
            (update_item if item in have else create_item)(stack, scratch)
            have.add(item)
            # round-trip check: rendering the new text must give back the original
            if mode != "compose":
                rendered = op("inject", input=new)
                if rendered.rstrip("\n") != text.rstrip("\n"):
                    raise SystemExit(f"{rel}: rendered template differs from original; nothing written")
            if mode == "tpl":
                (path.parent / (path.name + ".tpl")).write_text(new)
                path.unlink()
                entry = f"/{rel}"
                if entry not in gitignore.read_text():
                    with gitignore.open("a") as f:
                        f.write(f"{entry}\n")
            elif mode == "inline":
                path.write_text(new)
            elif mode == "compose":
                path.write_text(new)
                tpl = path.parent / ".env.tpl"
                lines = tpl.read_text().splitlines() if tpl.exists() else []
                for key in secrets:
                    if not any(l.startswith(f"{key}=") for l in lines):
                        lines.append(f"{key}={ref(item, key)}")
                tpl.write_text("\n".join(lines) + "\n")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
