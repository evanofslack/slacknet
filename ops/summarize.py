"""Summarise .inventory/<host>/ against the repo's vms/ tree.

For each host: running compose projects and whether the repo tracks them,
repo stacks that aren't running, and containers not managed by compose.
"""

import json
import subprocess
import sys
from pathlib import Path

import inventory

REPO = Path(__file__).resolve().parent.parent
INV = REPO / ".inventory"
LOCAL_HEAD = subprocess.run(["git", "-C", str(REPO), "rev-parse", "main"], capture_output=True, text=True).stdout.strip()


def read_meta(p: Path) -> dict:
    meta = {}
    if p.exists():
        for line in p.read_text().splitlines():
            k, _, v = line.partition("=")
            meta[k] = v
    return meta


def main(only: set[str]) -> None:
    # every list-of-(name, data) group defined in inventory.py
    hosts = [h for v in vars(inventory).values() if isinstance(v, list) for h in v
             if isinstance(h, tuple) and len(h) == 2 and isinstance(h[1], dict)]
    for name, data in hosts:
        if only and name not in only:
            continue
        hdir = INV / name / "inv"
        print(f"\n### {name}")
        if not hdir.exists():
            print("  (no inventory collected — host unreachable?)")
            continue
        if (hdir / "docker-unavailable.txt").exists():
            print("  docker:", (hdir / "docker-unavailable.txt").read_text().strip())
            continue

        repo_dir = REPO / data["repo_path"]
        repo_stacks = {p.name for p in repo_dir.iterdir() if p.is_dir()} if repo_dir.exists() else set()
        seen_repo = set()

        print(f"  {'project':24} {'status':14} {'repo':10} working dir")
        for pdir in sorted((hdir / "projects").iterdir()):
            meta = read_meta(pdir / "meta.txt")
            wd = meta.get("working_dir", "")
            key = Path(wd).name if wd else pdir.name
            if key in repo_stacks:
                tracked = "tracked"
                seen_repo.add(key)
            elif pdir.name in repo_stacks:
                tracked = "tracked*"  # matched by project name, dir differs
                seen_repo.add(pdir.name)
            else:
                tracked = "UNTRACKED"
            git = ""
            if meta.get("git_toplevel"):
                head = meta.get("git_head", "")[:8]
                behind = "" if head and LOCAL_HEAD.startswith(head) else f" @{head}"
                gs = pdir / "git-status.txt"
                dirty = len([l for l in gs.read_text().splitlines() if l.strip()]) if gs.exists() else 0
                git = f" [git{behind}{f', {dirty} dirty' if dirty else ''}]"
            if meta.get("working_dir_missing"):
                git += " [dir missing]"
            print(f"  {pdir.name:24} {meta.get('status', '')[:14]:14} {tracked:10} {wd}{git}")

        missing = sorted(repo_stacks - seen_repo)
        if missing:
            print(f"  in repo but not on host: {', '.join(missing)}")

        loose = []
        cfile = hdir / "containers.jsonl"
        if cfile.exists():
            for line in cfile.read_text().splitlines():
                c = json.loads(line)
                if "com.docker.compose.project=" not in c.get("Labels", ""):
                    loose.append(f"{c['Names']} ({c['Image']}, {c['State']})")
        if loose:
            print("  containers outside compose:", "; ".join(loose))

        on_disk = (hdir / "compose-files-on-disk.txt")
        if on_disk.exists():
            running_dirs = {read_meta(p / "meta.txt").get("working_dir") for p in (hdir / "projects").iterdir()}
            own = f"/{data['repo_path']}/"
            stale = [
                f for f in on_disk.read_text().splitlines()
                if str(Path(f).parent) not in running_dirs
                # host clones contain every host's dirs; only report this host's or non-repo files
                and ("/slacknet/vms/" not in f or own in f)
            ]
            if stale:
                print("  compose files on disk with no project:")
                for f in stale:
                    print(f"    {f}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
