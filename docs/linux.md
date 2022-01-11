# Linux: instructions and troubleshoot

## Pairing the robots

To pair the robots, you can run:

```
./bluetooth/pair.sh
```

Then, wait for your robots to be detected

## Mounting the robots

Once you paired your robots, you can run:

```
./bluetooth/mount.sh
```

To mount them all as `/dev/rfcomm*` devices

## Removing robots

If you want to clean up your paired devices, you can use:

```
./bluetooth/remove-all.sh
```

To remove all paired devices.