# hohm

[hohm](https://github.com/evanofslack/hohm) replaces SUI/Flame as the nubuntu start page. It runs on
host port `5005` (same as SUI/Flame, so only one of them can run at a time) and stores everything in
`./data/config.yaml`.

`config.example.yaml` is the seed config. It's the same catalog as `docs/network/flame-dashboard.md`, grouped by host.
Once hohm is running, the live copy in `data/` is the source of truth (in-page editor, CLI, API).
Check it back in with `docker compose exec hohm /hohm config get > config.example.yaml`.

## Deploy

```sh
cd ~/slacknet/vms/nubuntu
docker compose -f sui/docker-compose.yaml down     # frees :5005 (or flame/, whichever is running)
cd hohm
mkdir -p data && cp config.example.yaml data/config.yaml
sudo chown -R 65532:65532 data
docker compose run --rm hohm validate -f /data/config.yaml
docker compose up -d
curl -s localhost:5005 | head -n 5
```

## Gateway Caddy route

```caddy
@hohm host home.local.{$DOMAIN}
handle @hohm {
    reverse_proxy {$NUBUNTU_ADDR}:5005
}
```

This takes over `home.local` from the archived Homepage route (`:3963`). Point `flame.local` at
`:5005` too if you want the old name to keep working. hohm has no auth: the gateway's
`private_ranges` check is what keeps it LAN-only.

## Icons

Most icons are the MDI names from the Flame plan, prefixed `mdi:`. Flame's `vault` and `kafka` don't exist in
MDI, so those two use `si:vault` and `si:apachekafka`. To use brand logos instead, switch any item to
`di:<name>` (dashboard-icons, fetched and cached in `data/icons/`) from the editor's icon picker.
