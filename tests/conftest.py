import time

import pytest

from rsk.backend import Backend


@pytest.fixture(scope="session")
def backend():
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
