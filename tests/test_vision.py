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
    "above": synthetic.camera(),
    "lower, rotated": synthetic.camera(2.0, 0, 3),
    "tilted": synthetic.camera(2.2, -12, 0, (0, -0.3)),
    "rotated 90deg": synthetic.camera(2.5, 0, 90),
}


@pytest.mark.parametrize("camera", CAMERAS.values(), ids=CAMERAS.keys())
@pytest.mark.parametrize("noisy", [False, True], ids=["clean", "noisy"])
def test_detection_accuracy(camera, noisy):
    rng = np.random.default_rng(42)
    position_errors, orientation_errors = [], []

    for _ in range(3):
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
        assert math.dist(detection.ball, ball) < 0.005

    assert max(position_errors) < 0.005
    assert np.mean(orientation_errors) < math.radians(1.5)
    assert max(orientation_errors) < math.radians(4)


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
