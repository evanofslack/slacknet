# Reconcile status

Goal: make `vms/` describe what actually runs on every host, with secrets in
1Password, then make the hosts match `vms/`.

| Pass | What | State |
|---|---|---|
| 1 | host → git: import real state, move secrets to 1Password | **done** on `reconcile/pass1` (not merged) |
| 2 | git → host: hosts run from the repo, `.env` rendered from 1Password | not started |
| 3 | drift check on a schedule | not started |

Last inventory: 2026-11-15. Nothing on any host was changed by pass 1.

## Hosts

| Host | repo path | Ran from | Notes |
|---|---|---|---|
| mon | `vms/mon` | `~/slacknet` clone | local edits imported; k6, portainer, quickwit archived on host |
| gateway | `vms/gateway` | clone | caddy imported; authentik, nginx, dockerproxy, portainer archived on host |
| joule | `vms/joule` | clone | 3 exporters still run from the old `vms/joules/` path |
| nubuntu | `vms/nubuntu` | clone + `~/docker` | ~30 stacks imported; caddy, esphome, flame, hoarder, homebridge, homepage, rundeck archived on host |
| dorp | `vms/dorp` | clone (dir not in `main`) | all stacks new to the repo; go-poker pending (see below) |
| torrr | `vms/torrr` | `~/docker` | all 26 stacks new to the repo |
| racknerd | `vms/racknerd` | `~/docker` | public VPS; all stacks new to the repo |
| ralph | `vms/raspi/ralph` | clone | 5 stacks still run from the old `vms/raspi/<app>` path |
| ronald | `vms/raspi/ronald` | clone | keepalived, homebridge imported |
| ved, kubuntu | `vms/ved`, `vms/kubuntu` | — | not in the inventory (off / retired) |

Stacks the hosts had moved into a local `archive/` dir are in `vms/archive/<host>/<app>`.

## Secrets

- 1Password vault **Homelab**, one Secure Note per stack, titled from the path:
  `vms/nubuntu/immich` → `nubuntu-immich`, `vms/raspi/ralph/nut` → `ralph-nut`,
  `vms/archive/gateway/convoy` → `archive-gateway-convoy`.
- Each stack with secrets has a committed `.env.tpl`; plain settings are inline,
  secrets are `{{ op://Homelab/<item>/<KEY> }}`. Render with
  `op inject -i .env.tpl -o .env` (`.env` is gitignored everywhere).
- Literal secrets in compose files were replaced by `${KEY}`, with `KEY` in `.env.tpl`.
- App config files with secrets became `<file>.tpl`, with the rendered file
  gitignored: `vms/torrr/recyclarr/config/secrets.yml`,
  `vms/nubuntu/pve-exporter/config/pve.yaml`.
- Verified per stack: the rendered `.env` equals the host's `.env`, and
  `docker compose config` is identical before and after the rewrite.

## Needs attention

1. **Don't `git pull` + `docker compose up` on a host after merging, until pass 2.**
   Compose files now use `${KEY}` where values used to be hardcoded; without a
   rendered `.env` those containers start with empty secrets.
2. **go-poker (dorp) is not committed yet.** The host's own `vms/dorp/.gitignore`
   listed it, so the first import missed it. It's imported in the working tree
   (with the ignore line removed), but its compose still hardcodes
   `DATABASE_URL` and `POSTGRES_PASSWORD`. 1Password authorization timed out.
   Finish with:
   ```sh
   cd ops && uv run --no-env-file python reconcile/secrets.py --apply --only vms/dorp/go-poker
   git add vms/dorp/.gitignore vms/dorp/go-poker && git commit
   ```
