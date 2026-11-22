"""Diff a host's running stacks against the repo (read-only; uses the ops/collect snapshot).

    uv run --no-env-file python deploy/diff_host.py <host> [--stack a,b] [--any-branch]

Secret files (.env, rendered *.tpl) are compared by key only; values are never
printed. Values of secret-looking keys are masked in every other diff too.
Output is printed and saved to .inventory/<host>/diff.txt.
"""

import argparse
import difflib
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import INV, SECRET_KEY, compose_config, parse_kv_lines  # noqa: E402
from deploy.desired import Stack, canonical_dir, check_repo, load_hashes, plan, render  # noqa: E402

SECRET_LINE = re.compile(r"^([+\- ]?\s*-?\s*\"?)([A-Za-z_][\w.-]*)(\"?\s*[:=]\s*)(.+)$")
NOISE = re.compile(r"(\.bak$|\.bak/|\.old$|\.orig$|\.log$|\.pid$|~$|\.swp$)")


class Masker:
    def __init__(self):
        self.values: set[str] = set()

    def learn(self, kv: dict[str, str], force: set[str] = frozenset()) -> None:
        """Mask values of secret-looking keys, and of every key filled from 1Password."""
        for k, v in kv.items():
            if (k in force or SECRET_KEY.search(k)) and len(v) >= 4 and "${" not in v and "op://" not in v:
                self.values.add(v)

    def __call__(self, line: str) -> str:
        for v in sorted(self.values, key=len, reverse=True):
            line = line.replace(v, "***")
        m = SECRET_LINE.match(line)
        if m and SECRET_KEY.search(m.group(2)) and not m.group(4).startswith(("${", "***", "{{")):
            line = f"{m.group(1)}{m.group(2)}{m.group(3)}***"
        return line


def kv_diff(host_text: str | None, want_text: str) -> list[str]:
    have = parse_kv_lines(host_text or "")
    want = parse_kv_lines(want_text)
    out = []
    for k in sorted(set(have) | set(want)):
        if k not in have:
            out.append(f"+ {k}")
        elif k not in want:
            out.append(f"- {k}   (on host only; removed on apply)")
        elif have[k] != want[k]:
            out.append(f"~ {k}   (value differs)")
    return out


def host_tree(snap: Path) -> dict[str, str]:
    """rel path -> size, from tree.txt (maxdepth 2, includes uncaptured files)."""
    t = snap / "tree.txt"
    out = {}
    if t.exists():
        for line in t.read_text().splitlines():
            parts = line.split(None, 2)
            if len(parts) == 3 and parts[0] == "f":
                out[parts[2]] = parts[1]
    return out


def effective(stack: Stack, snap_files: Path, mask: Masker) -> list[str]:
    """docker compose config of host copy vs desired, at the same temp path."""
    files = [Path(f).name for f in stack.config_files] or None
    with tempfile.TemporaryDirectory(prefix="slacknet-cfg-") as td:
        work = Path(td) / stack.name
        res = {}
        for label, src in (("host", snap_files), ("repo", stack.local)):
            shutil.copytree(src, work)
            names = files or [n for n in ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml")
                              if (work / n).exists()]
            raw = compose_config(work, names)
            raw = raw.replace(str(work), stack.working_dir)
            if not raw.startswith("ERROR"):
                raw = json.dumps(json.loads(raw), indent=2, sort_keys=True)
            res[label] = raw
            shutil.rmtree(work)
    if res["host"] == res["repo"]:
        return []
    if res["repo"].startswith("ERROR"):
        return [f"  !! repo config does not render: {mask(res['repo'][6:300])}"]
    if res["host"].startswith("ERROR"):
        return [f"  (host config does not render in snapshot: {mask(res['host'][6:200])})"]
    d = difflib.unified_diff(res["host"].splitlines(), res["repo"].splitlines(), "host", "repo", n=1, lineterm="")
    return ["  " + mask(l) for l in list(d)[2:]]


