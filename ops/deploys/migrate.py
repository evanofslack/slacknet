"""Move stacks' state out of their compose dir to /srv/<stack>, and relocate stacks to
~/slacknet/<repo dir>. Plan: .inventory/<host>/datadirs.json (reconcile/datadirs.py).

Run via ../ops/migrate <host> --stack a,b. Per stack:
  1. preflight (nothing changed yet): sources present, targets absent, same filesystem,
     files to carry over readable; pull the mv helper image
  2. back up the compose/config files at the old dir -> ~/.slacknet-backups/<ts>/<stack>.tgz,
     and the move list -> <stack>.migrate (for --rollback)
  3. docker compose down (never -v); mv each data path to /srv/<stack>/... (as root, via a container)
  4. relocation only: copy app-written files out of tracked dirs (cp -an), then push repo files
  5. docker compose up -d --pull missing (never updates images); verify mounts
     (--no-up: leave the stack down, only check the moved paths exist)

--rollback (with --ts): down, mv everything back, restore the old files, up from the old dir.
"""

import json
import os
import shlex
import sys

from pyinfra import host
from pyinfra.operations import files, server

OPS_DIR = os.getcwd()
sys.path.insert(0, OPS_DIR)
from deploy.desired import check_repo, plan, render  # noqa: E402
from lib import COMPOSE_NAMES, INV  # noqa: E402

q = shlex.quote
want = [s for s in str(host.data.get("stacks") or "").split(",") if s]
ts = str(host.data.get("ts") or "")
rollback = bool(host.data.get("rollback"))
no_up = bool(host.data.get("no_up"))
if not want or not ts:
    raise SystemExit("migrate: --stack and ts are required")

manifest_path = INV / host.name / "datadirs.json"
if not manifest_path.exists():
    raise SystemExit(f"migrate: no {manifest_path}; run reconcile/datadirs.py")
manifest = json.loads(manifest_path.read_text())
B = f"$HOME/.slacknet-backups/{q(ts)}"
# Data dirs are often owned by root or a container uid, and renaming a directory into another
# parent needs write access to the directory itself. Rename as root in a throwaway container
# (docker group is root-equivalent already); one bind of / keeps it a same-filesystem rename.
HELPER = "alpine:3.20"
RMV = (f'helper() {{ docker image inspect {HELPER} >/dev/null 2>&1 || docker pull -q {HELPER} >/dev/null; }}\n'
       f'rmv() {{ mkdir -p "$(dirname "$2")" && docker run --rm --network none -v /:/host {HELPER} mv "/host$1" "/host$2"; }}\n')


def compose_args(names: list[str]) -> str:
    return " ".join(f"-f {q(n)}" for n in names)


# ------------------------------------------------------------------ rollback
if rollback:
    for name in want:
        n = q(name)
        server.shell(
            name=f"{name}: rollback from {ts}",
            commands=[f"""set -eu
{RMV}helper
M={B}/{n}.migrate
test -f "$M" || {{ echo "no migration record $M"; exit 1; }}
OLD=$(sed -n 's/^old_wd\\t//p' "$M"); CFG=$(sed -n 's/^old_cfg\\t//p' "$M")
cd "$OLD" 2>/dev/null || cd /
docker compose -p {n} down
grep '^mv\\t' "$M" | while IFS="$(printf '\\t')" read -r _ src dst; do
  if [ -e "$dst" ] && [ ! -e "$src" ]; then rmv "$dst" "$src" && echo "moved back $dst -> $src"; fi
done
cd "$OLD" && tar xzf {B}/{n}.tgz
args=""; for f in $(echo "$CFG" | tr ',' ' '); do args="$args -f $f"; done
docker compose -p {n} $args up -d --pull missing
docker ps -a --filter label=com.docker.compose.project={n} --format '{{{{.Names}}}} {{{{.State}}}}'
"""],
        )
else:
    check_repo(bool(host.data.get("any_branch")))
    stacks, _ = plan(host.name)

