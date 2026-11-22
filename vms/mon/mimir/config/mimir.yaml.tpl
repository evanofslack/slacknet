# Do not use this configuration in production.
# It is for demonstration purposes only.
# Run Mimir in single process mode, with all components running in 1 process.
target: all,alertmanager,overrides-exporter

common:
  storage:
    backend: s3
    s3:
      endpoint: 10.33.1.242:9000
      region: us-east-1
      access_key_id: {{ op://Homelab/mon-mimir/S3_ACCESS_KEY_ID }}
      secret_access_key: {{ op://Homelab/mon-mimir/S3_SECRET_ACCESS_KEY }}
      insecure: true
      bucket_name: mimir

blocks_storage:
  storage_prefix: blocks
  tsdb:
    dir: /data/ingester

memberlist:
  join_members: [mimir-1, mimir-2, mimir-3]

ruler:
  rule_path: /data/ruler
  alertmanager_url: http://127.0.0.1:8080/alertmanager
  ring:
    heartbeat_period: 2s
    heartbeat_timeout: 10s

alertmanager:
  data_dir: /data/alertmanager
  fallback_config_file: /etc/alertmanager-fallback-config.yaml
  external_url: http://localhost:9009/alertmanager

server:
  log_level: info

usage_stats:
  enabled: false

limits:
  max_label_names_per_series: 50
