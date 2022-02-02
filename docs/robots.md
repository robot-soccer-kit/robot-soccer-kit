# Robots

**Disclaimer: robots used in Robot Soccer Kit are a fork of a previous project (holo). Current prototypes
were hacked to add a kicker. In the future, this kicker will be integrated in the robot itself,
this is STILL A WORK IN PROGRESS**

![Holo](/docs/imgs/robots.jpg)

[The full robot CAD can be found here (OnShape)](https://cad.onshape.com/documents/c5fe05581d14c59bfb08f79e/w/a8cb82e3a358c0b06e1cbf91/e/f45372d8263c18466905bd9b?renderMode=0&uiState=616d8b41f463de7ef1eedc0f)


## Structure

* Structural screws
    * 6x M3x35
    * 6x M3x10 female-female spacer
    * 6x M3x8 female-male spacer
    * 6x M3x15 female-male spacer

## Wheels

[Wheel CAD 3D design](https://cad.onshape.com/documents/beccbfab729802507eb805eb/w/eea13ac7371464cd172aefcf/e/76e58097a54be25b6c68caca?renderMode=0&uiState=616d8c2f00cc7207a3c8ae7b)

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

### Operating

![Kicker](/docs/imgs/kicker_pcb.png)

The kicker is stepping up input voltage to approximate 20V to charge a bank of capacitors (9x 470uF rated
for 25V).

Thanks to a MOSFET transistor, the capacitors can be discharged directly in the solenoid, triggering the kicker.

The duration of the pulse in the MOSFET allows to control the power of the kick.