for name in ([] if rollback else want):
    if name not in manifest:
        raise SystemExit(f"migrate: {name!r} has nothing to migrate on {host.name} (see datadirs.json)")
    m = manifest[name]
    if not m["moves"] and m["old_wd"] == m["new_wd"]:
        raise SystemExit(f"migrate: {name!r} only needs volume pins; use ops/apply (files only)")
    s = render(stacks[name])
    old, new, n = m["old_wd"], m["new_wd"], q(name)
    old_cfg = [os.path.basename(f) for f in s.config_files] or m["config_files"]
    new_cfg = [f for f in COMPOSE_NAMES if f in s.files]
    if not new_cfg:
        raise SystemExit(f"migrate: {name}: no compose file in repo")
    moves = m["moves"]
    reloc = old != new
    keep_dirs = m["keep_relative"] if reloc else []
    backup_files = " ".join(q(f) for f in sorted(set(s.files) | set(old_cfg) | {".env"}))

    record = "\\n".join(
        [f"old_wd\\t{old}", f"new_wd\\t{new}", f"old_cfg\\t{','.join(old_cfg)}"]
        + [f"mv\\t{mv['src']}\\t{mv['dst']}" for mv in moves])
    pre = []
    for mv in moves:
        src, dst = q(mv["src"]), q(mv["dst"])
        pre.append(f"""
if [ -e {dst} ] && [ ! -e {src} ]; then echo "already moved: {mv['rel']}"
elif [ ! -e {src} ]; then echo "MISSING source {mv['src']}"; bad=1
elif [ -e {dst} ]; then echo "TARGET EXISTS {mv['dst']}"; bad=1
else
  [ "$(stat -c %d "$(dirname {src})")" = "$(stat -c %d /srv)" ] || {{ echo "DIFFERENT FILESYSTEM: {mv['src']}"; bad=1; }}
fi""")
    for r in keep_dirs:
        d = q(old + "/" + r)
        pre.append(f"""
if [ -d {d} ] && [ -n "$(find {d} ! -readable -print -quit 2>/dev/null)" ]; then
  echo "UNREADABLE files in tracked dir to carry over: ./{r}"; bad=1; fi""")
    # 1-3: preflight, backup, down, move
    server.shell(
        name=f"{name}: preflight, back up, down, move data",
        commands=[f"""set -eu
{RMV}bad=0
test -w /srv || {{ echo "/srv not writable (sudo chown $USER: /srv)"; exit 1; }}
{''.join(pre)}
[ "$bad" = 0 ] || exit 1
helper
mkdir -p {B} && chmod 700 $HOME/.slacknet-backups {B}
if [ -d {q(old)} ]; then cd {q(old)} && for f in {backup_files}; do [ -e "$f" ] && echo "$f"; done | tar czf {B}/{n}.tgz -T - ; else tar czf {B}/{n}.tgz -T /dev/null; fi
chmod 600 {B}/{n}.tgz
printf '{record}\\n' > {B}/{n}.migrate
if [ -d {q(old)} ] && (cd {q(old)} && for f in {' '.join(q(f) for f in old_cfg) or 'none'}; do [ -f "$f" ] || exit 1; done); then
  cd {q(old)} && docker compose -p {n} {compose_args(old_cfg)} down
else
  cd / && docker compose -p {n} down
fi
""" + "".join(
            f"if [ -e {q(mv['src'])} ]; then rmv {q(mv['src'])} {q(mv['dst'])} && echo 'moved {mv['rel']}'; fi\n"
            for mv in moves) + (
            f"mkdir -p {q(new)}\n" + "".join(
                f"if [ -d {q(old + '/' + r)} ]; then mkdir -p {q(new + '/' + r)} && cp -an {q(old + '/' + r)}/. {q(new + '/' + r)}/ && echo 'carried over ./{r}'; fi\n"
                for r in keep_dirs) if reloc else "")],
    )
    # 4: repo files into the (new) dir
    for rel, secret in s.files.items():
        files.put(
            name=f"{name}: {rel}",
            src=str(s.local / rel),
            dest=f"{new}/{rel}",
            mode="600" if rel == ".env" else None,
        )
    if no_up:
        server.shell(
            name=f"{name}: left down (--no-up); check moved paths",
            commands=["set -eu\n" + "".join(
                f"[ -e {q(mv['dst'])} ] && echo 'ok {mv['dst']}' || {{ echo 'MISSING {mv['dst']}'; exit 1; }}\n"
                for mv in moves) or "true"],
        )
        continue
    # 5: up + verify
    server.shell(
        name=f"{name}: up -d --pull missing, verify",
        commands=[f"""set -eu
cd {q(new)} && docker compose -p {n} {compose_args(new_cfg)} up -d --pull missing
sleep 5
docker ps -a --filter label=com.docker.compose.project={n} --format '{{{{.Names}}}} {{{{.State}}}} {{{{.Status}}}}'
for c in $(docker ps -aq --filter label=com.docker.compose.project={n}); do
  docker inspect -f '{{{{range .Mounts}}}}{{{{if eq .Type "bind"}}}}{{{{.Source}}}}{{{{"\\n"}}}}{{{{end}}}}{{{{end}}}}' "$c"
done | sort -u | while read -r src; do
  [ -n "$src" ] || continue
  for d in {q(old)} {q(new)}; do
    case "$src" in
      "$d"/*) rel="${{src#"$d"/}}"
        case " {' '.join(m['keep_relative'])} " in
          *" $rel "*) ;;
          *) echo "DATA STILL IN STACK DIR: $src"; exit 1 ;;
        esac ;;
    esac
  done
  [ -e "$src" ] || {{ echo "MISSING mount source: $src"; exit 1; }}
  echo "mount ok: $src"
done
"""],
    )
