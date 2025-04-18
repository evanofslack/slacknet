https://datavirke.dk/posts/bare-metal-kubernetes-part-1-talos-on-hetzner/

https://www.talos.dev/v1.4/introduction/getting-started/

```
talosctl gen secrets -o secrets.yaml
```

Export $CLUSTER_NAME and $CLUSTER_ENDPOINT


copy from `gen-config.sh`

Export $CONTROL1 ... $CONTROLN and $WORKER1 ... $WORKERN

then generate talosconfig

for each control
```
talosctl apply-config --insecure -n $CONTROLN --file rendered/controlplane.yaml
```


for each worker
```
talosctl apply-config --insecure -n $WORKERN --file rendered/worker.yaml
```

then bootstrap

```
talosctl bootstrap --nodes $CONTROL1 --endpoints $CONTROL1 \
    --talosconfig=./talosconfig
```

generate k8s config

apply cilium, see /cilium

then install flux: https://fluxcd.io/flux/get-started/

export $GITHUB_USER and $GITHUB_TOKEN

then from toplevel `slacknet`

```
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=slacknet \
  --branch=main \
  --path=./clusters/cluster \
  --personal

```
