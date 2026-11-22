"""Data migration stage 2: plan moving stack state out of compose dirs to /srv/<stack>.

From the latest ops/collect snapshot, for every repo stack that runs on a host, each bind
mount whose source is inside the stack's working dir is classified:

  git    the path (or its .tpl) is tracked in the repo -> stays relative
  data   anything else -> /srv/<stack>/<same rel path>

Named volumes get pinned with a top-level `name:` (so a project rename can't orphan them).

Writes .inventory/<host>/datadirs.json (move list for ops/migrate; gitignored, holds host
paths) and, with --write, rewrites compose files / .env.tpl in vms/. Every rewritten stack is
checked with `docker compose config`: only data bind sources and volume names may change.

    uv run --no-env-file python reconcile/datadirs.py [--host h ...] [--write]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from deploy.desired import canonical_dir, git, plan  # noqa: E402
from lib import INV, REPO, hosts  # noqa: E402

SRV = "/srv"
# reviewed by hand before migrating (see docs/data-migration.md)
REVIEW: dict[tuple[str, str, str], str] = {}
# mounts dropped from compose on purpose: not moved, not remapped (old copy stays, archived later)
DROPPED = {
    ("nubuntu", "changedetection", "browser/dev/shm"),   # -> shm_size: 2gb
    ("dorp", "umami", "sql/schema.postgresql.sql"),      # init script; db already initialised
}
OP_REF = re.compile(r"\{\{\s*op://[^}]*\}\}")


def tracked(repo_dir: str) -> set[str]:
    """Paths tracked under a stack dir (relative), with .tpl names also listed as rendered."""
    out = set()
    for p in git("ls-tree", "-r", "--name-only", "HEAD", "--", repo_dir).splitlines():
        rel = Path(p).relative_to(repo_dir).as_posix()
        out.add(rel)
        if rel.endswith(".tpl"):
            out.add(rel[: -len(".tpl")])
    return out


def is_tracked(rel: str, files: set[str]) -> bool:
    return rel in files or any(f.startswith(rel + "/") for f in files)


def containers(host: str) -> list[dict]:
    return json.loads((INV / host / "inv" / "inspect.json").read_text())


def plan_host(host: str) -> dict:
    stacks, _ = plan(host)
    by_project: dict[str, list[dict]] = {}
    for c in containers(host):
        p = c["Config"]["Labels"].get("com.docker.compose.project")
        if p:
            by_project.setdefault(p, []).append(c)
    out = {}
    for name, s in stacks.items():
        if not s.working_dir or name not in by_project:
            continue
        wd = s.working_dir.rstrip("/")
        files = tracked(s.repo_dir)
        moves, keep, named, review, mixed = {}, set(), {}, {}, set()
        for c in by_project[name]:
            for m in c.get("Mounts", []):
                src = m.get("Source", "")
                if m["Type"] == "bind" and src.startswith(wd + "/"):
                    rel = src[len(wd) + 1:]
                    if is_tracked(rel, files):
                        keep.add(rel)
                        if rel not in files:   # a tracked dir: may also hold app-written files
                            snap = INV / host / "inv" / "projects" / name / "files" / rel
                            if snap.is_dir() and any(
                                    f.is_file() and f"{rel}/{f.relative_to(snap).as_posix()}" not in files
                                    for f in snap.rglob("*")):
                                mixed.add(rel)
                    elif (host, name, rel) in DROPPED:
                        continue
                    else:
                        moves[rel] = f"{SRV}/{name}/{rel}"
                        if (host, name, rel) in REVIEW:
                            review[rel] = REVIEW[(host, name, rel)]
                elif m["Type"] == "volume" and len(m.get("Name", "")) != 64:
                    named[m["Name"]] = m["Destination"]
        # every moved path is remapped in compose; a path inside another moved one isn't mv'd itself
        remap = dict(moves)
        for rel in list(moves):
            if any(rel != o and rel.startswith(o + "/") for o in remap):
                moves.pop(rel)
        canon = canonical_dir(host, s.repo_dir)
        if not (moves or named or wd != canon):
            continue
        out[name] = {
            "repo_dir": s.repo_dir,
            "old_wd": wd,
            "new_wd": canon,
            "moves": [{"rel": r, "src": f"{wd}/{r}", "dst": d} for r, d in sorted(moves.items())],
            "remap": [{"rel": r, "dst": d} for r, d in sorted(remap.items())],
            "keep_relative": sorted(keep),
            "mixed_dirs": sorted(mixed),
            "named_volumes": sorted(named),
            "review": review,
            "config_files": [Path(f).name for f in s.config_files] or [],
        }
    return out


# ------------------------------------------------------------------ rewriting
def rewrite_compose(text: str, stack: str, moves: list[dict]) -> tuple[str, int]:
    n_total = 0
    for mv in sorted(moves, key=lambda m: -len(m["rel"])):
        rel = re.escape(mv["rel"])
        # short syntax:  - ./rel:/x   - "./rel:/x"   - ./rel/:/x ; long syntax:  source: ./rel
        pat = re.compile(rf"(^\s*-\s*['\"]?|^\s*source:\s*['\"]?)\./{rel}/?(?=[:'\"\s]|$)", re.M)
        text, n = pat.subn(lambda m: m.group(1) + mv["dst"], text)
        n_total += n
    return text, n_total


def rewrite_env_tpl(text: str, moves: list[dict]) -> tuple[str, int, set[str]]:
    n_total, keys = 0, set()
    for mv in moves:
        pat = re.compile(rf"^([A-Z_][A-Z0-9_]*)=['\"]?\./{re.escape(mv['rel'])}/?['\"]?[ \t]*$", re.M)
        keys |= {m.group(1) for m in pat.finditer(text)}
        text, n = pat.subn(lambda m: f"{m.group(1)}={mv['dst']}", text)
        n_total += n
    return text, n_total, keys


def pin_volumes(text: str, project: str, named: list[str]) -> tuple[str, list[str]]:
    """Add `name: <actual>` under top-level volumes whose actual name is <project>_<key>."""
    lines = text.splitlines(keepends=True)
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"^volumes:\s*$", l))
    except StopIteration:
        return text, []
    pinned, i = [], start + 1
    while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
        m = re.match(r"^(\s+)([\w.-]+):\s*(\{\})?\s*(#.*)?$", lines[i])
        if m and len(m.group(1)) <= 4:
            key, ind = m.group(2), m.group(1)
            # what's already under this key
            j, body = i + 1, []
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > len(ind)):
                body.append(lines[j])
                j += 1
            if any(re.match(r"\s*(name|external):", b) for b in body):
                i = j
                continue
            actual = f"{project}_{key}"
            if actual in named:
                lines[i] = f"{ind}{key}:\n"
                lines.insert(i + 1, f"{ind}{ind}name: {actual}\n")
                pinned.append(actual)
                j += 1
            i = j
            continue
        i += 1
    return "".join(lines), pinned


def compose_cfg(stack_dir: Path, files: list[str]) -> dict:
    env = {}
    tpl = stack_dir / ".env.tpl"
    if tpl.exists():
        for line in tpl.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = OP_REF.sub("x", v.strip())
    content = "".join(f"{k}={v}\n" for k, v in env.items())
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write(content)
    # services with `env_file: .env` need the file to exist; never touch a real one
    dummy = stack_dir / ".env"
    made = not dummy.exists()
    if made:
        dummy.write_text(content)
    args = ["docker", "compose", "-p", "check", "--env-file", f.name]
    for c in files:
        args += ["-f", c]
    try:
        r = subprocess.run(args + ["config", "--format", "json"], cwd=stack_dir, capture_output=True, text=True)
    finally:
        Path(f.name).unlink()
        if made:
            dummy.unlink()
    if r.returncode:
        raise SystemExit(f"{stack_dir}: compose config failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def check(before: dict, after: dict, stack_dir: Path, moves: list[dict], env_keys: set[str]) -> list[str]:
    """Problems if anything other than data bind sources / volume names changed.
    env_keys: .env vars that were rewritten; they may also change in services that load .env."""
    want = {str(stack_dir / m["rel"]): m["dst"] for m in moves}
    probs, seen = [], set()
    for svc, b in before.get("services", {}).items():
        a = after["services"].get(svc, {})
        bv, av = b.get("volumes", []), a.get("volumes", [])
        if len(bv) != len(av):
            probs.append(f"{svc}: volume count changed")
            continue
        for x, y in zip(bv, av):
            if x == y:
                continue
            if x.get("type") == "bind" and want.get(x["source"].rstrip("/")) == y.get("source", "").rstrip("/"):
                seen.add(x["source"].rstrip("/"))
                if {**x, "source": y["source"]} == y:
                    continue
            probs.append(f"{svc}: unexpected volume change {x} -> {y}")
        def rest(d: dict) -> dict:
            out = {k: v for k, v in d.items() if k != "volumes"}
            if "environment" in out:
                out["environment"] = {k: v for k, v in out["environment"].items() if k not in env_keys}
            return out
        if rest(b) != rest(a):
            probs.append(f"{svc}: non-volume config changed")
    for k in set(want) - seen:
        probs.append(f"move not applied in compose: {k}")
    for k, v in before.get("volumes", {}).items():
        a = after.get("volumes", {}).get(k)
        if a is None or {kk: vv for kk, vv in a.items() if kk != "name"} != {kk: vv for kk, vv in v.items() if kk != "name"}:
            probs.append(f"top-level volume {k}: changed beyond name")
    return probs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", action="append")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    failed = False
    for host in a.host or list(hosts()):
        if not (INV / host / "inv").exists():
            continue
        p = plan_host(host)
        (INV / host / "datadirs.json").write_text(json.dumps(p, indent=2) + "\n")
        print(f"\n# {host}: {len(p)} stacks")
        for name, s in sorted(p.items()):
            reloc = f"  (relocate from {s['old_wd']})" if s["old_wd"] != s["new_wd"] else ""
            print(f"  {name}{reloc}")
            for mv in s["moves"]:
                note = f"   !! REVIEW: {s['review'][mv['rel']]}" if mv["rel"] in s["review"] else ""
                print(f"      mv ./{mv['rel']} -> {mv['dst']}{note}")
            for r in s["mixed_dirs"]:
                print(f"      ~  ./{r} is tracked but holds app-written files")
            sd = REPO / s["repo_dir"]
            cfs = [f for f in ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml")
                   if (sd / f).exists()]
            files = [f for f in (s["config_files"] or cfs) if (sd / f).exists()] or cfs
            before = compose_cfg(sd, files) if a.write else None
            changed = {}
            n_moves = 0
            for f in files:
                t = (sd / f).read_text()
                new, n = rewrite_compose(t, name, s["remap"])
                n_moves += n
                new, pinned = pin_volumes(new, name, s["named_volumes"])
                for v in pinned:
                    print(f"      pin volume {v}")
                if new != t:
                    changed[sd / f] = new
            env_keys = set()
            tpl = sd / ".env.tpl"
            if tpl.exists():
                new, n, env_keys = rewrite_env_tpl(tpl.read_text(), s["remap"])
                n_moves += n
                if n:
                    changed[tpl] = new
            # already rewritten by an earlier run
            texts = [(sd / f).read_text() for f in files] + ([tpl.read_text()] if tpl.exists() else [])
            n_moves += sum(1 for m in s["remap"] if any(re.search(rf"{re.escape(m['dst'])}(?=[:'\"\s/]|$)", x, re.M) for x in texts))
            if n_moves < len(s["remap"]):
                print(f"      !! only {n_moves}/{len(s['remap'])} mounts found in compose/.env.tpl")
                failed = True
            if a.write and changed:
                old = {f: f.read_text() for f in changed}
                for f, t in changed.items():
                    f.write_text(t)
                probs = check(before, compose_cfg(sd, files), sd, s["remap"], env_keys)
                if probs:
                    failed = True
                    for f, t in old.items():
                        f.write_text(t)
                    print("      !! check failed, not written:\n" + "\n".join(f"         {x}" for x in probs))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
