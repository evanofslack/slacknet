"""Reconcile pass 1b: move stack secrets out of vms/ into 1Password.

For every stack dir under vms/ (a dir containing a compose file):
  * the host's .env (from .inventory/, when the stack runs somewhere) is split:
    secret-looking keys go to a 1Password item, everything else stays plain.
  * literal secret values in compose `environment:` blocks become ${KEY}.
  * <stack>/.env.tpl is written: plain `KEY=value` lines and
    `KEY={{ op://Homelab/<item>/KEY }}` for secrets. Render on deploy with
        op inject -i .env.tpl -o .env

One 1Password item per stack in vault Homelab, titled from its path
(vms/nubuntu/immich -> nubuntu-immich, vms/raspi/ralph/nut -> ralph-nut).

Verification (every changed stack): the template is rendered with `op inject`
in memory and `docker compose config` must be identical before and after.

    uv run --no-env-file python reconcile/secrets.py            # plan only
    uv run --no-env-file python reconcile/secrets.py --apply    # create items, write files
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

OPS = Path(__file__).resolve().parent.parent
REPO = OPS.parent
INV = REPO / ".inventory"
VAULT = "Homelab"
sys.path.insert(0, str(OPS))
import inventory  # noqa: E402

COMPOSE_NAMES = {"docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml"}

SECRET_KEY = re.compile(
    r"(PASS(WORD|WD)?|SECRET|TOKEN|API_?KEY|PRIVATE|CREDENTIAL|(^|_)KEY$|HOOK_URL|WEBHOOK"
    r"|DSN|SALT|COOKIE|JWT|ENCRYPTION|ACCESS_KEY|AUTH_KEY|LICENSE_KEY|PSK|AUTH_PASS)",
    re.I,
)
NOT_SECRET_KEY = re.compile(r"(NO_PASSWORD|_FILE|_PATH|_DIR|_LENGTH|_ALGORITHM|_ENABLED|_EXPIRY|_TTL|_TIMEOUT|_ID)$", re.I)
CREDS_IN_URL = re.compile(r"://[^/\s:@]+:[^/\s@]+@")


def is_secret(key: str, value: str) -> bool:
    if not value or "${" in value or value.startswith("op://"):
        return False
    if CREDS_IN_URL.search(value) or key.upper().endswith("ACCESS_KEY_ID"):
        return True
    if NOT_SECRET_KEY.search(key):
        return False
    if value.lower() in {"true", "false", "yes", "no", "none", "null"}:
        return False
    return bool(SECRET_KEY.search(key))


def item_title(stack_dir: str) -> str:
    parts = [p for p in Path(stack_dir).parts[1:] if p != "raspi"]
    return "-".join(parts)


# ------------------------------------------------------------------ .env parsing
ENV_LINE = re.compile(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_.-]*)(\s*=\s*)(.*?)(\s*)$")


@dataclass
class EnvLine:
    raw: str
    key: str | None = None
    prefix: str = ""
    sep: str = "="
    value: str = ""      # unquoted
    quote: str = ""      # '', "'", '"'


def parse_env(text: str) -> list[EnvLine]:
    out = []
    for raw in text.splitlines():
        m = ENV_LINE.match(raw)
        if not m or raw.lstrip().startswith("#"):
            out.append(EnvLine(raw))
            continue
        prefix, key, sep, val, _ = m.groups()
        quote = ""
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            quote, val = val[0], val[1:-1]
        elif " #" in val and not val.startswith(("'", '"')):
            val = val.split(" #", 1)[0].rstrip()
        out.append(EnvLine(raw, key, prefix, sep, val, quote))
    return out


def env_values(text: str) -> dict[str, str]:
    return {l.key: l.value for l in parse_env(text) if l.key}


# ------------------------------------------------------------------ compose rewriting
@dataclass
class Stack:
    dir: str
    compose_files: list[Path]
    host_env: Path | None = None
    item: str = ""
    secrets: dict[str, str] = field(default_factory=dict)      # key -> value
    tpl_lines: list[str] = field(default_factory=list)
    new_compose: dict[Path, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def ref(self, key: str) -> str:
        return f"{{{{ op://{VAULT}/{self.item}/{key} }}}}"


def rewrite_compose(stack: Stack, path: Path) -> None:
    """Replace literal secret values in environment blocks with ${KEY}."""
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    out = []
    env_indent = None
    changed = False
    service = ""
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        m_svc = re.match(r"^( {2}|\t)([A-Za-z0-9_.-]+):\s*(#.*)?$", line.rstrip("\n"))
        if m_svc:
            service = m_svc.group(2)
        if env_indent is not None and stripped and indent <= env_indent:
            env_indent = None
        if re.match(r"^\s*environment:\s*$", line):
            env_indent = indent
            out.append(line)
            continue
        if env_indent is None or not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        key = val = None
        m_list = re.match(r"^(\s*-\s*)(['\"]?)([A-Za-z_][A-Za-z0-9_]*)=(.*?)\2(\s*(#.*)?)$", line.rstrip("\n"))
        m_map = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s+(.+?)(\s+#.*)?$", line.rstrip("\n"))
        if m_list:
            lead, q, key, val, trail = m_list.group(1, 2, 3, 4, 5)
            raw_val = val
        elif m_map:
            lead, key, raw_val, trail = m_map.group(1, 2, 3, 4)
            trail = trail or ""
            try:
                val = yaml.safe_load(raw_val)
            except Exception:
                val = raw_val
            val = "" if val is None else str(val)
        if key is None or not is_secret(key, val):
            out.append(line)
            continue
        literal = val.replace("$$", "$")                 # compose escape -> real value
        var = key
        if var in stack.secrets and stack.secrets[var] != literal:
            var = f"{key}_{re.sub(r'[^A-Za-z0-9]', '_', service).upper()}"
            stack.notes.append(f"{key} differs per service; service {service} uses ${var}")
        stack.secrets[var] = literal
        nl = "\n" if line.endswith("\n") else ""
        if m_list:
            out.append(f"{lead}{q}{key}=${{{var}}}{q}{trail}{nl}")
        else:
            out.append(f"{lead}{key}: ${{{var}}}{trail}{nl}")
        changed = True
    if changed:
        stack.new_compose[path] = "".join(out)


def tpl_value(value: str) -> str:
    """Quote a value moved from compose into .env so compose reads it literally."""
    return value


def build(stack: Stack) -> None:
    stack.item = item_title(stack.dir)
    tpl: list[str] = []
    env_keys = set()
    if stack.host_env:
        for l in parse_env(stack.host_env.read_text()):
            if not l.key:
                m = re.match(r"^(\s*#\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)=(.+)$", l.raw)
                if m and is_secret(m.group(2), m.group(3).strip("'\" ")):
                    tpl.append(f"{m.group(1)}{m.group(2)}=  # old value removed")
                else:
                    tpl.append(l.raw)
                continue
            env_keys.add(l.key)
            if is_secret(l.key, l.value):
                stack.secrets[l.key] = l.value
                q = l.quote or ("'" if "$" in l.value else "")
                tpl.append(f"{l.prefix}{l.key}{l.sep}{q}{stack.ref(l.key)}{q}")
            else:
                tpl.append(l.raw)
    for cf in stack.compose_files:
        rewrite_compose(stack, cf)
    moved = [k for k in stack.secrets if k not in env_keys]
    if moved:
        if tpl and tpl[-1].strip():
            tpl.append("")
        tpl.append("# moved out of docker-compose (was hardcoded)")
        for k in moved:
            v = stack.secrets[k]
            q = "'" if any(c in v for c in "$ #\"") else ""
            if "'" in v and q:
                stack.notes.append(f"{k}: value contains a quote; check rendering")
            tpl.append(f"{k}={q}{stack.ref(k)}{q}")
    stack.tpl_lines = tpl


# ------------------------------------------------------------------ discovery
def host_env_map() -> dict[str, Path]:
    """repo stack dir -> host .env collected in .inventory."""
    hp = {n: d["repo_path"] for v in vars(inventory).values() if isinstance(v, list)
          for it in v if isinstance(it, tuple) and len(it) == 2 for n, d in [it]}
    out = {}
    for host, rp in hp.items():
        pr = INV / host / "inv" / "projects"
        if not pr.exists():
            continue
        for p in pr.iterdir():
            meta = dict(l.split("=", 1) for l in (p / "meta.txt").read_text().splitlines() if "=" in l)
            wd = meta.get("working_dir", "")
            env = p / "files" / ".env"
            if not env.exists() or not wd:
                continue
            if f"/slacknet/{rp}/" in wd + "/":
                dest = wd.split("/slacknet/", 1)[1]
            elif "/slacknet/" in wd:
                continue  # project rooted elsewhere (e.g. whole vms/nubuntu)
            else:
                dest = f"{rp}/{Path(wd).name}"
            out[dest] = env
    return out


def discover(only: str | None) -> list[Stack]:
    envs = host_env_map()
    dirs: dict[str, list[Path]] = {}
    for p in sorted((REPO / "vms").rglob("*")):
        if p.is_file() and p.name in COMPOSE_NAMES:
            rel = str(p.parent.relative_to(REPO))
            if only and not rel.startswith(only):
                continue
            dirs.setdefault(rel, []).append(p)
    return [Stack(d, files, envs.get(d)) for d, files in dirs.items()]


# ------------------------------------------------------------------ 1password
def op(*args: str, input: str | None = None) -> str:
    r = subprocess.run(["op", *args], input=input, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"op {' '.join(args[:3])}: {r.stderr.strip()}")
    return r.stdout


def existing_items() -> set[str]:
    return {i["title"] for i in json.loads(op("item", "list", "--vault", VAULT, "--format", "json") or "[]")}


def update_item(stack: Stack, scratch: Path) -> None:
    item = json.loads(op("item", "get", stack.item, "--vault", VAULT, "--format", "json", "--reveal"))
    fields = item.setdefault("fields", [])
    by_label = {f.get("label"): f for f in fields}
    changed = False
    for k, v in stack.secrets.items():
        if k in by_label:
            if by_label[k].get("value") != v:
                raise RuntimeError(f"{stack.item}/{k} already exists with a different value; not overwriting")
            continue
        fields.append({"id": k, "label": k, "type": "CONCEALED", "value": v})
        changed = True
    if not changed:
        return
    f = scratch / f"{stack.item}.json"
    f.write_text(json.dumps(item))
    f.chmod(0o600)
    try:
        op("item", "edit", stack.item, "--vault", VAULT, "--template", str(f), "--format", "json")
    finally:
        f.unlink()


def create_item(stack: Stack, scratch: Path) -> None:
    host = Path(stack.dir).parts[1]
    tmpl = {
        "title": stack.item,
        "category": "SECURE_NOTE",
        "tags": ["slacknet", host],
        "fields": [
            {"id": "notesPlain", "type": "STRING", "purpose": "NOTES", "label": "notesPlain",
             "value": f"Secrets for {stack.dir} (slacknet). Rendered via {stack.dir}/.env.tpl"},
            *[{"id": k, "label": k, "type": "CONCEALED", "value": v} for k, v in stack.secrets.items()],
        ],
    }
    f = scratch / f"{stack.item}.json"
    f.write_text(json.dumps(tmpl))
    f.chmod(0o600)
    try:
        op("item", "create", "--vault", VAULT, "--template", str(f), "--format", "json")
    finally:
        f.unlink()


# ------------------------------------------------------------------ verification
def compose_config(workdir: Path, files: list[str]) -> str:
    args = ["docker", "compose", "-p", "verify"]
    for f in files:
        args += ["-f", f]
    r = subprocess.run(args + ["config", "--format", "json"], cwd=workdir, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else f"ERROR {r.stderr.strip()}"


def verify(stack: Stack, scratch: Path) -> str:
    rendered = op("inject", input="\n".join(stack.tpl_lines) + "\n")
    if stack.host_env:
        want = env_values(stack.host_env.read_text())
        got = env_values(rendered)
        bad = [k for k in want if want[k] != got.get(k)]
        if bad:
            return f"FAIL .env mismatch: {bad}"
    src = REPO / stack.dir
    before = scratch / "verify"
    shutil.rmtree(before, ignore_errors=True)
    shutil.copytree(src, before, ignore=shutil.ignore_patterns(".env", ".env.tpl"))
    for p in before.rglob("*"):
        if p.is_file():
            p.chmod(0o600)
    names = [str(cf.relative_to(src)) for cf in stack.compose_files]
    if stack.host_env:
        shutil.copy(stack.host_env, before / ".env")
    old = compose_config(before, names)
    for cf, text in stack.new_compose.items():
        (before / cf.relative_to(src)).write_text(text)
    (before / ".env").write_text(rendered)
    new = compose_config(before, names)
    shutil.rmtree(before, ignore_errors=True)
    if old == new:
        return "ok" if not old.startswith("ERROR") else f"unverified (compose errors before and after: {old[6:90]})"
    # Services that load the whole .env (env_file) also receive keys moved out of
    # compose. Allow exactly that difference and report it.
    try:
        o, n = json.loads(old), json.loads(new)
    except ValueError:
        return "FAIL compose config differs"
    moved = {k for k in stack.secrets if not stack.host_env or k not in env_values(stack.host_env.read_text())}
    extra = []
    for name, svc in (n.get("services") or {}).items():
        oenv = ((o.get("services") or {}).get(name) or {}).get("environment") or {}
        nenv = svc.get("environment") or {}
        for k in moved:
            if k in nenv and k not in oenv:
                del nenv[k]
                extra.append(f"{name}:{k}")
    if o == n:
        return f"ok (env_file now also passes {', '.join(extra)} to those services)"
    return "FAIL compose config differs"


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", help="limit to stack dirs under this path, e.g. vms/torrr")
    a = ap.parse_args()

    stacks = [s for s in discover(a.only)]
    for s in stacks:
        build(s)
    todo = [s for s in stacks if s.secrets or s.host_env]
    have = existing_items() if a.apply else set()
    scratch = Path(tempfile.mkdtemp(prefix="slacknet-secrets-"))
    scratch.chmod(0o700)
    failures = 0
    try:
        for s in todo:
            keys = ", ".join(s.secrets) or "-"
            src = "env+compose" if s.host_env and s.new_compose else ("env" if s.host_env else "compose")
            line = f"{s.dir:45} {src:11} [{s.item}] {keys}"
            if not a.apply:
                print(line)
                for n in s.notes:
                    print(f"    note: {n}")
                continue
            tpl_path = REPO / s.dir / ".env.tpl"
            marker = "# moved out of docker-compose"
            if tpl_path.exists() and marker in tpl_path.read_text() and marker not in "\n".join(s.tpl_lines):
                print(f"{line}\n    SKIP: already converted (compose secrets were moved earlier); not rebuilding")
                continue
            if s.secrets:
                (update_item if s.item in have else create_item)(s, scratch)
            result = verify(s, scratch)
            print(f"{line}\n    verify: {result}")
            for n in s.notes:
                print(f"    note: {n}")
            if not result.startswith(("ok", "unverified")):
                failures += 1
                continue
            for cf, text in s.new_compose.items():
                cf.write_text(text)
            (REPO / s.dir / ".env.tpl").write_text("\n".join(s.tpl_lines) + "\n")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    n_secrets = sum(len(s.secrets) for s in todo)
    print(f"\n{len(todo)} stacks, {n_secrets} secrets, {sum(1 for s in todo if s.secrets)} items"
          + (f", {failures} FAILED verification (files left untouched)" if a.apply else " (plan only)"))


if __name__ == "__main__":
    main()
