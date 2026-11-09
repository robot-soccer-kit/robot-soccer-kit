"""
Camera intrinsic calibration tool (focal, principal point and lens distortion), using a ChArUco
board (a chessboard with ArUco markers in its white squares).

The board can be partially visible, which allows to bring it in the corners of the image, where the
distortion of wide angle lenses is the largest.

Installation (with the Game Controller dependencies):

    pip install -U "robot-soccer-kit[gc]"

Usage:

    # 1. Generate the board (calibration_board.png, in the current directory), print it and glue
    #    it on a flat rigid support
    python -m rsk.calibrate_camera --generate

    # 2. Calibrate with the live camera (views are captured automatically)
    python -m rsk.calibrate_camera --camera 0 --save-dir calibration_images

    # Or calibrate from existing images
    python -m rsk.calibrate_camera --images "calibration_images/*.png"

On Windows, "py" can be used instead of "python".

The printed size of the board doesn't matter: the focal and the distortion don't depend on it.
Requires OpenCV >= 4.7 (installed with the [gc] extra).
"""

import argparse
import glob
import json
import math
import os
import sys
import time

import numpy as np

INSTALL_HELP = 'Install the Game Controller dependencies with: pip install -U "robot-soccer-kit[gc]"'

try:
    import cv2
except ImportError:
    sys.exit("OpenCV is not installed. " + INSTALL_HELP)

if not hasattr(cv2, "aruco") or not hasattr(cv2.aruco, "CharucoDetector"):
    sys.exit(
        f"OpenCV {cv2.__version__} is too old (4.7 or newer is needed). " + INSTALL_HELP
    )

# Board: 9x6 squares, 5x5 ArUco markers (different from the 4x4 markers of the field and robots)
BOARD_SQUARES = (9, 6)
SQUARE_LENGTH = 0.030  # [m] (only used to scale the board pose, not the intrinsics)
MARKER_LENGTH = 0.022  # [m]
DICTIONARY = cv2.aruco.DICT_5X5_100

# Minimum number of chessboard corners detected for a view to be used
MIN_CORNERS = 12
# Minimum number of views to calibrate
MIN_VIEWS = 12

# Default file name of the board image (written in the current directory)
DEFAULT_BOARD_FILE = "calibration_board.png"

# Resolution used by the Game Controller (see video.py)
DEFAULT_RESOLUTION = (1920, 1080)


def make_board():
    dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY)
    return cv2.aruco.CharucoBoard(
        BOARD_SQUARES, SQUARE_LENGTH, MARKER_LENGTH, dictionary
    )


def generate_board(
    filename: str, square_pixels: int = 300, margin_pixels: int = 150
) -> None:
    """
    Writes an image of the board (to be printed)
    """
    board = make_board()
    size = (
        BOARD_SQUARES[0] * square_pixels + 2 * margin_pixels,
        BOARD_SQUARES[1] * square_pixels + 2 * margin_pixels,
    )
    image = board.generateImage(size, marginSize=margin_pixels)
    if not cv2.imwrite(filename, image):
        raise RuntimeError(f"Can't write {filename}")


def detect_board(image, detector, board):
    """
    Detects the board in an image

    :return: (object_points, image_points) or None if the board is not (enough) visible
    """
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)

    if charuco_corners is None or len(charuco_corners) < MIN_CORNERS:
        return None

    object_points, image_points = board.matchImagePoints(charuco_corners, charuco_ids)
    if object_points is None or len(object_points) < MIN_CORNERS:
        return None

    return object_points.reshape(-1, 3), image_points.reshape(-1, 2)


def calibrate(views: list, image_size: tuple) -> dict:
    """
    Calibrates the camera

    :param list views: list of (object_points, image_points)
    :param tuple image_size: (width, height)
    :return dict: calibration result
    """
    if len(views) < MIN_VIEWS:
        raise ValueError(f"At least {MIN_VIEWS} views are needed, got {len(views)}")

    object_points = [np.asarray(o, dtype=np.float32) for o, _ in views]
    image_points = [np.asarray(i, dtype=np.float32) for _, i in views]

    rms, intrinsic, distortion, _, _ = cv2.calibrateCamera(
        object_points, image_points, image_size, None, None
    )
    distortion = distortion.ravel()

    width, height = image_size
    focal = (intrinsic[0, 0] + intrinsic[1, 1]) / 2

    # How much the distortion moves the points in the corners of the image
    corners = np.array(
        [[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]],
        dtype=np.float64,
    ).reshape(-1, 1, 2)
    undistorted = cv2.undistortPoints(
        corners, intrinsic, distortion, P=intrinsic
    ).reshape(-1, 2)
    corner_displacement = float(
        np.max(np.linalg.norm(undistorted - corners.reshape(-1, 2), axis=1))
    )

    return {
        "image_size": [int(width), int(height)],
        "views": len(views),
        "rms_reprojection_error_px": float(rms),
        "focal_px": [float(intrinsic[0, 0]), float(intrinsic[1, 1])],
        "principal_point_px": [float(intrinsic[0, 2]), float(intrinsic[1, 2])],
        "principal_point_offset_px": [
            float(intrinsic[0, 2] - width / 2),
            float(intrinsic[1, 2] - height / 2),
        ],
        # OpenCV model: k1, k2, p1, p2, k3
        "distortion": [float(d) for d in distortion[:5]],
        "distortion_at_image_corners_px": corner_displacement,
        # Value of the "focal" setting of the Game Controller (defined for a 1080p image)
        "rsk_focal_setting": float(focal * 1080 / height),
        "diagonal_fov_deg": float(
            2 * math.degrees(math.atan(math.hypot(width / 2, height / 2) / focal))
        ),
    }


