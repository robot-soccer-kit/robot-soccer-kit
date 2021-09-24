#!/bin/bash

VERSION=`cat version`
echo "* Version is $VERSION"
echo "* Re-building...";
make clean
make

echo "* Copying .bin and .version"
cp build/maple_mini.bin ../holobot.bin
cp version ../holobot.version
