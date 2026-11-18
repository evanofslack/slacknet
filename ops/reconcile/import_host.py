"""Reconcile pass 1: pull one host's real state into vms/. Never touches the host.

Reads the read-only inventory in .inventory/<host>/ (run ops/collect first):

  1. clone edits   - the host's ~/slacknet clone has uncommitted edits against an
                     old commit. Replay its `git diff HEAD` (limited to this host's
                     repo_path) onto the current branch with a 3-way merge, so
                     newer repo changes are kept and real conflicts get markers.
  2. clone files   - untracked files the host added under its repo_path.
  3. loose stacks  - stacks run from outside the clone (e.g. ~/docker/<app>):
                     compose files, top-level files, single-file bind mounts and
                     EXTRA files -> <repo_path>/<app>/. Directory mounts are app
                     state and are not imported.
  Host-local archive dirs (<repo_path>/archive/<app>) are skipped (not tracked).

Secrets are NOT handled here: .env files are never copied. Run secrets.py next.

    uv run --no-env-file python reconcile/import_host.py <host> [--dry-run]
"""

import argparse
import collections
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

OPS = Path(__file__).resolve().parent.parent
REPO = OPS.parent
INV = REPO / ".inventory"
sys.path.insert(0, str(OPS))
import inventory  # noqa: E402

# Never imported (matched against repo-relative paths).
EXCLUDE = [
    "*/.env", "*/.env.*.local",
    "*.bak", "*.bak/*", "*/plugins/*",
    "*.log", "*/logs/*", "*.db", "*.db-*", "*.sqlite*", "*.pid",
    "vms/nubuntu/filebrowser/srv/*",     # served files, not config
    "*/jellyfin/config/*",               # app state
    "*_data/*", "*/redis_data/*",        # db dirs in archived stacks
    "*/state.json",                      # app state (wineparty)
]

# User-authored files inside otherwise app-owned mount dirs (loose stacks).
EXTRA = {
    ("racknerd", "caddy"): ["conf/Caddyfile", "conf/Caddyfile.full"],
    ("torrr", "recyclarr"): ["config/recyclarr.yml", "config/settings.yml", "config/secrets.yml"],
}


def hosts() -> dict[str, dict]:
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


def excluded(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in EXCLUDE)