3. **Uncommitted edits in the main checkout conflict with this branch:**
   `vms/nubuntu/caddy/Caddyfile` (the host archived nubuntu's caddy) and
   `vms/raspi/ralph/adguard/conf/AdGuardHome.yaml` (the branch has the host's
   version; the main checkout has different upstream DNS). Decide which wins before merging.
4. **Secrets already in git history** (from before this work); rotate if still in use:
   - `provision/talos/cilium/cilium.yaml`: private keys / k8s secrets (3 commits)
   - `vms/mon/grafana/docker-compose.yaml`: an API key in an older version
   - AdGuard `users[].password` bcrypt hashes are still tracked in
     `vms/raspi/*/adguard/conf/AdGuardHome.yaml` (AdGuard rewrites this file itself).
5. **Running ≠ file on disk** (compose config-hash differs: edited but never
   `up`'d, or a compose version change). `up` in pass 2 will recreate these;
   review the diff first:
   - dorp: analogdb, analogdb-consumer, analogdb-web, go-poker, kafka-ui, otel, pastebnn, samila, watchtower, weaviate-ui
   - torrr: cadvisor, gluetun-qbittorrent, navidrome, podgrab, whisparr
   - nubuntu: expanse, immich, paperless-ngx
6. **pastebnn runs twice**: on dorp (`vms/dorp/pastebnn`) and on nubuntu from a
   deleted dir (`~/docker/pastebnn`). Pick one and stop the other.
7. **Orphaned containers** run from dirs that were renamed; the repo has the
   current copy at the new path. Re-`up` from the new path in pass 2:
   - joule: cadvisor, node-exporter, watchtower (`vms/joules/*` → `vms/joule/*`)
   - ralph: adguard-exporter, cadvisor, dockerproxy, node-exporter, nut-exporter
     (`vms/raspi/*` → `vms/raspi/ralph/*`)
8. **Not imported (decide: delete or recover):**
   - exited, dir deleted: nubuntu archivebox, playit, vikunja · torrr dozzle,
     jfa-go · racknerd nginx, postgres-backup-s3, analogdb-migrate · mon mimir-minio
   - dorp `analogdb`, `analogdb-consumer`: compose lives in the separate
     `analogdb` app repo cloned inside `vms/dorp/`
   - dorp's leftover `vms/ved/*` copies (incl. databend, exited)
   - `hello-world` / one-off containers on most hosts; `metabase` (dorp, outside compose)
9. **Broken / unhealthy right now:** vector-agent (mon, gateway restarting; joule,
   ronald, torrr exited), loki and tempo (mon), immich partly down (nubuntu),
   tracearr restarting (torrr), jellyfin partly exited (joule).
10. **paperless-ngx:** its `webserver` loads the whole `.env`, so it now also
    receives `POSTGRES_PASSWORD`. Harmless, but different.
11. **racknerd** (public): Ubuntu 20.04 (EOL), 2022 kernel, Docker 20.10 (EOL),
    353 days uptime. Both tailscale and zerotier installed.
12. **App state left in stack dirs** (`./data`, `./postgres`, `./config`, …) must
    move to absolute paths before deploying from a fresh checkout (pass 2).

## Tooling

All in `ops/` (`cd ops`, use `uv run --no-env-file` because the shell sets `UV_ENV_FILE`):

| Command | Does |
|---|---|
| `./collect [--limit host]` | read-only inventory of hosts → `../.inventory/<host>/` (**contains secrets, gitignored**) and a drift summary |
| `uv run --no-env-file python summarize.py [host]` | re-print the summary from the last inventory |
| `uv run --no-env-file python reconcile/import_host.py <host> [--dry-run]` | host state → `vms/` (replays clone edits, imports untracked/`~/docker` stacks; never overwrites existing repo files) |
| `uv run --no-env-file python reconcile/secrets.py [--apply] [--only vms/x]` | secrets → 1Password + `.env.tpl`, verified; plan only without `--apply` |
| `uv run --no-env-file python reconcile/template_files.py [--apply]` | secrets in specific app config files → `*.tpl` |

Host addresses live in `ops/.env` (gitignored; keys in `.env.example`), and pyinfra
authenticates through the ssh-agent.
