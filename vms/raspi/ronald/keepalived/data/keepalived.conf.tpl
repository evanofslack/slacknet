# primary instance
vrrp_instance VI_1 {
    state BACKUP
    interface eth0 # may need to alter this
    virtual_router_id 51
    priority 100
    advert_int 1
    authentication {
        auth_type PASS
        auth_pass {{ op://Homelab/ronald-keepalived/AUTH_PASS }}
    }
    virtual_ipaddress {
        10.33.1.69
    }
}