class Importer:
    def __init__(self, host: str, dry_run: bool):
        self.host = host
        self.repo_path = hosts()[host]["repo_path"]
        self.inv = INV / host / "inv"
        self.dry = dry_run
        self.done: list[str] = []
        self.skipped: list[str] = []
        self.conflicts: list[str] = []
        self.excluded = collections.Counter()

    def copy(self, src: Path, rel: str) -> None:
        if excluded(rel):
            self.excluded["/".join(rel.split("/")[:4])] += 1
            return
        # Host-local archive dirs are not tracked
        if rel.startswith(f"{self.repo_path}/archive/") or "/archive/" in rel:
            self.excluded["archive"] += 1
            return
        dest = REPO / rel
        if dest.exists():
            if dest.read_bytes() != src.read_bytes():
                # Never clobber: the repo copy may already have had secrets
                # moved out (secrets.py), or been edited during review.
                self.skipped.append(f"{rel}  (exists and differs; kept repo version)")
            return
        self.done.append(f"add    {rel}")
        if not self.dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # 1 -------------------------------------------------------------------
    def clone_edits(self, clone: Path) -> None:
        patch = clone / "diff.patch"
        if not patch.exists() or not patch.stat().st_size:
            return
        args = ["git", "-C", str(REPO), "apply", "--3way", f"--include={self.repo_path}/*", str(patch)]
        check = subprocess.run(["git", "-C", str(REPO), "apply", "--stat",
                                f"--include={self.repo_path}/*", str(patch)], capture_output=True, text=True)
        files = [l.split("|")[0].strip() for l in check.stdout.splitlines() if "|" in l]
        if not files:
            return
        if self.dry:
            self.done += [f"patch  {f}" for f in files]
            return
        r = subprocess.run(args, capture_output=True, text=True)
        for line in (r.stdout + r.stderr).splitlines():
            if "with conflicts" in line or line.startswith("U "):
                self.conflicts.append(line)
            elif line.startswith("error"):
                self.conflicts.append(line)
        self.done += [f"patch  {f}" for f in files]
        # --3way stages results; leave everything unstaged for review.
        subprocess.run(["git", "-C", str(REPO), "reset", "-q", "--", self.repo_path])

    # 2 -------------------------------------------------------------------
    def clone_untracked(self, clone: Path) -> None:
        root = clone / "untracked"
        listed = (clone / "untracked.txt").read_text().splitlines() if (clone / "untracked.txt").exists() else []
        copied = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} if root.exists() else set()
        for rel in sorted(copied):
            if rel.startswith(self.repo_path + "/"):
                self.copy(root / rel, rel)
        outside = sorted({"/".join(r.split("/")[:3]) for r in listed if not r.startswith(self.repo_path + "/")})
        for o in outside:
            self.skipped.append(f"{o}/  (untracked on host, outside {self.repo_path})")
        not_copied = [r for r in listed if r.startswith(self.repo_path + "/") and r not in copied and not excluded(r)]
        if not_copied:
            dirs = sorted({str(Path(r).parent) for r in not_copied})
            self.skipped.append(f"{len(not_copied)} large/data files in: {', '.join(dirs[:8])}{' …' if len(dirs) > 8 else ''}")

    # 3 -------------------------------------------------------------------
    def loose_stacks(self) -> None:
        for pdir in sorted((self.inv / "projects").iterdir()):
            meta = read_kv(pdir / "meta.txt")
            wd = meta.get("working_dir", "")
            name, status = pdir.name, meta.get("status", "")
            if meta.get("working_dir_missing"):
                inrepo = (REPO / self.repo_path / Path(wd).name).exists()
                why = "dir moved; repo has it" if inrepo else "dir deleted on host"
                self.skipped.append(f"{name}  ({status}, {why}: {wd})")
                continue
            if "/slacknet/" in wd:
                own = f"/slacknet/{self.repo_path}/"
                if own not in wd + "/":
                    self.skipped.append(f"{name}  (runs from another host's dir: {wd})")
                    continue
                if meta.get("git_toplevel", "").rstrip("/") != wd.split(f"/{self.repo_path}/")[0].rstrip("/") + "":
                    self.skipped.append(f"{name}  (its own git repo, not slacknet: {wd})")
                    continue
                dest = wd.split("/slacknet/", 1)[1]
                if any((REPO / dest / n).exists() for n in
                       ("docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml")):
                    continue  # handled by the clone steps
                # In the clone but invisible to git (e.g. gitignored on the host):
                # fall through and import it like a loose stack.
                app = Path(wd).name
            else:
                app = Path(wd).name
                dest = f"{self.repo_path}/{app}"
            files = pdir / "files"
            wanted: set[str] = set()
            for p in files.iterdir() if files.exists() else []:
                if p.is_file() and not p.name.startswith("."):
                    wanted.add(p.name)
            for cf in meta.get("config_files", "").split(","):
                if cf:
                    wanted.add(str(Path(cf).relative_to(wd)) if cf.startswith(wd + "/") else Path(cf).name)
                    wanted |= self.file_mounts(files / Path(cf).name, files)
            wanted |= set(EXTRA.get((self.host, app), []))
            for rel in sorted(wanted):
                src = files / rel
                if src.is_file():
                    self.copy(src, f"{dest}/{rel}")
                else:
                    self.skipped.append(f"{dest}/{rel}  (not collected)")

    @staticmethod
    def file_mounts(compose: Path, files: Path) -> set[str]:
        out = set()
        try:
            doc = yaml.safe_load(compose.read_text()) or {}
        except Exception:
            return out
        for svc in (doc.get("services") or {}).values():
            for v in svc.get("volumes") or []:
                src = v.split(":")[0] if isinstance(v, str) else (v or {}).get("source", "")
                if src.startswith("./") and (files / src).is_file():
                    out.add(str(Path(src)))
        return out

    def run(self) -> None:
        clone = self.inv / "clones" / "_home_eslack_slacknet"
        if clone.exists():
            self.clone_edits(clone)
            self.clone_untracked(clone)
        self.loose_stacks()

        print(f"## {self.host} -> {self.repo_path}{'  (dry run)' if self.dry else ''}")
        print(f"\nimported ({len(self.done)}):")
        for d in self.done:
            print(f"  {d}")
        if self.conflicts:
            print("\nCONFLICTS (resolve markers before committing):")
            for c in self.conflicts:
                print(f"  {c}")
        if self.excluded:
            print(f"\nexcluded by pattern ({sum(self.excluded.values())} files):")
            for d, n in sorted(self.excluded.items()):
                print(f"  {n:4}  {d}/")
        print(f"\nnot imported ({len(self.skipped)}):")
        for s in self.skipped:
            print(f"  {s}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("host", choices=sorted(hosts()))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    Importer(a.host, a.dry_run).run()