def print_result(result: dict) -> None:
    print()
    print("Calibration result")
    print("==================")
    print(f"Views used:                     {result['views']}")
    print(
        f"Reprojection error (RMS):       {result['rms_reprojection_error_px']:.3f} px"
    )
    print(
        f"Focal:                          {result['focal_px'][0]:.1f} / {result['focal_px'][1]:.1f} px"
    )
    print(f"Game Controller focal setting:  {result['rsk_focal_setting']:.0f}")
    print(
        "Principal point offset:         "
        f"{result['principal_point_offset_px'][0]:+.1f} / {result['principal_point_offset_px'][1]:+.1f} px"
    )
    print(
        "Distortion (k1, k2, p1, p2, k3): "
        + ", ".join(f"{d:+.4f}" for d in result["distortion"])
    )
    print(
        f"Distortion at image corners:    {result['distortion_at_image_corners_px']:.1f} px"
    )
    print(
        f"Diagonal field of view (pinhole equivalent): {result['diagonal_fov_deg']:.1f} deg"
    )
    if result["rms_reprojection_error_px"] > 1.0:
        print()
        print(
            "WARNING: the reprojection error is high, check that the board is flat and that the"
        )
        print("images are not blurred (keep the board still when views are captured)")


def view_key(image_points, image_size):
    """
    A descriptor of a view (position, size and shape of the board in the image), used to only keep
    views that are different enough
    """
    width, height = image_size
    center = image_points.mean(axis=0) / [width, height]
    hull = cv2.convexHull(image_points.astype(np.float32))
    area = math.sqrt(cv2.contourArea(hull)) / width
    # Elongation of the board in the image gives an idea of its tilt
    _, (w, h), angle = cv2.minAreaRect(image_points.astype(np.float32))
    elongation = min(w, h) / max(w, h, 1e-6)
    return np.array([center[0], center[1], area, elongation, math.radians(angle) / 4])


