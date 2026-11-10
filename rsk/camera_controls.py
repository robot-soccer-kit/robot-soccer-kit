"""
Ranges and default values of the camera controls (brightness, contrast...), as given by the camera
driver. OpenCV sets the raw values of these controls, but can't tell their ranges, that differ from
a camera to another: a value that suits a camera can give washed out colors with another one.

Only available on Linux (V4L2), with no additional dependency. On other systems, the ranges are
unknown (an empty dict is returned).
"""

import ctypes
import os
import sys

is_linux = sys.platform.startswith("linux")

# V4L2 controls (linux/v4l2-controls.h), by name of the setting of video.py
V4L2_CID_BASE = 0x00980900
V4L2_CID_CAMERA_CLASS_BASE = 0x009A0900
CONTROLS = {
    "brightness": V4L2_CID_BASE + 0,
    "contrast": V4L2_CID_BASE + 1,
    "saturation": V4L2_CID_BASE + 2,
    "gain": V4L2_CID_BASE + 19,
    # Exposure time, in 100 µs units
    "exposure": V4L2_CID_CAMERA_CLASS_BASE + 2,
}

# Anti-flicker of the camera for the lights (0: disabled, 1: 50 Hz, 2: 60 Hz), by frequency of the
# power line (0: lights that don't flicker). Only used by the automatic exposure of the camera
V4L2_CID_POWER_LINE_FREQUENCY = V4L2_CID_BASE + 24
POWER_LINE_FREQUENCIES = {0: 0, 50: 1, 60: 2}

V4L2_CTRL_FLAG_DISABLED = 0x0001


class v4l2_queryctrl(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("name", ctypes.c_char * 32),
        ("minimum", ctypes.c_int32),
        ("maximum", ctypes.c_int32),
        ("step", ctypes.c_int32),
        ("default_value", ctypes.c_int32),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 2),
    ]


class v4l2_control(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("value", ctypes.c_int32)]


def _iowr(group: str, number: int, size: int) -> int:
    # _IOWR macro of the Linux kernel (asm-generic/ioctl.h)
    return (3 << 30) | (size << 16) | (ord(group) << 8) | number


VIDIOC_QUERYCTRL = _iowr("V", 36, ctypes.sizeof(v4l2_queryctrl))
VIDIOC_S_CTRL = _iowr("V", 28, ctypes.sizeof(v4l2_control))


def set_power_line_frequency(index: int, frequency: int) -> bool:
    """
    Sets the frequency of the anti-flicker of the camera (Linux only)

    :param int index: the camera index (/dev/videoN on Linux)
    :param int frequency: the frequency of the power line (50 or 60, 0 for no flickering) [Hz]
    :return bool: whether it was set
    """
    if not is_linux or frequency not in POWER_LINE_FREQUENCIES:
        return False

    import fcntl

    try:
        fd = os.open(f"/dev/video{int(index)}", os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        control = v4l2_control(
            id=V4L2_CID_POWER_LINE_FREQUENCY,
            value=POWER_LINE_FREQUENCIES[frequency],
        )
        fcntl.ioctl(fd, VIDIOC_S_CTRL, control)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def query_controls(index: int) -> dict:
    """
    Ranges and default values of the controls of a camera

    :param int index: the camera index (/dev/videoN on Linux)
    :return dict: setting name => {"min", "max", "step", "default"}, only for the controls the
        camera has (empty if unknown)
    """
    if not is_linux:
        return {}

    import fcntl

    try:
        fd = os.open(f"/dev/video{int(index)}", os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return {}

    controls = {}
    try:
        for name, control_id in CONTROLS.items():
            query = v4l2_queryctrl(id=control_id)
            try:
                fcntl.ioctl(fd, VIDIOC_QUERYCTRL, query)
            except OSError:
                # The camera doesn't have this control
                continue
            if query.flags & V4L2_CTRL_FLAG_DISABLED:
                continue
            controls[name] = {
                "min": query.minimum,
                "max": query.maximum,
                "step": max(1, query.step),
                "default": query.default_value,
            }
    finally:
        os.close(fd)

    return controls
