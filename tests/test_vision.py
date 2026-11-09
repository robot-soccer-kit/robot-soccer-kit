import math

import numpy as np
import pytest
import synthetic

from rsk.detection import Detection
from rsk.field import Field
from rsk.state import State


def angle_error(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def detect(image, frames=2):
    """
    Runs the detection on an image (the first frame is used for the field calibration)
    """
    detection = Detection()
    detection.state = State()
    detection.field.focal = synthetic.FOCAL
    for _ in range(frames):
        detection.detect_markers(image)
        detection.detect_ball(image, None)
    return detection


CAMERAS = {
    "above": synthetic.Camera(),
    "lower, rotated": synthetic.Camera(height=2.0, yaw=3),
    "tilted": synthetic.Camera(pitch=-12, offset=(0, -0.3)),
    "rotated 90deg": synthetic.Camera(height=2.5, yaw=90),
}


def detection_errors(cameras, rng, noisy=True, scenes=1):
    """
    Renders scenes seen by the given cameras, and returns the position, orientation and ball errors
    """
    position_errors, orientation_errors, ball_errors = [], [], []

    for camera in cameras:
        for _ in range(scenes):
            robots = synthetic.random_robots(rng)
            ball = (rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5))
            image = synthetic.render(robots, ball, camera)
            if noisy:
                image = synthetic.degrade(image, rng)

            detection = detect(image)
            assert detection.field.calibrated()
            assert detection.field.see_whole_field

            markers = detection.state.markers
            for name, (x, y, orientation) in robots.items():
                assert name in markers, f"{name} not detected"
                px, py = markers[name]["position"]
                position_errors.append(math.hypot(px - x, py - y))
                orientation_errors.append(
                    angle_error(markers[name]["orientation"], orientation)
                )

            assert detection.ball is not None
            ball_errors.append(math.dist(detection.ball, ball))

    return (
        np.array(position_errors),
        np.array(orientation_errors),
        np.array(ball_errors),
    )


@pytest.mark.parametrize("camera", CAMERAS.values(), ids=CAMERAS.keys())
@pytest.mark.parametrize("noisy", [False, True], ids=["clean", "noisy"])
def test_detection_accuracy(camera, noisy):
    positions, orientations, balls = detection_errors(
        [camera], np.random.default_rng(42), noisy, scenes=3
    )

    assert positions.max() < 0.005
    assert balls.max() < 0.005
    assert orientations.mean() < math.radians(1.5)
    assert orientations.max() < math.radians(4)


def test_detection_with_any_camera_pose():
    """
    The camera doesn't have to be centered nor perpendicular to the field
    """
    rng = np.random.default_rng(7)
    cameras = [synthetic.random_camera(rng) for _ in range(6)]
    positions, orientations, balls = detection_errors(cameras, rng)

    assert positions.max() < 0.005
    assert balls.max() < 0.005
    assert orientations.max() < math.radians(4)


@pytest.mark.xfail(
    strict=True,
    reason="Lens distortion is not modeled: the field calibration forces all distortion "
    "coefficients to zero (field.py), errors reach several centimeters near the field borders",
)
def test_detection_with_lens_distortion():
    """
    Barrel distortion estimated for the recommended camera (120 deg wide angle lens)
    """
    rng = np.random.default_rng(3)
    cameras = [
        synthetic.random_camera(rng, distortion=(-0.1, 0.0, 0.0, 0.0, 0.0))
        for _ in range(4)
    ]
    positions, orientations, balls = detection_errors(cameras, rng)

    assert positions.max() < 0.01
    assert balls.max() < 0.01


def test_orientation_uses_the_whole_tag():
    """
    The orientation is the direction from the middle of the back edge to the middle of the front
    edge of the tag (and not from its center)
    """
    field = Field()
    field.is_calibrated = True
    # Pixels are field positions here
    field.pixel_to_position = lambda pixel, z=0: list(pixel)

    # Front edge (corners 0 and 1) towards +x, only the corner 3 (back left) is shifted by 0.4 in y
    corners = [(1, 1), (1, -1), (-1, -1), (-1, 1.4)]
    pose = field.pose_of_tag(corners)

    # Back middle is (-1, 0.2), front middle is (1, 0)
    assert pose["orientation"] == pytest.approx(math.atan2(0 - 0.2, 1 - (-1)))
    # The position is still the middle of the diagonal 0-2
    assert pose["position"] == pytest.approx([0, 0])
