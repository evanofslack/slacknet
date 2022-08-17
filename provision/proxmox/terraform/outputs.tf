output "master_dhcp_ip" {
    description = "Master IP4 Addresses"
    value = proxmox_vm_qemu.proxmox_vm_master.*.default_ipv4_address
}

output "node_dhcp_ip" {
    description = "Worker IP4 Addresses"
    value = proxmox_vm_qemu.proxmox_vm_workers.*.default_ipv4_address
}
