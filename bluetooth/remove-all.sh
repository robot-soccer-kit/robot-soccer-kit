#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
filter=`cat $SCRIPT_DIR/filter`

# Retrieving devices
uids=`echo "paired-devices" | bluetoothctl | grep ^Device | grep $filter | cut -d" " -f2 | uniq | sort`

for uid in $uids;
do
    echo "Removing $uid"
    echo "remove $uid" | bluetoothctl
done


