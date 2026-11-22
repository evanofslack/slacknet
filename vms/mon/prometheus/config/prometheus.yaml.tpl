global:
  scrape_interval: 15s
  scrape_timeout: 10s
  evaluation_interval: 1m
  external_labels:
    cluster: slacknet
    namespace: slacknet

alerting:
  alertmanagers:
    - follow_redirects: true
      enable_http2: true
      scheme: http
      timeout: 10s
      api_version: v2
      static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - /etc/prometheus/rules.yaml

scrape_configs:
  - job_name: raspi
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.98:9100
          - 10.33.1.98:9101
          - 10.33.1.98:9102

  - job_name: torrr
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.23:9100
          - 10.33.1.23:9101

  - job_name: mon
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.212:9100
          - 10.33.1.212:9101

  - job_name: nubuntu
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:9100
          - 10.33.1.114:9101

  - job_name: gateway
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.24:9100
          - 10.33.1.24:9101

  - job_name: ved
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.142:9100
          - 10.33.1.142:9101

  - job_name: dorp
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.143:9100
          - 10.33.1.143:9101

  - job_name: joule
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.168:9100
          - 10.33.1.168:9101

  - job_name: racknerd
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.24:9598 #gateway vector sink from racknerd

  - job_name: nut
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    relabel_configs:
      - source_labels: [__address__]
        separator: ;
        regex: (.*)
        target_label: __param_target
        replacement: $1
        action: replace
      - source_labels: [__param_target]
        separator: ;
        regex: (.*)
        target_label: instance
        replacement: $1
        action: replace
      - separator: ;
        regex: (.*)
        target_label: __address__
        replacement: 10.33.1.98:9995
        action: replace
    static_configs:
      - targets:
          - 10.33.1.98:3493

  - job_name: prometheus
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - localhost:9090

  - job_name: mimir
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - mimir-1:8080
        labels:
          pod: mimir-1
      - targets:
          - mimir-2:8080
        labels:
          pod: mimir-2
      - targets:
          - mimir-3:8080
        labels:
          pod: mimir-3

  - job_name: vector
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - vector:9598

  - job_name: loki
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - loki:3100

  - job_name: unifipoller
    scrape_interval: 30s
    scrape_timeout: 10s
    metrics_path: /metrics
    static_configs:
      - targets:
        - unifi-poller:9130

  - job_name: pve-ms01
    honor_timestamps: true
    params:
      module:
        - default
      node:
        - "1"
      cluster:
        - "0"
      target:
        - 10.33.10.10
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /pve
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:9221

  - job_name: pve-ms02
    honor_timestamps: true
    params:
      module:
        - default
      node:
        - "1"
      cluster:
        - "0"
      target:
        - 10.33.10.11
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /pve
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:9221

  - job_name: pve-ms03
    honor_timestamps: true
    params:
      module:
        - default
      node:
        - "1"
      cluster:
        - "0"
      target:
        - 10.33.10.12
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /pve
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:9221

  - job_name: pve-navi-node-exporter
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:9100

  - job_name: exportarr
    honor_timestamps: true
    scrape_interval: 1m
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.23:9707
          - 10.33.1.23:9708
          - 10.33.1.23:9709

  - job_name: transmission
    honor_timestamps: true
    scrape_interval: 1m
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.23:19091

  - job_name: caddy
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:2019

  - job_name: hass
    honor_timestamps: true
    scrape_interval: 30s
    scrape_timeout: 10s
    metrics_path: /api/prometheus
    scheme: http
    authorization:
      type: Bearer
      credentials: {{ op://Homelab/mon-prometheus/HASS_TOKEN }}
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:8123

  - job_name: scale
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.212:9108
    metric_relabel_configs:
      - source_labels: [__name__]
        target_label: __name__
        replacement: truenas_$1

  - job_name: minio-cluster
    bearer_token: {{ op://Homelab/mon-prometheus/MINIO_CLUSTER_TOKEN }}
    metrics_path: /minio/v2/metrics/cluster
    scheme: http
    static_configs:
      - targets:
          - 10.33.1.242:9000

  - job_name: minio-bucket
    bearer_token: {{ op://Homelab/mon-prometheus/MINIO_BUCKET_TOKEN }}
    metrics_path: /minio/v2/metrics/bucket
    scheme: http
    static_configs:
      - targets:
          - 10.33.1.242:9000

  - job_name: minio-resource
    bearer_token: eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJwcm9tZXRoZXVzIiwic3ViIjoiZEhRUG9WU0JTaTAyRmFKV3FsRnUiLCJleHAiOjQ4ODE1ODI3Mzd9.TcO5pStGBtIvE0SvIOf_CvKCUNVuGFFHSEdIf1ZppJK9MhUOCvtpDZo2oMTse_ImljObxfwfwOjGwNExc3bPtQ
    metrics_path: /minio/v2/metrics/resource
    scheme: http
    static_configs:
      - targets:
          - 10.33.1.242:9000

  - job_name: bambulab-exporter
    scheme: http
    static_configs:
      - targets:
          - 10.33.1.212:9091

  - job_name: ceph
    scheme: http
    honor_labels: true
    static_configs:
      - targets:
          - 10.33.32.10:9283
          - 10.33.32.11:9283
          - 10.33.32.12:9283

  - job_name: analogdb
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.143:9091

  - job_name: analogdb-weaviate
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.143:2112

  - job_name: rustfs
    honor_timestamps: true
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
    scheme: http
    follow_redirects: true
    enable_http2: true
    static_configs:
      - targets:
          - 10.33.1.114:8889

remote_write:
  - url: http://mimir-gateway:9010/api/v1/push
    remote_timeout: 30s
    headers:
      X-Scope-OrgID: slacknet
    follow_redirects: true
    enable_http2: true
    queue_config:
      capacity: 2500
      max_shards: 200
      min_shards: 1
      max_samples_per_send: 500
      batch_send_deadline: 5s
      min_backoff: 30ms
      max_backoff: 5s
    metadata_config:
      send: true
      send_interval: 1m
      max_samples_per_send: 500
