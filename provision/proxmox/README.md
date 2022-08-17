# Proxmox Provisioning

## API Token Setup

API token must not have priviledge seperation

```bash
pveum role add TerraformProv -privs "VM.Allocate VM.Clone VM.Config.CDROM VM.Config.CPU VM.Config.Cloudinit VM.Config.Disk VM.Config.HWType VM.Config.Memory VM.Config.Network VM.Config.Options VM.Monitor VM.Audit VM.PowerMgmt Datastore.AllocateSpace Datastore.Audit"
```

```bash
pveum user add terraform-prov@pve --password <password>
```

```bash
pveum aclmod / -user terraform-prov@pve -role TerraformProv
```

## Expand VM Disk

In your VM instance setting, click on the disk then increase the capacity by the amount you need.

Grow the partition:

```bash
sudo growpart /dev/sda 1
```
Resize the file system:

```bash
sudo resize2fs /dev/sda1
```

Verify:
```bash
df -h
```
