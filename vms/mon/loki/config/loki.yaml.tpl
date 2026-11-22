auth_enabled: false

server:
  http_listen_port: 3100
  grpc_server_max_recv_msg_size: 8000000
  grpc_server_max_send_msg_size: 8000000
  log_level: "info"

common:
  storage:
    s3:
      endpoint: s3.wasabisys.com
      region: us-east-1
      insecure: false
      bucketnames: eslack-loki
      access_key_id: {{ op://Homelab/mon-loki/S3_ACCESS_KEY_ID }}
      secret_access_key: {{ op://Homelab/mon-loki/S3_SECRET_ACCESS_KEY }}
      s3forcepathstyle: true

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  wal:
    enabled: true
    dir: /loki/wal
  chunk_idle_period: 5m
  chunk_retain_period: 30s

ruler:
  enable_api: true
  wal:
    dir: /tmp/ruler-wal
  storage:
    type: local
    local:
      directory: /loki/rules
  rule_path: /tmp/prom-rules
  remote_write:
    enabled: true
    clients:
      local:
         url: http://prometheus:9090/api/v1/write
         queue_config:
           # send immediately as soon as a sample is generated
           capacity: 1
           batch_send_deadline: 0s

schema_config:
  configs:
    - from: 2023-05-13
      store: boltdb-shipper
      object_store: s3
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /tmp/index
    cache_location: /tmp/boltdb-cache

limits_config:
  # Enable log-volume endpoints.
  # volume_enabled: true
  # The maximum number of aggregated series in a log-volume response
  # volume_max_series: 1000
  max_cache_freshness_per_query: '10m'
  reject_old_samples: true
  reject_old_samples_max_age: 30m
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20
  # parallelize queries in 15min intervals
  split_queries_by_interval: 15m

table_manager:
  retention_deletes_enabled: true
  retention_period: 336h

query_range:
  # make queries more cache-able by aligning them with their step intervals
  align_queries_with_step: true
  max_retries: 5
  parallelise_shardable_queries: true
  cache_results: true

frontend:
  log_queries_longer_than: 5s
  compress_responses: true
  max_outstanding_per_tenant: 2048

query_scheduler:
  max_outstanding_requests_per_tenant: 1024

querier:
  query_ingesters_within: 2h

compactor:
  working_directory: /tmp/compactor

analytics:
  reporting_enabled: false
