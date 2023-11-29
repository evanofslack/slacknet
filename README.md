# Slacknet

My homelab kubernetes cluster managed declaratively with gitops.

## Overview

At its core, this is a [k3s](https://k3s.io) cluster and collection of standalone VMs running on [proxmox](https://www.proxmox.com/en/). VMs are created with [Terraform](https://www.terraform.io) from [cloud-init](https://cloud-init.io/) Ubuntu images, provisioned with [Ansible](https://www.ansible.com), 

K3s cluster is managed with [Flux](https://toolkit.fluxcd.io/) with encrypted secrets from Mozilla's [SOPS](https://github.com/mozilla/sops).


### Note

Credits goes to [onedr0p](https://github.com/onedr0p) and the [k8s-at-home](https://github.com/k8s-at-home) community for k3s guides.
