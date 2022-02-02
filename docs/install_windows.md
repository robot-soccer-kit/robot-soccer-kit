# Windows: install and setup

## Installing Python

You need to have Python version 3.8 or newer.

* You can install Python from the Windows Store
* Or download the [installer for Python 3.9](https://www.python.org/ftp/python/3.9.0/python-3.9.0-amd64.exe)

## Installing `robot-soccer-kit` package

If you want to install only the client, run:

```bash
py -m pip install -U robot-soccer-kit
```

If you also want the game controller:

```bash
py -m pip install -U robot-soccer-kit[gc]
```

## Running the Game Controller

To run the game controller: enter the following command:

```bash
py -m rsk.game_controller
```

## Pairing the robots

We recommend using USB external [ZEXMTE Bluetooth adapter](https://www.amazon.fr/gp/product/B08SC9M9K3/). On Windows,
the drivers are automatically installed from internet.

If you already have native Bluetooth on your computer, you can give it a try. If it doesn't work well, don't forget
to disable it before using the USB dongle by going to "Devices Manager".

To pair the robots, simply go to your Bluetooth menu and pair them one by one. If you encounter issues, do not hesitate
to disable and re-enable your Bluetooth.

**Note: default bluetooth PIN for robots is always 1234.**

**Note 2: You will NOT have to pair the robots again after each restart of your computer, only if you bring in new
robots.**

## Camera

Simply plug the camera on your computer's USB, it should work natively.