#!/bin/bash

# Retrieving devices
uids=`echo "paired-devices" | bluetoothctl | grep ^Device | grep Holo | cut -d" " -f2 | uniq | sort`

for uid in $uids;
do
    echo "Removing $uid"
    echo "remove $uid" | bluetoothctl
done


