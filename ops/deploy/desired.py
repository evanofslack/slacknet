"""Desired state for a host: repo files at HEAD + secrets rendered with `op inject`.

Stacks are mapped to the dir they already run from on the host (from the latest
`ops/collect` snapshot), so nothing moves. A repo stack with no running compose
project is "not deployed"; a running project with no repo stack is "unmanaged".
"""

import atexit
import io
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import COMPOSE_NAMES, INV, REPO, hosts, op, parse_kv_lines, read_kv  # noqa: E402

SKIP_NAMES = {".gitignore", ".env.example"}
SKIP_SUFFIXES = (".md",)


@dataclass
class Stack:
    name: str
    repo_dir: str                      # e.g. vms/mon/grafana
    working_dir: str = ""              # on host; "" = not deployed
    relocate_from: str = ""            # running from a dir that no longer exists
    config_files: list[str] = field(default_factory=list)
    local: Path | None = None          # rendered desired tree
    files: dict[str, bool] = field(default_factory=dict)   # rel path -> is_secret
    op_keys: dict[str, set[str]] = field(default_factory=dict)  # rendered rel -> keys filled from 1Password
    secret_values: set[str] = field(default_factory=set)        # every value op inject filled in


def git(*args: str, binary: bool = False):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=not binary)
    if r.returncode:
        raise SystemExit(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout


def check_repo(allow_branch: bool = False) -> str:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != "main" and not allow_branch:
        raise SystemExit(f"on branch {branch!r}: deploys use main (pass --any-branch to override)")
    dirty = git("status", "--porcelain", "--", "vms").strip()
    if dirty:
        print("warning: vms/ has uncommitted changes; desired state is HEAD, they are ignored\n", file=sys.stderr)
    return git("rev-parse", "--short", "HEAD").strip()


def projects(host: str) -> dict[str, dict]:
    root = INV / host / "inv" / "projects"
    if not root.exists():
        raise SystemExit(f"no snapshot for {host}: run ops/collect --limit {host}")
    return {m.parent.name: read_kv(m) for m in root.glob("*/meta.txt")}


def repo_stacks(host: str) -> dict[str, str]:
    """project name (dir basename) -> repo dir, from HEAD."""
    rp = hosts()[host]["repo_path"]
    out = {}
    for path in git("ls-tree", "-r", "--name-only", "HEAD", "--", rp).splitlines():
        p = Path(path)
        if p.name in COMPOSE_NAMES:
            out[p.parent.name] = p.parent.as_posix()
    return out


def canonical_dir(host: str, repo_dir: str) -> str:
    """Where a stack lives on the host when it isn't pinned to an existing running dir."""
    return f"/home/{hosts()[host]['ssh_user']}/slacknet/{repo_dir}"


def plan(host: str) -> tuple[dict[str, Stack], list[str]]:
    """-> (stacks by name, unmanaged running project names)."""
    running = projects(host)
    stacks = {}
    for name, rd in sorted(repo_stacks(host).items()):
        s = Stack(name, rd)
        if name in running:
            meta = running[name]
            s.working_dir = meta.get("working_dir", "")
            s.config_files = [f for f in meta.get("config_files", "").split(",") if f]
            if meta.get("working_dir_missing"):
                # the dir it was started from is gone: deploy to the clone's canonical path
                s.relocate_from = s.working_dir
                s.working_dir = canonical_dir(host, rd)
                s.config_files = []
        stacks[name] = s
    unmanaged = sorted(set(running) - set(stacks))
    return stacks, unmanaged


def _scratch() -> Path:
    d = Path(tempfile.mkdtemp(prefix="slacknet-desired-"))
    d.chmod(0o700)
    atexit.register(shutil.rmtree, d, True)
    return d


REF = re.compile(r"\{\{\s*op://[^}]*\}\}")


def _filled_values(tpl: str, rendered: str) -> set[str]:
    """Values op inject put in place of each {{ op://... }}, matched line by line."""
    out = set()
    for t, r in zip(tpl.splitlines(), rendered.splitlines()):
        if "op://" not in t:
            continue
        pos, rx = 0, ""
        for m in REF.finditer(t):
            rx += re.escape(t[pos:m.start()]) + "(.+?)"
            pos = m.end()
        rx += re.escape(t[pos:])
        mm = re.fullmatch(rx, r)
        if mm:
            out |= {v for v in mm.groups() if len(v) >= 4}
    return out


def render(stack: Stack, scratch: Path | None = None) -> Stack:
    """Export the stack's HEAD files and render *.tpl into stack.local."""
    scratch = scratch or _scratch()
    raw = git("archive", "--format=tar", "HEAD", stack.repo_dir, binary=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        t.extractall(scratch, filter="data")
    local = scratch / stack.repo_dir
    stack.local = local
    for p in sorted(local.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(local).as_posix()
        if p.name in SKIP_NAMES or p.name.endswith(SKIP_SUFFIXES):
            p.unlink()
            continue
        if p.name.endswith(".tpl"):
            target = p.with_name(p.name[: -len(".tpl")])
            stack.op_keys[target.relative_to(local).as_posix()] = {
                k for k, v in parse_kv_lines(p.read_text()).items() if "op://" in v}
            tpl_text = p.read_text()
            op("inject", "-f", "-i", str(p), "-o", str(target))
            stack.secret_values |= _filled_values(tpl_text, target.read_text())
            target.chmod(0o600)
            p.unlink()
            stack.files[target.relative_to(local).as_posix()] = True
        else:
            stack.files[rel] = False
    return stack


def target_paths(host: str) -> list[str]:
    """Absolute host paths the repo would write, for every deployed stack (no rendering)."""
    stacks, _ = plan(host)
    out = []
    for s in stacks.values():
        if not s.working_dir:
            continue
        for path in git("ls-tree", "-r", "--name-only", "HEAD", "--", s.repo_dir).splitlines():
            rel = Path(path).relative_to(s.repo_dir)
            if rel.name in SKIP_NAMES or rel.name.endswith(SKIP_SUFFIXES):
                continue
            if rel.name.endswith(".tpl"):
                rel = rel.with_name(rel.name[: -len(".tpl")])
            out.append(f"{s.working_dir}/{rel.as_posix()}")
    return out


def load_hashes(host: str) -> dict[str, str] | None:
    """abs path -> sha256 from the last ops/diff hash check, or None if never run."""
    p = INV / host / "hashes.txt"
    if not p.exists():
        return None
    out = {}
    for line in p.read_text().splitlines():
        sha, _, path = line.partition("  ")
        if path:
            out[path] = sha
    return out
