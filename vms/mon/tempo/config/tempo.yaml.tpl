server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        http:
        grpc:

ingester:
  max_block_duration: 30m

metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /tmp/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
        send_exemplars: true

storage:
  trace:
    backend: s3
    s3:
      bucket: eslack-tempo
      endpoint: s3.wasabisys.com
      region: us-east-1
      access_key: {{ op://Homelab/mon-tempo/S3_ACCESS_KEY }}
      secret_key: {{ op://Homelab/mon-tempo/S3_SECRET_KEY }}

    wal:
      path: /tmp/tempo/wal

overrides:
  metrics_generator_processors: [service-graphs, span-metrics] # enables metrics generator
