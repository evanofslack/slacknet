talosctl apply-config --insecure -n $CONTROL --file rendered/controlplane.yaml
talosctl apply-config --insecure -n $WORKER1 --file rendered/worker.yaml
talosctl apply-config --insecure -n $WORKER2 --file rendered/worker.yaml
