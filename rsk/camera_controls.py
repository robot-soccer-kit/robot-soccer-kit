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


# Structures of the Linux kernel (linux/videodev2.h), their size is part of the ioctl numbers


class v4l2_queryctrl(ctypes.Structure):
    """
    Range and default of a control (VIDIOC_QUERYCTRL)
    """

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
    """
    Value of a control (VIDIOC_S_CTRL)
    """

    _fields_ = [("id", ctypes.c_uint32), ("value", ctypes.c_int32)]


class v4l2_fmtdesc(ctypes.Structure):
    """
    An image format of the camera (VIDIOC_ENUM_FMT)
    """

    _fields_ = [
        ("index", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("description", ctypes.c_char * 32),
        ("pixelformat", ctypes.c_uint32),
        ("mbus_code", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 3),
    ]


class v4l2_frmsizeenum(ctypes.Structure):
    """
    An image size of a format (VIDIOC_ENUM_FRAMESIZES)
    """

    # The union of the discrete and stepwise sizes is read as 6 integers
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("pixel_format", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32 * 6),
        ("reserved", ctypes.c_uint32 * 2),
    ]


class v4l2_frmivalenum(ctypes.Structure):
    """
    A frame interval of an image size (VIDIOC_ENUM_FRAMEINTERVALS)
    """

    # The union of the discrete and stepwise intervals is read as 6 integers (fractions)
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("pixel_format", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("interval", ctypes.c_uint32 * 6),
        ("reserved", ctypes.c_uint32 * 2),
    ]


V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_FRMSIZE_TYPE_DISCRETE = 1
V4L2_FRMIVAL_TYPE_DISCRETE = 1


def fourcc(code: str) -> int:
    """
    :param str code: a format name of 4 characters (e.g. "MJPG")
    :return int: its V4L2 code
    """
    return sum(ord(c) << (8 * i) for i, c in enumerate(code))


# Format of the images asked by RSK to the cameras (see video.py)
MJPG = fourcc("MJPG")


def _iowr(group: str, number: int, size: int) -> int:
    # _IOWR macro of the Linux kernel (asm-generic/ioctl.h)
    return (3 << 30) | (size << 16) | (ord(group) << 8) | number


VIDIOC_QUERYCTRL = _iowr("V", 36, ctypes.sizeof(v4l2_queryctrl))
VIDIOC_S_CTRL = _iowr("V", 28, ctypes.sizeof(v4l2_control))
VIDIOC_ENUM_FMT = _iowr("V", 2, ctypes.sizeof(v4l2_fmtdesc))
VIDIOC_ENUM_FRAMESIZES = _iowr("V", 74, ctypes.sizeof(v4l2_frmsizeenum))
VIDIOC_ENUM_FRAMEINTERVALS = _iowr("V", 75, ctypes.sizeof(v4l2_frmivalenum))


def _enumerate(fd, request, make):
    """
    Calls an enumeration ioctl with the indexes 0, 1, 2... until it fails
    """
    import fcntl

    index = 0
    while index < 256:
        item = make(index)
        try:
            fcntl.ioctl(fd, request, item)
        except OSError:
            return
        yield item
        index += 1


def frame_sizes(index: int) -> dict:
    """
    Sizes of the images a camera can give, with their maximum frame rate, in the format asked by
    RSK (MJPG), or in any format if the camera doesn't have it (Linux only)

    :param int index: the camera index (/dev/videoN on Linux)
    :return dict: (width, height) => maximum frame rate [FPS] (0 if unknown), empty if unknown
    """
    if not is_linux:
        return {}

    try:
        fd = os.open(f"/dev/video{int(index)}", os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return {}

    def sizes_of(pixel_format):
        sizes = {}
        for size in _enumerate(
            fd,
            VIDIOC_ENUM_FRAMESIZES,
            lambda i: v4l2_frmsizeenum(index=i, pixel_format=pixel_format),
        ):
            if size.type != V4L2_FRMSIZE_TYPE_DISCRETE:
                # Continuous or stepwise sizes: not listed
                continue
            width, height = size.size[0], size.size[1]
            fps = 0.0
            for interval in _enumerate(
                fd,
                VIDIOC_ENUM_FRAMEINTERVALS,
                lambda i: v4l2_frmivalenum(
                    index=i, pixel_format=pixel_format, width=width, height=height
                ),
            ):
                numerator, denominator = interval.interval[0], interval.interval[1]
                if interval.type == V4L2_FRMIVAL_TYPE_DISCRETE and numerator:
                    fps = max(fps, denominator / numerator)
            sizes[(width, height)] = max(fps, sizes.get((width, height), 0.0))
        return sizes

    try:
        formats = [
            description.pixelformat
            for description in _enumerate(
                fd,
                VIDIOC_ENUM_FMT,
                lambda i: v4l2_fmtdesc(index=i, type=V4L2_BUF_TYPE_VIDEO_CAPTURE),
            )
        ]
        if MJPG in formats:
            return sizes_of(MJPG)
        sizes = {}
        for pixel_format in formats:
            for size, fps in sizes_of(pixel_format).items():
                sizes[size] = max(fps, sizes.get(size, 0.0))
        return sizes
    finally:
        os.close(fd)


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
