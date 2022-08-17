# Proxmox VM Template

Create proxmox VM templates from cloud-init images.

### Automated Script

[Guide](https://gtgb.io/2022/07/23/proxmox-vm-templating/)

Change variables in `vars` then:

```bash
sh ./build-image.sh
```

### Manual Setup

[Guide](https://docs.technotim.live/posts/cloud-init-cloud-image/)

Choose cloud image:
[Ubuntu](https://cloud-images.ubuntu.com/)

The cloud image must be downloaded onto proxmov node:

``` bash
wget https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img
```

Create new VM:

```bash
qm create 9000 --memory 2048 --core 1 --name ubuntu-cloud --net0 virtio,bridge=vmbr0
```

Import the Ubunutu disk to local-lvm storage:

```bash
qm importdisk 8000 focal-server-cloudimg-amd64.img local-lvm
```

Attach the new disk to the vm as a scsi drive on the scsi controller

```bash
qm set 8000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-8000-disk-0
```

Add cloud init drive

```bash
qm set 8000 --ide2 local-lvm:cloudinit
```

Make the cloud init drive bootable and restrict BIOS to boot from disk only

```bash
qm set 8000 --boot c --bootdisk scsi0
```

Add serial console

```bash
qm set 8000 --serial0 socket --vga serial0
```