def running_env(host: str) -> dict[tuple[str, str], dict[str, str]]:
    """(project, service) -> env of the running container, from the snapshot's docker inspect."""
    p = INV / host / "inv" / "inspect.json"
    out = {}
    if p.exists():
        for c in json.loads(p.read_text() or "[]"):
            labels = c.get("Config", {}).get("Labels") or {}
            key = (labels.get("com.docker.compose.project", ""), labels.get("com.docker.compose.service", ""))
            running = bool(c.get("State", {}).get("Running"))
            if key[0] and (running or key not in out):   # prefer the running container
                out[key] = dict(e.split("=", 1) for e in c["Config"].get("Env") or [] if "=" in e)
                out[key]["__running__"] = "1" if running else ""
                out[key]["__oneshot__"] = "1" if (c.get("HostConfig", {}).get("RestartPolicy") or {}).get("Name", "no") in ("no", "") else ""
    return out


def env_check(s: Stack, runtime: dict, mask: Masker) -> list[str]:
    """Env the repo version would give each service vs what the running container has."""
    files = [n for n in ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml") if (s.local / n).exists()]
    raw = compose_config(s.local, files)
    if raw.startswith("ERROR"):
        return []
    out = []
    for svc, conf in json.loads(raw).get("services", {}).items():
        have = runtime.get((s.name, svc))
        if have is None:
            continue
        if not have.get("__running__") and not have.get("__oneshot__"):
            out.append(f"  !! {svc}: container is NOT running on the host")
        for k, v in (conf.get("environment") or {}).items():
            v = "" if v is None else str(v)
            if not v and have.get(k):
                out.append(f"  !! {svc}: {k} would be EMPTY (running container has a value)")
            elif v and k in have and have[k] != v:
                out.append(f"  ~ {svc}: {k} differs from the running container")
    return out


def diff_stack(host: str, s: Stack, hashes: dict[str, str] | None, runtime: dict) -> tuple[str, list[str]]:
    snap = INV / host / "inv" / "projects" / s.name
    snap_files = snap / "files"
    render(s)
    mask = Masker()
    for rel, secret in s.files.items():
        if secret:
            want_kv = parse_kv_lines((s.local / rel).read_text(errors="replace"))
            mask.learn(want_kv, force=s.op_keys.get(rel, set()))
            hp = snap_files / rel
            if hp.exists():
                mask.learn(parse_kv_lines(hp.read_text(errors="replace")), force=s.op_keys.get(rel, set()))
    if (snap_files / ".env").exists():
        mask.learn(parse_kv_lines((snap_files / ".env").read_text(errors="replace")), force=s.op_keys.get(".env", set()))

    out, changed = [], 0
    tree = host_tree(snap)
    for rel, secret in sorted(s.files.items()):
        want = s.local / rel
        hp = snap_files / rel
        if hashes is not None:
            # live hash check is authoritative; the snapshot only supplies content to diff
            live = hashes.get(f"{s.working_dir}/{rel}")
            if live == hashlib.sha256(want.read_bytes()).hexdigest():
                continue
            if live is None:
                out.append(f"  + {rel}: new file" + ("  [secret]" if secret else ""))
                changed += 1
                continue
            if not hp.exists() or hashlib.sha256(hp.read_bytes()).hexdigest() != live:
                out.append(f"  ~ {rel}: differs (current content not in snapshot; re-run ops/collect to see it)")
                changed += 1
                continue
        elif not hp.exists():
            if rel in tree:
                out.append(f"  ? {rel}: on host ({tree[rel]} bytes) but not in snapshot; will be overwritten")
            else:
                out.append(f"  + {rel}: new file?  (no hash check; snapshot only)" + ("  [secret]" if secret else ""))
            changed += 1
            continue
        if hp.read_bytes() == want.read_bytes():
            continue
        changed += 1
        if secret:
            lines = kv_diff(hp.read_text(errors="replace"), want.read_text(errors="replace"))
            out.append(f"  ~ {rel}  [secret, keys only]")
            out += [f"      {l}" for l in lines] or ["      (same keys and values; whitespace/order/quoting only)"]
        else:
            try:
                a, b = hp.read_text().splitlines(), want.read_text().splitlines()
            except UnicodeDecodeError:
                out.append(f"  ~ {rel}: binary differs")
                continue
            out.append(f"  ~ {rel}")
            out += ["      " + mask(l) for l in list(difflib.unified_diff(a, b, "host", "repo", n=2, lineterm=""))[2:]]

    if not (snap_files / ".env.tpl").exists() and (snap_files / ".env").exists() and ".env" not in s.files:
        out.append("  note: host has .env but repo has no .env.tpl; host .env is left as is")

    env = env_check(s, runtime, mask)
    if env:
        out.append("  runtime env (repo vs running container):")
        out += env
        if any("EMPTY" in l or "differs" in l for l in env):
            changed += 1
    if s.relocate_from:
        out.insert(0, f"  RELOCATE: running from {s.relocate_from} (dir no longer exists); deploys to {s.working_dir}")
    eff = effective(s, snap_files, mask) if changed and not s.relocate_from else []
    if eff:
        out.append("  effective compose config (host -> repo):")
        out += eff
    elif changed and not s.relocate_from:
        out.append("  effective compose config: identical")

    extra = sorted(
        p.relative_to(snap_files).as_posix() for p in snap_files.rglob("*")
        if p.is_file() and p.relative_to(snap_files).as_posix() not in s.files
    )
    extra = [e for e in extra if e not in (".env.tpl",) and not (e == ".env" and ".env" in s.files)]
    if extra:
        noise = [e for e in extra if NOISE.search(e)]
        keep = [e for e in extra if e not in noise]
        if keep:
            out.append(f"  host-only files (left alone): {', '.join(keep[:12])}{' ...' if len(keep) > 12 else ''}")
        if noise:
            out.append(f"  host-only backups/logs (left alone): {len(noise)}")

    hf, hr = snap / "config-hash-files.txt", snap / "config-hash-running.txt"
    if hf.exists() and hr.exists():
        on_disk = {l.split()[0]: l.split()[1] for l in hf.read_text().splitlines() if len(l.split()) == 2}
        running = {l.split()[0]: l.split()[1] for l in hr.read_text().splitlines() if len(l.split()) == 2}
        stale = [svc for svc in running if svc in on_disk and on_disk[svc] != running[svc]]
        if stale:
            out.append(f"  note: host compose on disk was edited but never `up`'d for: {', '.join(stale)}")

    return ("changed" if changed else "same"), out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--stack", help="comma-separated stack names")
    ap.add_argument("--any-branch", action="store_true")
    a = ap.parse_args()

    head = check_repo(a.any_branch)
    stacks, unmanaged = plan(a.host)
    hashes = load_hashes(a.host)
    runtime = running_env(a.host)
    if hashes is None:
        print("warning: no live hash check (.inventory/<host>/hashes.txt); run via ops/diff\n", file=sys.stderr)
    want = set(a.stack.split(",")) if a.stack else None
    if want and (unknown := want - set(stacks)):
        raise SystemExit(f"unknown stacks for {a.host}: {', '.join(sorted(unknown))}")

    report, summary = [], {"same": [], "changed": [], "relocate": [], "not deployed": [], "unmanaged": unmanaged if not want else []}
    for name, s in stacks.items():
        if want and name not in want:
            continue
        if not s.working_dir:
            summary["not deployed"].append(name)
            if want:
                render(s)
                report += [f"\n## {name}  (not deployed; ops/apply --create puts it in {canonical_dir(a.host, s.repo_dir)})",
                           *(f"  + {rel}" + ("  [secret]" if secret else "") for rel, secret in sorted(s.files.items()))]
            continue
        status, lines = diff_stack(a.host, s, hashes, runtime)
        if s.relocate_from:
            status = "relocate"
        summary[status].append(name)
        if lines:
            report += [f"\n## {name}  ({s.working_dir})", *lines]

    snap_time = (INV / a.host / "inv" / "host.txt")
    head_lines = [f"# {a.host}: repo HEAD {head} vs host snapshot"
                  + (f" ({snap_time.read_text().splitlines()[3:4][0]})" if snap_time.exists() else "")]
    for k, v in summary.items():
        if v:
            head_lines.append(f"{k:13} {len(v):3}  {', '.join(v)}")
    text = "\n".join(head_lines + report) + "\n"
    out = INV / a.host / "diff.txt"
    out.write_text(text)
    out.chmod(0o600)
    print(text)
    print(f"(saved to {out.relative_to(INV.parent)})")


if __name__ == "__main__":
    main()
