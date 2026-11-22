# secondary instance
vrrp_instance VI_1 {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 200
    advert_int 1
    authentication {
        auth_type PASS
        auth_pass {{ op://Homelab/ralph-keepalived/AUTH_PASS }}
    }
    virtual_ipaddress {
        10.33.1.69
    }
}
