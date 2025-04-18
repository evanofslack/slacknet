talosctl gen config \
    --output rendered/controlplane.yaml \
    --output-types controlplane \
    --with-secrets secrets.yaml \
    --config-patch @patch/dns.yaml \
    --config-patch @patch/disable-kube-proxy-and-cni.yaml \
    $CLUSTER_NAME \
    $CLUSTER_ENDPOINT

talosctl gen config \
    --output rendered/worker.yaml \
    --output-types worker \
    --with-secrets secrets.yaml \
    --config-patch @patch/dns.yaml \
    --config-patch @patch/disable-kube-proxy-and-cni.yaml \
    $CLUSTER_NAME \
    $CLUSTER_ENDPOINT

talosctl gen config \
    --output-types talosconfig \
    --with-secrets secrets.yaml \
    $CLUSTER_NAME \
    $CLUSTER_ENDPOINT
