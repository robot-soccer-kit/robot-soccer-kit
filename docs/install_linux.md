# Linux: install and setup

## Installing Python 3

Use the following command to install python3 and pip packages manager:

```bash
sudo apt-get install python3 python3-pip
```

## Installing `robot-soccer-kit` package

If you want to install only the client, run:

```bash
# Client only
pip install -U robot-soccer-kit
```

If you also want the game controller:

```bash
# Full (with game controller)
pip install -U robot-soccer-kit[gc]
```

## Running the Game Controller

To run the game controller: enter the following command:

```bash
python -m rsk.game_controller
```

## Pairing the robots

### Installing RTL drivers

We recommend using USB external [ZEXMTE Bluetooth adapter](https://www.amazon.fr/gp/product/B08SC9M9K3/). On Linux,
it required you to install RTL driver, you can install them by cloning this repository and running:

```bash
# Requires root privilege
./bluetooth/install-rtl-driver.sh
```

### Pairing process

To pair the robots, you can run:

```bash
./bluetooth/pair.sh
```

Then, wait for your robots to be detected.

**Note: default bluetooth PIN for robots is always 1234**

### Mounting the robots

Once you paired your robots, you can run:

```bash
./bluetooth/mount.sh
```

To mount them all as `/dev/rfcomm*` devices

### Removing robots

If you want to clean up your paired devices, you can use:

```bash
./bluetooth/remove-all.sh
```

To remove all paired devices.

## Camera

Simply plug the camera on your computer's USB, it should work natively.