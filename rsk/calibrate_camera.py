"""
Camera lens calibration tool (focal, principal point and lens distortion), using a ChArUco board
(a chessboard with ArUco markers in its white squares).

The same calibration can be done in the Game Controller interface (Camera tab), where the result is
directly used by the vision.

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
import os
import sys
import time

INSTALL_HELP = 'Install the Game Controller dependencies with: pip install -U "robot-soccer-kit[gc]"'

try:
    import cv2
except ImportError:
    sys.exit("OpenCV is not installed. " + INSTALL_HELP)

if not hasattr(cv2, "aruco") or not hasattr(cv2.aruco, "CharucoDetector"):
    sys.exit(
        f"OpenCV {cv2.__version__} is too old (4.7 or newer is needed). " + INSTALL_HELP
    )

from . import lens_calibration  # noqa: E402
from .lens_calibration import MIN_VIEWS, calibrate, detect_board, make_board  # noqa: E402

# Default file name of the board image (written in the current directory)
DEFAULT_BOARD_FILE = "calibration_board.png"

# Resolution used by the Game Controller (see video.py)
DEFAULT_RESOLUTION = (1920, 1080)


def generate_board(filename: str) -> None:
    """
    Writes an image of the board (to be printed)
    """
    if not cv2.imwrite(filename, lens_calibration.board_image()):
        raise RuntimeError(f"Can't write {filename}")


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
    collector = lens_calibration.ViewCollector()
    capture = open_camera(index, resolution)
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

            key = cv2.waitKey(1) & 0xFF
            captured = collector.process(frame, force=key == ord(" "))
            if captured and save_dir:
                cv2.imwrite(
                    os.path.join(save_dir, f"view_{len(collector.views):03d}.png"),
                    frame,
                )

            display = frame.copy()
            collector.draw(display, captured)
            text = (
                f"{len(collector.views)} views (min {MIN_VIEWS}). "
                "Move the board everywhere, tilted, also in the corners"
            )
            for color, thickness in (((0, 0, 0), 5), ((255, 255, 255), 2)):
                cv2.putText(
                    display,
                    text,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    color,
                    thickness,
                )

            scale = min(1.0, 1280 / display.shape[1])
            cv2.imshow(window, cv2.resize(display, None, fx=scale, fy=scale))

            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                if len(collector.views) >= MIN_VIEWS:
                    break
                print(f"Not enough views yet ({len(collector.views)}/{MIN_VIEWS})")
    finally:
        capture.release()
        cv2.destroyAllWindows()

    return collector.views, collector.image_size


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