def draw_coverage(image, all_points, cells=(6, 4)):
    """
    Draws the parts of the image already covered by the board in the captured views
    """
    height, width = image.shape[:2]
    overlay = image.copy()
    counts = np.zeros((cells[1], cells[0]), dtype=int)
    for x, y in all_points:
        counts[
            min(int(y * cells[1] / height), cells[1] - 1),
            min(int(x * cells[0] / width), cells[0] - 1),
        ] += 1

    for j in range(cells[1]):
        for i in range(cells[0]):
            color = (
                (0, 0, 255)
                if counts[j, i] == 0
                else (0, 200, 255)
                if counts[j, i] < 30
                else (0, 200, 0)
            )
            top_left = (i * width // cells[0], j * height // cells[1])
            bottom_right = ((i + 1) * width // cells[0], (j + 1) * height // cells[1])
            cv2.rectangle(overlay, top_left, bottom_right, color, -1)

    cv2.addWeighted(overlay, 0.25, image, 0.75, 0, image)
    for x, y in all_points:
        cv2.circle(image, (int(x), int(y)), 2, (255, 255, 0), -1)


def open_camera(index: int, resolution: tuple):
    """
    Opens the camera with the same settings as the Game Controller (video.py)
    """
    capture = cv2.VideoCapture(index)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G"))
    capture.set(cv2.CAP_PROP_FPS, 30)
    if not capture.isOpened():
        raise RuntimeError(f"Can't open camera {index}")
    return capture


def live_calibration(index: int, resolution: tuple, save_dir: str = None) -> tuple:
    """
    Live calibration: views are captured automatically when the board is still and in a new
    position. Keys: space = force a capture, c = calibrate, q / Esc = quit

    :return: (views, image_size)
    """
    board = make_board()
    detector = cv2.aruco.CharucoDetector(board)
    capture = open_camera(index, resolution)

    views, keys, all_points = [], [], []
    previous_points, last_capture = None, 0.0
    image_size = None
    window = "RSK camera calibration (space: capture, c: calibrate, q: quit)"

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        print(f"Captured views are saved in {os.path.abspath(save_dir)}")

    try:
        while True:
            grabbed, frame = capture.read()
            if not grabbed or frame is None:
                time.sleep(0.01)
                continue

            image_size = (frame.shape[1], frame.shape[0])
            display = frame.copy()
            detection = detect_board(frame, detector, board)
            key = cv2.waitKey(1) & 0xFF

            capture_view = False
            if detection is not None:
                object_points, image_points = detection
                for x, y in image_points:
                    cv2.circle(display, (int(x), int(y)), 4, (0, 255, 0), -1)

                # The board should be still (no motion blur)
                still = (
                    previous_points is not None
                    and previous_points.shape == image_points.shape
                    and np.max(np.abs(previous_points - image_points)) < 1.5
                )
                current_key = view_key(image_points, image_size)
                new_view = (
                    not keys
                    or min(np.linalg.norm(k - current_key) for k in keys) > 0.08
                )
                capture_view = key == ord(" ") or (
                    still and new_view and time.time() - last_capture > 0.7
                )
                previous_points = image_points
            else:
                previous_points = None

            if capture_view:
                views.append(detection)
                keys.append(view_key(detection[1], image_size))
                all_points.extend(detection[1].tolist())
                last_capture = time.time()
                if save_dir:
                    cv2.imwrite(
                        os.path.join(save_dir, f"view_{len(views):03d}.png"), frame
                    )
                display[:] = 255 - display  # Flash

            draw_coverage(display, all_points)
            text = f"{len(views)} views (min {MIN_VIEWS}). Move the board everywhere, tilted, also in the corners"
            cv2.putText(
                display, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5
            )
            cv2.putText(
                display,
                text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
            )

            scale = min(1.0, 1280 / display.shape[1])
            cv2.imshow(window, cv2.resize(display, None, fx=scale, fy=scale))

            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                if len(views) >= MIN_VIEWS:
                    break
                print(f"Not enough views yet ({len(views)}/{MIN_VIEWS})")
    finally:
        capture.release()
        cv2.destroyAllWindows()

    return views, image_size


def views_from_images(patterns: list) -> tuple:
    """
    Detects the board in image files

    :return: (views, image_size)
    """
    board = make_board()
    detector = cv2.aruco.CharucoDetector(board)
    views, image_size = [], None

    filenames = sorted({f for pattern in patterns for f in glob.glob(pattern)})
    for filename in filenames:
        image = cv2.imread(filename)
        if image is None:
            print(f"Can't read {filename}, skipped")
            continue
        size = (image.shape[1], image.shape[0])
        if image_size is not None and size != image_size:
            print(f"{filename} has a different size {size}, skipped")
            continue
        image_size = size

        detection = detect_board(image, detector, board)
        if detection is None:
            print(f"Board not found in {filename}, skipped")
        else:
            views.append(detection)

    return views, image_size


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Camera calibration (focal, principal point, lens distortion) with a ChArUco board"
    )
    parser.add_argument(
        "--generate",
        type=str,
        nargs="?",
        const=DEFAULT_BOARD_FILE,
        help=f"Write the board image to print in this file (default: {DEFAULT_BOARD_FILE}, "
        "in the current directory)",
    )
    parser.add_argument(
        "--camera", "-c", type=int, help="Camera index for live calibration"
    )
    parser.add_argument(
        "--images", "-i", nargs="+", help="Calibrate from image files (glob patterns)"
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="%dx%d" % DEFAULT_RESOLUTION,
        help="Camera resolution for live calibration (default: 1920x1080, as the Game Controller)",
    )
    parser.add_argument(
        "--save-dir", type=str, help="Save the captured views in this directory"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="camera_calibration.json",
        help="Result file",
    )
    args = parser.parse_args(argv)

    if args.generate:
        generate_board(args.generate)
        print(f"Board written to {os.path.abspath(args.generate)}")
        print("Print it (the size doesn't matter) and glue it on a flat rigid support")
        return 0

    if args.camera is not None:
        resolution = tuple(int(v) for v in args.resolution.lower().split("x"))
        try:
            views, image_size = live_calibration(args.camera, resolution, args.save_dir)
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1
    elif args.images:
        views, image_size = views_from_images(args.images)
    else:
        parser.print_help()
        return 1

    if len(views) < MIN_VIEWS:
        print(f"Not enough views: {len(views)} (at least {MIN_VIEWS} are needed)")
        return 1

    result = calibrate(views, image_size)
    print_result(result)

    with open(args.output, "w") as file:
        json.dump(result, file, indent=2)
    print(f"\nResult saved to {os.path.abspath(args.output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
