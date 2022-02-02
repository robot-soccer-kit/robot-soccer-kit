# Game Controller and Python API

## Install

* [Install and setup on Windows](install_windows.md)
* [Install and setup on Linux](install_linux.md)

## Game controller

### Starting

Once you've installed the Python package, paired the robots and the camera, you can start the game controller. You
should see such a message appearing:

```
[INFO] 2022-02-02 15:49:54,117 - robot-soccer-kit - Starting robot-soccer-kit Game Controller
[INFO] 2022-02-02 15:49:54,119 - waitress - Serving on http://127.0.0.1:7070
```

Meaning that the game controller is now running and serving at a local web server on port 7070. If it is not already
opened, a browser should appear with the game controller's interface:

![](/docs/imgs/game_controller.png)

### Configuring vision

To configure the vision, first select your camera in the list. If you plug/unplug new cameras while the software is
running, press "Refresh cameras" button.

Once you've selected the camera, click "Start" to start the capture.

You can adjust several parameters vision using the interface. The image will be annotated with the output from the
detection.

For good games quality, you should aim at reaching about 30 FPS for detection.

### Configuring robots

First, add your COM ports in the manager and just wait to check if the robots are responding. When they do, they emit
a small beep and their battery level becomes available in the interface.

You can then assign them the corresponding marker, or alternatively click the "Identify" button that will get them
moving a little bit to auto-assign the markers to them.

### Allowing API control

In the "Control" tab, you can allow or disallow the control of robots through API/clients (see below). By default, the
control boxes are ticked, allowing the control for both teams.

If you fill the "key" field with a value, it will become a key (a password) required by the teams that want to control
their robots (preventing teams to control opponent robots).

If you press the "emergency" button, all the robots will stop moving, and the control boxes will be un-ticked
automatically to prevent the clients to send some controls for the robot.

## Programming

### Getting started

Here is simple example creating a client for the API and getting the robot green1 kicking:

```python
import rsk

with rsk.Client() as client:
    client.green1.kick()
```

Here:

* `import rsk` imports the relevant Python package
* The `with` statement ensures that the client will be properly closed at the end of the session.
  Especially, it forces the robots to stop moving at the end of the program.
* `client.green1.kick()` asks the robot `green1` to kick

When creating a client, you can also provide the following arguments:

```python
import rsk

with rsk.Client(host='127.0.0.1', 
                key='') as client:
    client.robots['green'][1].kick()

```

Where

* `host` is the IP address of the computer running the Game Controller
* `key` is the team access key (by default, blank) that can be set in the Game Controller to prevent a team from
  controlling opponents robots

### Accessing robots

Robots can be accessing using the following syntax:

```python
# Shortcuts to access a robot
client.green1
client.green2
client.blue1
client.blue2

# Full syntax allowing dynamic access
client.robots['green'][1]
client.robots['green'][2]
client.robots['blue'][1]
client.robots['blue'][2]
```

### Localization informations

Localization is polled using a thread and can be continuously accessed through the following variables:

```python
# Robot position (x [m], y [m]):
client.green1.position
# Robot orientation (theta [rad]):
client.green1.orientation
# Position + orientation (x [m], y [m], theta [rad])
client.green1.pose
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
# y speed [m/s] and rotation speed [rad/s]

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
