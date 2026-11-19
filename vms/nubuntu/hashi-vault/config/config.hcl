ui = true
disable_mlock = "true"

storage "raft" {
  path    = "/vault/data"
  node_id = "node1"
}

listener "tcp" {
  address = "[::]:8200"
  tls_disable = "true"
}

cluster_addr = "http://127.0.0.1:8200"
api_addr = "http://127.0.0.1:8201"
