variable "proxmox_api_url" {
    description = "Proxmox instance URL"
    type = string
}

variable "proxmox_api_token_id" {
    description = "Proxmox API token ID"
    type = string
    sensitive = true
}

variable "proxmox_api_token_secret" {
    description = "Proxmox API token secret"
    type = string
    sensitive = true
}

variable "pm_tls_insecure" {
  description = "Set to true to ignore certificate errors"
  type        = bool
  default     = true
}

variable "pm_node_name" {
  description = "name of the proxmox node to create the VMs on"
  type        = string
  default     = "host1"
}

variable "pvt_key" {
  description = "private key file"
  type        = string
  default     = "none"
}

variable "master_name" {
  description = "Base name for masters"
  type        = string
  default     = "master"
}

variable "num_masters" {
  description = "Enter the number of Master VMs you want"
  default = 3
}

variable "num_masters_core" {
  description = "Enter the value for the amount of cores for masters. ie. 4"
  default = "4"
}

variable "num_masters_mem" {
  description = "Enter the value for the amount of RAM for your masters. ie. 4096"
  default = "8192"
}

variable "master_disk_size" {
  description = "Enter the size of your Master node disks ie. 80G"
  type        = string
  default     = "50G"
}

variable "master_disk_type" {
  description = "What interface type are you using? ie. scsi"
  type        = string
  default     = "scsi"
}

variable "master_disk_location" {
  description = "Where do you want to store the disk on your host? ie. zfs-mirror, local, local-lvm, etc."
  type        = string
  default     = "local-lvm"
}

variable "node_name" {
  description = "Base name for worker nodes"
  type        = string
  default     = "worker"
}

variable "num_nodes" {
  description = "Enter the number of VMs you want for worker nodes."
  default = 3
}

variable "num_nodes_core" {
  description = "Enter the value for the amount of cores for worker nodes. ie. 2"
  default = "2"
}

variable "num_nodes_mem" {
  description = "Enter the value for the amount of RAM for your worker nodes. ie. 2048"
  default = "4096"
}

variable "node_disk_size" {
  description = "Enter the size of your worker node disks ie. 80G"
  type        = string
  default     = "50G"
}

variable "node_disk_type" {
  description = "What interface type are you using? ie. scsi"
  type        = string
  default     = "scsi"
}

variable "node_disk_location" {
  description = "Where do you want to store the disk on your host? ie. zfs-mirror, local, local-lvm, etc."
  type        = string
  default     = "local-lvm"
}

variable "template_vm_name" {
  description = "Name of the template VM"
  type        = string
  default     = "ubuntu-cloud-focal"
}

variable "master_ips" {
  description = "List of ip addresses for master nodes"
  type        = list(string)
  default     = [
  "10.33.1.200",
  "10.33.1.201",
  "10.33.1.202"
  ]
}

variable "worker_ips" {
  description = "List of ip addresses for worker nodes"
  type        = list(string)
  default     = [
    "10.33.1.203",
    "10.33.1.204",
    "10.33.1.205",
  ]
}

variable "networkrange" {
  description = "Enter as 8,16,22,24,etc. hint: 10.0.0.0/8"
  default = 24
}

variable "gateway" {
  description = "Enter your network gateway."
  default = "10.33.1.1"
}
