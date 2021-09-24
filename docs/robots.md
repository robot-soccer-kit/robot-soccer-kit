# Robots

![Holo](/docs/img/holo.png)

## Mechanics

* (TODO provide CAD) Top PMMA plate
* (TODO provide CAD) Upper marker plate
* Structural screws
    * 6x M3x35
    * 6x M3x10 female-female spacer
    * 6x M3x8 female-male spacer
    * 6x M3x15 female-male spacer

## Wheels

(TODO provide CAD)

* Bearings are V623ZZ, V shape 3x12x4mm
* O-rings, ID 8mm, 2mm thickness
* M3x6 cylindrical shaft
* Screws & nuts
    * 18x M3x8 screws
    * 18x M3 nuts
    * 9x M3x8 screws
    * 9x M3 square nuts

## PCB

Robot PCB can be found in the [/electronics/holo](/electronics/holo) directory of this repository.

**Disclaimer: robots used in SSL are a fork of a previous project (holo). Current prototypes
were hacked to add a kicker. In the future, this kicker will be integrated in the robot itself,
and other useless robot features will be removed**

## Motors

![GA12-N20](/docs/imgs/n20.png)

* Reference: GA12-N20
* Hall encoder
* Reduction ratio 1:210, metal gears
* Connector: 6-pin JST-ZH

The current reduction trade-off offers a high torque and the speed of the robots are thus limited.
This is however not an issue in adversarial game where precision counts more than velocity.

## Bluetooth communication

![HC-05](/docs/imgs/hc-05.png)

HC-05 modules are soldered on the robot PCB and allowing Bluetooth to on-board UART communication.

## Kicker

![Kicker](/docs/imgs/kicker.png)

### PCB

Kicker PCB can be found in the [/electronics/kicker](/electronics/kicker) directory of this repository.

It features MT3608 step-up converter to load a bank of capacitors that can then be unloaded in the
solenoid.

### Solenoid

![Solenoid](/docs/imgs/solenoid.png)

* 6V JF-0530B
* (TODO provide CAD)
