import time

import pytest
from rsk.backend import Backend


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
    backend = Backend(simulated=True)
    # Waiting for the initial one-time tasks to be processed
    time.sleep(0.5)
    yield backend
    backend.control.stop()
    backend.simulator.run = False


@pytest.fixture
def control(backend):
    return backend.control
