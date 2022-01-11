#!/bin/bash

# Unbinding all devices
for id in /dev/rfcomm*;
do
    sudo rfcomm unbind $id
done

# Retrieving devices
uids=`echo "paired-devices" | bluetoothctl | grep ^Device | grep Holo | cut -d" " -f2 | uniq | sort`
k=0

for uid in $uids;
do
    echo "Binding $uid to /dev/rfcomm$k"
    sudo rfcomm bind $k $uid
    k=$[$k+1]
done


