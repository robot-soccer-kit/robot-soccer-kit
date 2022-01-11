#!/bin/bash

echo "Enabling scan, looking for new robots..."
if [ -d scan.pid ]; then
    killall -2 `cat scan.pid`
    rm scan.pid
fi
bluetoothctl scan on &
echo "$!" > scan.pid

while [ 1 ];
do
    paired=`echo "paired-devices" | bluetoothctl | grep ^Device | grep Holo | cut -d" " -f2 | uniq | sort`
    devices=`echo "devices" | bluetoothctl | grep ^Dev | grep Holo | cut -d" " -f 2`

    for device in $devices;
    do
        o=`echo "$paired"|grep $device`
        if [ "$o" == "" ]; then
            echo "Pairng with $device"
            bluetoothctl pair "$device"
        fi
    done

    sleep .5
done
