"""Shared helpers for ops tooling (deploy/, deploys/)."""

import re
import subprocess
import sys
from pathlib import Path

OPS = Path(__file__).resolve().parent
REPO = OPS.parent
INV = REPO / ".inventory"
COMPOSE_NAMES = ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml")

sys.path.insert(0, str(OPS))
import inventory  # noqa: E402

# Keys whose values are never shown, even in local diff output.
SECRET_KEY = re.compile(
    r"(PASS(WORD|WD)?|_PW$|SECRET|TOKEN|API_?KEY|APIKEY|PRIVATE|CREDENTIAL|(^|_)KEY$|HOOK_URL|WEBHOOK"
    r"|DSN|SALT|COOKIE|JWT|ENCRYPTION|ACCESS_KEY|AUTH_KEY|LICENSE_KEY|PSK)",
    re.I,
)


def hosts() -> dict[str, dict]:
    """name -> host data, from every host group in ops/inventory.py."""
    return {
        name: data
        for v in vars(inventory).values() if isinstance(v, list)
        for item in v if isinstance(item, tuple) and len(item) == 2
        for name, data in [item]
    }


def read_kv(p: Path) -> dict[str, str]:
    if not p.exists():
        return {}
    return dict(line.split("=", 1) for line in p.read_text().splitlines() if "=" in line)


def parse_kv_lines(text: str) -> dict[str, str]:
    """KEY=value (.env) or key: value (simple yaml) lines -> dict. Comments skipped."""
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^(?:export\s+)?([A-Za-z_][\w.-]*)\s*[=:]\s?(.*)$", s)
        if m:
            v = m.group(2).strip()
            if v and v[0] in "\"'" and v[0] in v[1:]:
                v = v[1:v.index(v[0], 1)]
            else:
                v = re.sub(r"\s+#.*$", "", v).strip()
            out[m.group(1)] = v
    return out


def op(*args: str, input: str | None = None) -> str:
    r = subprocess.run(["op", *args], input=input, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"op {' '.join(args[:2])}: {r.stderr.strip()}")
    return r.stdout


def compose_files(d: Path) -> list[str]:
    return [n for n in COMPOSE_NAMES if (d / n).exists()]


def compose_config(workdir: Path, files: list[str]) -> str:
    """Effective compose config (JSON) for a dir, or 'ERROR ...'."""
    args = ["docker", "compose", "-p", "diff"]
    for f in files:
        args += ["-f", f]
    r = subprocess.run(args + ["config", "--format", "json"], cwd=workdir, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else f"ERROR {r.stderr.strip()}"
