#!/usr/bin/env bash
# Back up or restore the Dagster Postgres on dorp.
# Put this in the analogdb-dagster/ folder next to docker-compose.yaml and run it from anywhere.
#
#   ./dagster-db.sh backup                 dump the db, keep a copy of the current image
#   ./dagster-db.sh list                   show backups and saved images
#   ./dagster-db.sh restore <file> [image] restore a dump, optionally roll back to a saved image
#
# Rollback after a bad upgrade:
#   ./dagster-db.sh restore backups/dagster-<ts>.dump analogdb-dagster:backup-<ts>

set -euo pipefail

cd "$(dirname "$0")"

DB_CONTAINER=dagster_postgres
IMAGE=evanofslack/analogdb-dagster:latest
BACKUP_DIR=backups

die() { echo "error: $*" >&2; exit 1; }

pg() { docker exec -i "$DB_CONTAINER" sh -c "$1"; }

active_runs() {
  pg 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM runs WHERE status IN ('"'"'QUEUED'"'"', '"'"'STARTING'"'"', '"'"'STARTED'"'"', '"'"'CANCELING'"'"')"'
}

backup() {
  docker inspect "$DB_CONTAINER" >/dev/null 2>&1 || die "$DB_CONTAINER is not running"
  mkdir -p "$BACKUP_DIR"
  local ts file saved
  ts=$(date -u +%Y%m%d-%H%M%S)
  file="$BACKUP_DIR/dagster-$ts.dump"
  saved="analogdb-dagster:backup-$ts"

  local runs
  runs=$(active_runs | tr -d '[:space:]')
  if [ "$runs" != "0" ]; then
    echo "warning: $runs run(s) queued or in progress. Wait for them before upgrading."
  fi

  echo "Dumping db to $file"
  pg 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$file"
  pg 'pg_restore --list' < "$file" > /dev/null || die "dump $file does not read back"
  echo "Dump ok, $(du -h "$file" | cut -f1)"

  if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker tag "$IMAGE" "$saved"
    echo "Saved current image as $saved"
  fi

  echo
  echo "Restore with: $0 restore $file $saved"
}

list() {
  echo "Backups:"
  ls -lh "$BACKUP_DIR" 2>/dev/null || echo "  none"
  echo
  echo "Saved images:"
  docker images analogdb-dagster --format '  {{.Repository}}:{{.Tag}}  {{.CreatedSince}}'
}

restore() {
  local file=${1:-} saved=${2:-}
  [ -n "$file" ] || die "usage: $0 restore <file> [image]"
  [ -f "$file" ] || die "no such file: $file"
  if [ -n "$saved" ]; then
    docker image inspect "$saved" >/dev/null 2>&1 || die "no such image: $saved"
  fi

  echo "This stops the Dagster webserver and daemon, drops the Dagster db and restores $file."
  [ -n "$saved" ] && echo "It also points $IMAGE back at $saved."
  read -r -p "Type restore to continue: " answer
  [ "$answer" = "restore" ] || die "cancelled"

  docker compose stop dagster_webserver dagster_daemon

  if [ -n "$saved" ]; then
    docker tag "$saved" "$IMAGE"
    echo "Tagged $saved as $IMAGE"
  fi

  pg 'dropdb -U "$POSTGRES_USER" --force --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
  pg 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < "$file"
  echo "Restored $file"

  # no pull, so compose keeps the image tagged above
  docker compose up -d dagster_webserver dagster_daemon
  echo "Started webserver and daemon. Check: docker logs dagster_webserver"
}

case "${1:-}" in
  backup) backup ;;
  list) list ;;
  restore) shift; restore "$@" ;;
  *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac

