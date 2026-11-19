#!/usr/bin/env bash
# Read-only host inventory. Gathers host/docker state and copies small files
# from each compose project's working dir into a tarball. Changes nothing else.
#
# NOTE: output includes .env files and `docker inspect` env vars -> contains secrets.
set -u

OUT_TAR="${1:-/tmp/slacknet-inventory.tar.gz}"
MAX_FILE_SIZE="256k"   # skip anything bigger (db files, media, models)
MAX_FILES=2000         # per-project cap so a data dir can't explode the tarball
# Directory names never descended into (database/state storage).
PRUNE_NAMES=(.git node_modules postgres postgres-data pgdata mysql mariadb-aria
  loki tempo-data quickwit-data qwdata work media model-cache upload library
  cache transcodes letsencrypt)

WORK="$(mktemp -d /tmp/slacknet-inv.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
D="$WORK/inv"
mkdir -p "$D/projects"

section() { echo; echo "=== $1 ==="; }

# ---------------------------------------------------------------- host
{
  section "Host"
  hostname -f 2>/dev/null || hostname
  date -Is
  uname -a
  grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release 2>/dev/null
  uptime

  section "IPv4 addresses"
  ip -brief -4 address show scope global 2>/dev/null || echo "ip unavailable"

  section "Disk"
  df -hT -x tmpfs -x devtmpfs -x overlay -x squashfs 2>/dev/null

  section "Listening TCP ports"
  ss -tlnH 2>/dev/null | awk '{print $4}' | sort -u

  section "Running systemd services"
  systemctl list-units --type=service --state=running --no-legend --plain 2>/dev/null | awk '{print $1}'

  section "Crontabs"
  echo "# user ($(id -un))"; crontab -l 2>/dev/null || echo "(none)"
  echo "# /etc/cron.d"; ls -1 /etc/cron.d 2>/dev/null
} > "$D/host.txt" 2>&1

# ---------------------------------------------------------------- docker
if ! command -v docker >/dev/null 2>&1; then
  echo "docker not installed" > "$D/docker-unavailable.txt"
elif ! docker info >/dev/null 2>&1; then
  echo "docker daemon unavailable or permission denied" > "$D/docker-unavailable.txt"
else
  docker version --format '{{.Server.Version}}' > "$D/docker-version.txt" 2>&1
  docker compose version --short >> "$D/docker-version.txt" 2>&1
  docker compose ls --all --format json > "$D/compose-ls.json" 2>/dev/null || echo "[]" > "$D/compose-ls.json"
  docker ps --all --no-trunc --format '{{json .}}' > "$D/containers.jsonl"
  ids="$(docker ps -aq)"
  if [ -n "$ids" ]; then docker inspect $ids > "$D/inspect.json"; else echo "[]" > "$D/inspect.json"; fi
  docker network ls --format '{{json .}}' > "$D/networks.jsonl"
  docker volume ls --format '{{json .}}' > "$D/volumes.jsonl"
  docker image ls --format '{{json .}}' > "$D/images.jsonl"
fi

# Compose files on disk that may not be running (stopped/stale stacks).
find "$HOME" /opt /srv -maxdepth 5 \
  \( -name node_modules -o -name .git -o -name postgres -o -name data \) -prune -o \
  -type f \( -name 'docker-compose.y*ml' -o -name 'compose.y*ml' \) -print \
  2>/dev/null | sort > "$D/compose-files-on-disk.txt"

# ---------------------------------------------------------------- projects
prune_expr=()
for n in "${PRUNE_NAMES[@]}"; do prune_expr+=(-name "$n" -o); done
prune_expr+=(-false)

python3 - "$D/compose-ls.json" <<'PY' > "$WORK/projects.tsv"
import json, os, sys
try:
    projects = json.load(open(sys.argv[1]))
except Exception:
    projects = []
for p in projects:
    files = [f for f in p.get("ConfigFiles", "").split(",") if f]
    wd = os.path.dirname(files[0]) if files else ""
    print("\t".join([p.get("Name", ""), p.get("Status", ""), wd, ",".join(files)]))
PY

