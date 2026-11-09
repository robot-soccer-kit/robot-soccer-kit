import socket
import time

import pytest
from rsk.backend import Backend


@pytest.fixture(scope="session")
def board_images():
    """
    Views of the calibration board (with blur, noise and JPEG compression) seen by a camera with
    the lens synthetic.DISTORTED_LENS, enough to calibrate. Generated once (it takes a few seconds).
    """
    import numpy as np
    import synthetic

    return synthetic.calibration_board_views(
        synthetic.Camera(**synthetic.DISTORTED_LENS),
        np.random.default_rng(0),
        noisy=True,
    )


@pytest.fixture(scope="session", autouse=True)
def isolated_config(tmp_path_factory):
    """
    Tests never read nor write the real configuration file nor recordings
    """
    from rsk import config

    from rsk import replay_logger

    config.filename = str(tmp_path_factory.mktemp("config") / "config.json")
    config.config.clear()
    # Match recordings are also written in a temporary directory
    replay_logger.path = str(tmp_path_factory.mktemp("rsk_recorder")) + "/"
    yield config


@pytest.fixture(scope="session")
def backend(isolated_config):
    """
    A running simulated backend. It binds the 7557 and 7558 ports, so it is shared by all the tests.
    Tests should leave it in the state they found it (game stopped, no extra tasks).
    """
    # The backend uses fixed ports, that are already used if a Game Controller is running
    for port in (7557, 7558):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
            if test_socket.connect_ex(("127.0.0.1", port)) == 0:
                pytest.exit(
                    f"Port {port} is already used, is a Game Controller running? "
                    "Stop it before running the tests",
                    returncode=1,
                )

    backend = Backend(simulated=True)
    # Waiting for the initial one-time tasks to be processed
    time.sleep(0.5)
    yield backend
    backend.control.stop()
    backend.simulator.run = False


@pytest.fixture
def control(backend):
    return backend.control
