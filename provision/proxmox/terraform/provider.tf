terraform {
    required_version= ">= 0.13.0"
    required_providers {
        proxmox = {
            source  = "telmate/proxmox"
            version = ">=2.9.3"
        }
    }
}

provider "proxmox" {
  pm_api_url      = var.proxmox_api_url
  pm_api_token_id = var.proxmox_api_token_id
  pm_api_token_secret = var.proxmox_api_token_secret


  pm_tls_insecure = var.pm_tls_insecure
  pm_parallel     = 10
  pm_timeout      = 600
  pm_debug = true
  pm_log_enable = true
  pm_log_file   = "terraform-plugin-proxmox.log"
  pm_log_levels = {
    _default    = "debug"
    _capturelog = ""
  }
}
