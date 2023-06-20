 #! /bin/bash
 for FILE in /var/lib/docker/containers/*/*-json.log
 do
     jq '.' $FILE >/dev/null || echo "CORRUPT: $FILE"
 done

 # then stop docker
 # sudo systemctl stop docker

 # and zero out corrupted file
 # cat /dev/null > /path/to/corrupted/logfile
