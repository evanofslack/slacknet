# Slacknet

My homelab kubernetes cluster managed declaratively with gitops.

## Overview

At its core, this is a [k3s](https://k3s.io) cluster running on [proxmox](https://www.proxmox.com/en/) virtual machines. VMs are created with [Terraform](https://www.terraform.io) from [cloud-init](https://cloud-init.io/) Ubuntu images, provisioned with [Ansible](https://www.ansible.com), and managed with [Flux](https://toolkit.fluxcd.io/).

## Applications

The following applications are deployed on the k3s cluster.

 *System*
- [flux](https://toolkit.fluxcd.io/)
- [kube-vip](https://kube-vip.io/)
- [vertical-pod-autoscaler](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [metrics-server](https://github.com/kubernetes-sigs/metrics-server)
- [reflector](https://github.com/emberstack/kubernetes-reflector)
- [reloader](https://github.com/stakater/Reloader)
- [descheduler](https://github.com/kubernetes-sigs/descheduler)
- [kured](https://github.com/weaveworks/kured)
- [system-upgrade](https://github.com/rancher/system-upgrade-controller)

 *Networking*
- [calico](https://www.tigera.io/project-calico/)
- [metallb](https://metallb.universe.tf/)
- [external-dns](https://github.com/kubernetes-sigs/external-dns)
- [k8s_gateway](https://github.com/ori-edge/k8s_gateway)
- [ingress-nginx](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager](https://cert-manager.io/)

 *Monitoring*
- [prometheus](https://prometheus-operator.dev/)
- [grafana](https://github.com/grafana/grafana)
- [loki](https://github.com/grafana/loki)
- [goldilocks](https://github.com/FairwindsOps/goldilocks)
- [uptime-kuma](https://github.com/louislam/uptime-kuma)

*Storage*
- [local-path-provisioner](https://github.com/rancher/local-path-provisioner)
- [longhorn](https://github.com/longhorn/longhorn)

*Database*
- [Cloudnative-Postgres](https://github.com/cloudnative-pg/cloudnative-pg)

*Development*
- [Wakapi](https://github.com/muety/wakapi)

*Home Automation*
- [Mosquitto](https://github.com/eclipse/mosquitto)

 *General*
- [hajimari](https://github.com/toboshii/hajimari)
- [echo-server](https://github.com/Ealenn/Echo-Server)
- [libre-speedtest](https://github.com/librespeed/speedtest)


### Note
Credits goes to [onedr0p](https://github.com/onedr0p) and the [k8s-at-home](https://github.com/k8s-at-home) community for k3s guides and charts.