while IFS=$'\t' read -r name status wd cfgs; do
  [ -n "$name" ] || continue
  P="$D/projects/$name"
  mkdir -p "$P/files"
  {
    echo "name=$name"
    echo "status=$status"
    echo "working_dir=$wd"
    echo "config_files=$cfgs"
  } > "$P/meta.txt"

  if [ -z "$wd" ] || [ ! -d "$wd" ]; then
    echo "working_dir_missing=true" >> "$P/meta.txt"
    continue
  fi

  # Is the working dir inside a git checkout? (record state, don't change it)
  if top="$(git -C "$wd" rev-parse --show-toplevel 2>/dev/null)"; then
    {
      echo "git_toplevel=$top"
      echo "git_head=$(git -C "$top" rev-parse HEAD 2>/dev/null)"
      echo "git_branch=$(git -C "$top" rev-parse --abbrev-ref HEAD 2>/dev/null)"
      echo "git_remote=$(git -C "$top" remote get-url origin 2>/dev/null)"
    } >> "$P/meta.txt"
    git -C "$wd" status --porcelain -- . > "$P/git-status.txt" 2>&1
    echo "$top" >> "$WORK/toplevels.txt"
  fi

  # Drift check: hash of compose files on disk vs hash the running containers
  # were created from. A mismatch = file edited but never `up`'d (or older compose).
  fargs=()
  IFS=',' read -ra cf <<< "$cfgs"
  for f in "${cf[@]}"; do [ -f "$f" ] && fargs+=(-f "$f"); done
  if [ "${#fargs[@]}" -gt 0 ]; then
    (cd "$wd" && docker compose -p "$name" "${fargs[@]}" config --hash '*') \
      2> "$P/config-hash-err.txt" | sort > "$P/config-hash-files.txt"
  fi
  docker ps -a --filter "label=com.docker.compose.project=$name" \
    --format '{{.Label "com.docker.compose.service"}} {{.Label "com.docker.compose.config-hash"}}' \
    | sort -u > "$P/config-hash-running.txt"

  # Shape of the dir (including pruned data dirs, without descending).
  find "$wd" -maxdepth 2 -printf '%y %10s %P\n' 2>/dev/null | sort -k3 > "$P/tree.txt"

  # Small files, preserving relative paths. Unreadable files are listed, not fatal.
  (
    cd "$wd" || exit 0
    find . \( "${prune_expr[@]}" \) -prune -o -maxdepth 4 -type f -size -"$MAX_FILE_SIZE" -print 2>/dev/null \
      | head -n "$MAX_FILES" \
      | while IFS= read -r f; do
          if [ -r "$f" ]; then
            mkdir -p "$P/files/$(dirname "$f")"
            cp -p "$f" "$P/files/$f"
          else
            echo "$f" >> "$P/unreadable.txt"
          fi
        done
  )
done < "$WORK/projects.tsv"

# ---------------------------------------------------------------- git clones
# For each checkout a project runs from: exact local edits vs its own HEAD.
if [ -f "$WORK/toplevels.txt" ]; then
  sort -u "$WORK/toplevels.txt" | while IFS= read -r top; do
    C="$D/clones/$(echo "$top" | tr '/' '_')"
    mkdir -p "$C"
    {
      echo "path=$top"
      echo "head=$(git -C "$top" rev-parse HEAD 2>/dev/null)"
      echo "branch=$(git -C "$top" rev-parse --abbrev-ref HEAD 2>/dev/null)"
      echo "remote=$(git -C "$top" remote get-url origin 2>/dev/null)"
      echo "head_date=$(git -C "$top" log -1 --format=%cI 2>/dev/null)"
    } > "$C/meta.txt"
    git -C "$top" status --porcelain > "$C/status.txt" 2>&1
    git -C "$top" diff HEAD --binary 2>/dev/null | head -c 20000000 > "$C/diff.patch"
    git -C "$top" ls-files --others --exclude-standard > "$C/untracked.txt" 2>/dev/null
    # Copy small untracked files (skipping data dirs) so new stacks can be imported.
    n=0
    while IFS= read -r f; do
      skip=""
      for d in "${PRUNE_NAMES[@]}" data postgres-data; do
        case "/$f" in */"$d"/*) skip=1; break;; esac
      done
      [ -n "$skip" ] && continue
      src="$top/$f"
      [ -f "$src" ] && [ -r "$src" ] || continue
      [ "$(stat -c%s "$src" 2>/dev/null || echo 999999999)" -lt 262144 ] || continue
      mkdir -p "$C/untracked/$(dirname "$f")"
      cp -p "$src" "$C/untracked/$f"
      n=$((n+1)); [ "$n" -ge 3000 ] && break
    done < "$C/untracked.txt"
  done
fi

tar -czf "$OUT_TAR" -C "$WORK" inv
chmod 600 "$OUT_TAR"
echo "wrote $OUT_TAR ($(du -h "$OUT_TAR" | cut -f1))"
