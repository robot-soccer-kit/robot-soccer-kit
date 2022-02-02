# Coordinates and markers

* [Field](/docs/field.pdf)
* [Field corner markers](/docs/field-markers.pdf)
* [Green team markers](/docs/green-markers.pdf)
* [Blue team markers](/docs/blue-markers.pdf)

## Field

### Building the field

You can either:

* Print the [whole field](/docs/field.pdf)
* Print only the [corner markers](/docs/field-markers.pdf) to stick them on existing field

In the second case, this is where they are placed:

![Putting markers on existing field](/docs/imgs/field-markers-explain.png)

### Coordinates

The field coordinates are the following:

![Field coordinates](/docs/imgs/field-frame.png)

The frame's origin is the middle of the field, and robots orientation are angle formed by
field x axis and front of the robot.

Roughly, the coordinates of the blue robot above will look like *(x=0.4, y=0.4, alpha=45 deg)*.

## Robots

You can print [green](/docs/green-markers.pdf) and [blue](/docs/blue-markers.pdf) markers and
place them on the robots:

![Robot markers](/docs/imgs/robots-markers-explain.png)

## Camera

The camera can be any USB camera that works with OpenCV, and it should be able to see the whole field

We recommend using [**Spedal MF920Pro, 1080p and 120° angle**](https://www.amazon.com/Spedal-Conference-Streaming-Microphone-Desktop/dp/B07TDQ8NL3)

To assemble the structure, you can use 50mm PVC pipes, and attach the camera with a Ziptie:

![Ziptie camera](/docs/imgs/camera_ziptie.png)

(here, zip tie is a 7.5 x 300mm)

## Bluetooth

We recommend using USB external [ZEXMTE Bluetooth adapter](https://www.amazon.fr/gp/product/B08SC9M9K3/)

On Linux, you might need to run the `./install.sh` script located in the [bluetooth directory](/bluetooth) of this
repository to get it working.

## Markers

Markers are ArUco 4x4, you can use tool like [this one](https://chev.me/arucogen/), printed with a scale
of 8 cm. The PDF provided previously are 1:1 scale. The ArUco ids are:

* 0: field corner 1
* 1: field corner 2
* 2: field corner 3
* 3: field corner 4
* 4: robot green 1
* 5: robot green 2
* 6: robot blue 1
* 7: robot blue 2
* 8-15: generic objects

## Ball

![Balls](/docs/imgs/balls.png)

For the ball, we use orange gold ball in PU (foam) material

## Field

The field material can be anything, but we strongly recommend that you use thick carpet. If you don't, the ball will
not be stopped enough and the game experiences will be very poor.