#!/usr/bin/bash

nowdate=$(date +'%y%m%d')
nowtime=$(date +'%T')

# OPTIONS
WEBHOOK=""
LOGFILE=""
FROM=""
TO=""

echo $LOGFILE

touch $LOGFILE

echo "started rsync pbs backup on $nowdate @ $nowtime" | tee -a $LOGFILE
curl -X POST -H 'Content-type: application/json' --data '{"text":"started rsync pbs backup"}' $WEBHOOK | tee -a $LOGFILE

if pidof -o %PPID -x "pbs-rsync-backup.sh"
then
        echo "failed rsync pbs backup attempt on $nowdate @ $nowtime (rclone already running)" | tee -a $LOGFILE
                curl -X POST -H 'Content-type: application/json' --data '{"text":"failed rsync pbs backup attempt (rclone already running)"}' $WEBHOOK | tee -a $LOGFILE
                        exit 1
fi

rclone sync $FROM $TO -v --stats 10m --transfers=10 --log-file=$LOGFILE

enddate=$(date +'%y%m%d')
endtime=$(date +'%T')
echo "Completed backup on $enddate @ $endtime" | tee -a $LOGFILE
curl -X POST -H 'Content-type: application/json' --data '{"text":"completed rsync pbs backup"}' $WEBHOOK | tee -a $LOGFILE

# if [ -f $LOGFILE ]
# then
        # rm $LOGFILE
# fi

