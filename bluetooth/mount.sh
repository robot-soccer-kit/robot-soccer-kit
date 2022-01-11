#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
filter=`cat $SCRIPT_DIR/filter`


echo "Unbinding all devices"
for id in /dev/rfcomm*;
do
    sudo rfcomm unbind $id
done

echo "Retrieving devices..."
uids=`echo "paired-devices" | bluetoothctl | grep ^Device | grep $filter | cut -d" " -f2 | uniq | sort`
k=0

for uid in $uids;
do
    echo "Binding $uid to /dev/rfcomm$k"
    sudo rfcomm bind $k $uid
    k=$[$k+1]
done


