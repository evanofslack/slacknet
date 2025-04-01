# hubble.peerService.clusterDomain matches cluster name defined for talos + local. prefix
helm install cilium cilium/cilium --version 1.17.2 \
    --namespace kube-system \
    --set=ipam.mode=kubernetes \
    --set=kubeProxyReplacement=true \
    --set=hostFirewall.enabled=false \
    --set=hubble.relay.enabled=true \
    --set=hubble.ui.enabled=true \
    --set=hubble.peerService.clusterDomain=local.slacknet \
    --set=securityContext.capabilities.ciliumAgent="{CHOWN,KILL,NET_ADMIN,NET_RAW,IPC_LOCK,SYS_ADMIN,SYS_RESOURCE,DAC_OVERRIDE,FOWNER,SETGID,SETUID}" \
    --set=securityContext.capabilities.cleanCiliumState="{NET_ADMIN,SYS_ADMIN,SYS_RESOURCE}" \
    --set=cgroup.autoMount.enabled=false \
    --set=cgroup.hostRoot=/sys/fs/cgroup \
    --set=k8sServiceHost=localhost \
    --set=k8sServicePort=7445

helm template \
    cilium \
    cilium/cilium \
    --version 1.17.2 \
    --namespace kube-system \
    --set ipam.mode=kubernetes \
    --set kubeProxyReplacement=true \
    --set hubble.relay.enabled=true \
    --set hubble.ui.enabled=true \
    --set securityContext.capabilities.ciliumAgent="{CHOWN,KILL,NET_ADMIN,NET_RAW,IPC_LOCK,SYS_ADMIN,SYS_RESOURCE,DAC_OVERRIDE,FOWNER,SETGID,SETUID}" \
    --set securityContext.capabilities.cleanCiliumState="{NET_ADMIN,SYS_ADMIN,SYS_RESOURCE}" \
    --set cgroup.autoMount.enabled=false \
    --set cgroup.hostRoot=/sys/fs/cgroup \
    --set k8sServiceHost=localhost \
    --set k8sServicePort=7445 >cilium.yaml
