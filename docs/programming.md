# Game Controller and Python API

## Install

### Prerequisites

You need to have Python version 3.8 newer.

* **Windows**:
    * You can install Python from the Windows Store
    * Or download the [installer for Python 3.9](https://www.python.org/ftp/python/3.9.0/python-3.9.0-amd64.exe)
* **Ubuntu**: run `sudo apt-get install python3 python3-pip`

### Installing `junior-ssl` package

`junior-ssl` is available as a package you can install using `pip`, simply run the following command:

* **Windows**: `py -m pip install -U junior-ssl`
* **Linux**: `pip install -U junior-ssl`
  * [Specific instructions and troubleshooting for Linux](linux.md)

## Game Controller

The Game Controller is a program that can be used to configure the vision, the communication with robots
and the game referee.

To run it:

* **Windows**: `py -m pip jssl.game_controller`
* **Linux**: `jssl-gc` (or `python -m jssl.game_controller`)

## Programming

### Getting started

Here is simple example creating a client for the API and getting the robot red1 kicking:

```python
import jssl

with jssl.Client() as client:
    client.red1.kick()
```

Here:

* `import jssl` imports the relevant Python package
* The `with` statement ensures that the client will be properly closed at the end of the session.
  Especially, it forces the robots to stop moving at the end of the program.
* `client.red1.kick()` asks the robot `red1` to kick

When creating a client, you can also provide the following arguments:

```python
import jssl

with jssl.Client(host='127.0.0.1', 
                key='') as client:
    client.robots['red'][1].kick()

```

Where

* `host` is the IP address of the computer running the Game Controller
* `key` is the team access key (by default, blank) that can be set in the Game Controller to prevent a team from
  controlling opponents robots

### Accessing robots

Robots can be accessing using the following syntax:

```python
# Shortcuts to access a robot
client.red1
client.red2
client.blue1
client.blue2

# Full syntax allowing dynamic access
client.robots['red'][1]
client.robots['red'][2]
client.robots['blue'][1]
client.robots['blue'][2]
```

### Localization informations

Localization is polled using a thread and can be continuously accessed through the following variables:

```python
# Robot position (x [m], y [m]):
client.red1.position
# Robot orientation (theta [rad]):
client.red1.orientation
# Position + orientation (x [m], y [m], theta [rad])
client.red1.pose
# Ball's position (x [m], y [m])
client.ball
```

The field frame is detailed in the [coordinates and markers](/docs/coordinates-markers.md) section 

Note: arrays are *numpy array*

### Controlling the robots

#### Basic commands

To control the robots, you can use the following functions:

```python
# Kicks, takes an optional power parameter between 0 and 1
robot.kick()

# Controls the robots in its own frame, arguments are x speed [m/s],
# y spoeed [m/s] and rotation speed [rad/s]

# Go forward, 0.25 m/s
robot.control(0.25, 0., 0.)

# Rotates 30 deg/s counter-clockwise
robot.control(0., 0., math.radians(30))
```

#### Goto

You can also use the `goto` method to send the robot to an arbitrary position on the field:

```python
robot.goto((0.2, 0.5, 1.2))
```

Sends the robot to the position `x=0.2`, `y=0.5` and `theta=1.2` on the field.

The second argument of `goto` is a *boolean* (`wait`, default `True`). When `wait` is `True`, the call to `goto` will
block the execution of the program until the robot reaches its destination. When `wait` is `False`, the
`goto` call will return immediately, after updating the instant velocity of the controlled robot, and return
`True` if the robot reached, `False` else.