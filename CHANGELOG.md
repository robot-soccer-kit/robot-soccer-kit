# Changelog

## Unreleased (branch `refactorv3`)

Tested on Linux (Ubuntu) and Windows 11, including the interface tests and the tests with real
cameras.

### Game Controller interface

* New interface, with light and dark themes (switch in the navigation bar). It fits the window
  without scrolling from 1024 x 640, and the referee is usable on a phone in portrait.
* Referee tab: scoreboard with the teams on the side of the field they defend, timer and game
  state; one main button to start / pause / resume (space bar too); large Validate / Cancel
  buttons for a goal waiting for validation; readable robot states ("Penalized by the referee
  (3 s)", "Being placed"...).
* Vision tab: camera image, detection, camera settings and lens calibration side by side.
  Robots tab: robot cards (communication, battery, detection, marker). Control tab: team cards.
* API errors are shown as notifications; confirmations use a modal.
* Live referee and replay share the same display code.
* Libraries updated and trimmed to the files actually used (832 KB instead of ~11 MB):
  Bootstrap 5.3.8, Bootstrap Icons 1.13.2, jQuery 3.7.1, in `rsk/static/vendor/`.

### Vision

* Preview of the camera before the vision starts (MJPEG stream, all the images at full size).
* Automatic camera settings (image settings to the defaults of the camera, exposure searched)
  and automatic crop to the field.
* Lights setting (50 Hz, 60 Hz, none): the exposure is a multiple of the flickering period of
  the lights, to avoid bands on the image (Linux).
* Settings and lens calibration saved for each camera; the lights setting is shared.
* On Linux: cameras listed with their names, opened with V4L2 (a camera was listed twice), only
  the resolutions the camera can give are proposed.
* Lens calibration (focal, optical center, distortion) with a ChArUco board, in the interface
  and with `python -m rsk.calibrate_camera`. When calibrated, only the camera pose is estimated
  from the field markers: positions within a few millimeters instead of 1 to 2.5 cm near the
  borders with a wide angle lens.
* Default focal set to the one of the recommended camera (935 instead of 885); a
  configuration with the previous default is updated.
* Robot orientation computed from the back to the front of the tag (mean error 1.04 -> 0.87
  deg).
* A camera that gives no image (e.g. used by another program) is reported.
* Faster ball detection (about 5 times), image encoded once whatever the number of pages.
* The image follows the sliders while they move, only the changed settings are sent to the
  camera.

### Referee and control

* Penalty spot: a spot assigned to another robot is never chosen.
* Goal validation ignored when no goal is pending (cancelling twice decremented the score).
* Half time cancels an expected ball placement; ending the game during half time clears it.
* Control and referee threads survive unexpected errors (they used to stop for good).
* Tasks accessed under a lock; placement tasks stop the right robots; path finder 8 times
  faster and returns no path instead of crashing.
* Ball teleport no longer truncates the coordinates to integers.

### Robots and simulator

* Packet reader recovers after a corrupted packet (a WiFi robot stayed "no response").
* Negative values of serial robots decoded correctly with numpy 2.
* WiFi service no longer freezes on a short packet, and Ctrl+C stops the Game Controller.
* Simulated robots apply the orders like the real ones (same rounding, same maximum wheel
  speed); overlapping objects are separated; state published at 30 Hz as the vision; less CPU.
* Running the simulator no longer replaces the saved real robots.
* Serial robots: a missing port is retried every second (busy loop on Linux).

### API and configuration

* HTTP API calls are validated (arguments, NaN, booleans): errors are returned instead of
  HTTP 500.
* Configuration written atomically; an unreadable file is kept aside and the Game Controller
  starts anyway.

### Installation, tests and CI

* `game-controller.bat` fixed (it ran `py -m install`, and didn't install the `gc` extra).
* Test suite (`tests/`): unit tests, property-based tests (hypothesis), vision on synthetic
  images, interface tests (Playwright), optional tests with real cameras. See the README.
* CI: Python 3.9 to 3.14 actually tested, on Linux, macOS and Windows; pull requests checked.
* Makefile: `python -m build`, `ruff format`, `make test`.
* Dead code removed (`rsk/logger.py`, `detection.Detect`).
