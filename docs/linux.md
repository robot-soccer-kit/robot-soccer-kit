# Linux: instructions and troubleshoot

## Connecting to robots

### 1: Pair the robots

If you don't have a bluetooth manager, install `blueman`, pair the robots (pin code is usually `1234`)

### 2: Add your user to the `dialout` group

To be sure you can open serial (and rfcomm) ports, add your user to the `dialout` group:

```
adduser my_username dialout
```

### 3: Collect the robots Bluetooth addresses

Run:

```
bluetoothctl
```

And then:

```
paired-devices
```

You should see something similar to:

```
Device 20:18:08:30:10:44 Holo_6
Device 20:18:08:30:02:03 Holo_3
Device 20:18:08:30:10:57 Holo_0
Device 20:18:08:30:02:00 Holo_5
```

Here, you can see the MAC addresses of your robots

### 4: Create a script to bind your robots to rfcomm ports

Here is a simple example:

```bash
# bluetooth.sh
sudo rfcomm unbind 0
sudo rfcomm unbind 1
sudo rfcomm unbind 2
sudo rfcomm unbind 3

sudo rfcomm bind 0 20:18:08:30:10:57
sudo rfcomm bind 1 20:18:08:30:02:03
sudo rfcomm bind 2 20:18:08:30:02:00
sudo rfcomm bind 3 20:18:08:30:10:44
```

Simply replace the mac addresses with the one listed in step 3.
Run this script before starting the game controller.

## Missing `xcb` library when running

Here is a workaround:

```
cd /usr/lib/x86_64-linux-gnu
ln -sf libxcb-util.so.0 libxcb-util.so.1
```