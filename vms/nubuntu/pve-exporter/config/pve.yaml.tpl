default:
    user: prometheus@pve
    password: {{ op://Homelab/nubuntu-pve-exporter/PVE_PASSWORD }}
    # Optional: set to false to skip SSL/TLS verification
    verify_ssl: false
