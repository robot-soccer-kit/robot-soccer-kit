import time
import numpy as np
import cv2
import logging
from . import constants
import os
from . import utils

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"


class Field:
    """
    Handle the field calibration and coordinates
    """

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger("field")
        self.focal = None

        # Should we (re-)calibrate the field ?
        self.should_calibrate: bool = True

        self.corner_field_positions = {}
        for (c, sx, sy) in (["c1", 1, 1], ["c2", 1, -1], ["c3", -1, 1], ["c4", -1, -1]):
            cX = sx * (constants.field_length / 2 + (constants.corner_tag_size / 2) + constants.corner_tag_border)
            cY = sy * (constants.field_width / 2 + (constants.corner_tag_size / 2) + constants.corner_tag_border)

            self.corner_field_positions[c] = [
                # Top left
                (
                    cX + constants.corner_tag_size / 2,
                    cY + constants.corner_tag_size / 2,
                ),
                # Top right
                (
                    cX + constants.corner_tag_size / 2,
                    cY - constants.corner_tag_size / 2,
                ),
                # Bottom right
                (
                    cX - constants.corner_tag_size / 2,
                    cY - constants.corner_tag_size / 2,
                ),
                # Bottom left
                (
                    cX - constants.corner_tag_size / 2,
                    cY + constants.corner_tag_size / 2,
                ),
            ]

        # Position of corners on the image
        self.corner_gfx_positions: dict = {}

        # Is the field calibrated ?
        self.is_calibrated = False

        # Do we see the whole field ?
        self.see_whole_field = False

        # Extrinsic (4x4) transformations
        self.extrinsic = None
        self.extrinsic_inv = None

        # Camera intrinsic and distortion
        self.intrinsic = None
        self.distortion = None
        self.errors = 0

    def calibrated(self) -> bool:
        """
        Is the field calibrated ?

        :return bool: True if the field is calibrated properly
        """
        return self.is_calibrated

    def tag_position(self, corners: list, front=False) -> tuple:
        """
        Returns the position of a tag

        :param list corners: tag's corners
        :param bool front: tag front ? (else, center), defaults to False
        :return tuple: position of the tag
        """

        if front:
            pX = (corners[0][0] + corners[1][0]) / 2.0
            pY = (corners[0][1] + corners[1][1]) / 2.0
        else:
            pX = (corners[0][0] + corners[2][0]) / 2.0
            pY = (corners[0][1] + corners[2][1]) / 2.0

        return pX, pY

    def set_corner_position(self, corner: str, corners: list):
        """
        Sets the position of a corner

        :param str corner: the corner name (c1, c2, c3 or c4)
        :param list corners: the corner position
        """
        self.corner_gfx_positions[corner] = corners

    def update_calibration(self, image):
        """
        If the field should be calibrated, compute a calibration from the detected corners.
        This will use corner positions previously passed with set_corner_positions.

        :param image: the (OpenCV) image used for calibration
        """
        if len(self.corner_gfx_positions) >= 4 and self.should_calibrate and self.focal is not None:
            # Computing point-to-point correspondance
            object_points = []
            graphics_positions = []
            for key in self.corner_gfx_positions:
                k = 0
                for gfx, real in zip(self.corner_gfx_positions[key], self.corner_field_positions[key]):
                    graphics_positions.append(gfx)
                    object_points.append([*real, 0.0])

            object_points = np.array(object_points, dtype=np.float32)
            graphics_positions = np.array(graphics_positions, dtype=np.float32)

            # Intrinsic parameters are fixed
            intrinsic = [
                [self.focal, 0, image.shape[1] / 2],
                [0, self.focal, image.shape[0] / 2],
                [0, 0, 1],
            ]

            # Calibrating camera
            flags = cv2.CALIB_USE_INTRINSIC_GUESS + cv2.CALIB_FIX_FOCAL_LENGTH + cv2.CALIB_FIX_PRINCIPAL_POINT

            # No distortion
            flags += cv2.CALIB_FIX_TANGENT_DIST
            flags += cv2.CALIB_FIX_K1 + cv2.CALIB_FIX_K2 + cv2.CALIB_FIX_K3 + cv2.CALIB_FIX_K4 + cv2.CALIB_FIX_K5

            ret, self.intrinsic, self.distortion, rvecs, tvecs = cv2.calibrateCamera(
                [object_points],
                [graphics_positions],
                image.shape[:2][::-1],
                np.array(intrinsic, dtype=np.float32),
                None,
                flags=flags,
            )

            # Computing extrinsic matrices
            transformation = np.eye(4)
            transformation[:3, :3], _ = cv2.Rodrigues(rvecs[0])
            transformation[:3, 3] = tvecs[0].T
            # transformation[:3, 3] = [0, 0, 2]
            self.extrinsic = transformation
            self.extrinsic_inv = np.linalg.inv(self.extrinsic)

            # We are now calibrated
            self.is_calibrated = True
            self.should_calibrate = False
            self.errors = 0

            # Checking if we can see the whole fields
            image_height, image_width, _ = image.shape
            image_points = []
            self.see_whole_field = True
            for sx, sy in [(-1, 1), (1, 1), (1, -1), (-1, -1)]:
                x = sx * ((constants.field_length / 2) + constants.border_size)
                y = sy * ((constants.field_width / 2) + constants.border_size)

                img = self.position_to_pixel([x, y, 0.0])
                image_points.append((int(img[0]), int(img[1])))

                if img[0] < 0 or img[0] > image_width or img[1] < 0 or img[1] > image_height:
                    self.see_whole_field = False

        # We check that calibration is consistent, this can happen be done with only a few corners
        # The goal is to avoid recalibrating everytime for performance reasons
        if len(self.corner_gfx_positions) >= 3:
            if self.is_calibrated:
                has_error = False
                for key in self.corner_gfx_positions:
                    for gfx, real in zip(self.corner_gfx_positions[key], self.corner_field_positions[key]):
                        projected_position = self.pixel_to_position(gfx)
                        reprojection_distance = np.linalg.norm(np.array(real) - np.array(projected_position))
                        if reprojection_distance > 0.025:
                            has_error = True

                if not has_error:
                    self.errors = 0
                else:
                    self.errors += 1
                    if self.errors > 8:
                        self.logger.warning("Calibration seems wrong, re-calibrating")
                        self.should_calibrate = True

        self.corner_gfx_positions = {}

    def field_to_camera(self, point: list) -> np.ndarray:
        """
        Transforms a point from field frame to camera frame

        :param list point: point in field frame (3d)
        :return np.ndarray: point in camera frame (3d)
        """
        return (self.extrinsic @ np.array([*point, 1.0]))[:3]

    def camera_to_field(self, point: list) -> np.ndarray:
        """
        Transforms a point from camera frame to field frame

        :param list point: point in camera frame (3d)
        :return np.ndarray: point in field frame (3d)
        """
        return (self.extrinsic_inv @ np.array([*point, 1.0]))[:3]

    def pixel_to_position(self, pixel: list, z: float = 0) -> list:
        """
        Transforms a pixel on the image to a 3D point on the field, given a z

        :param list pos: pixel
        :param float z: the height to intersect with, defaults to 0
        :return list: point coordinates (x, y)
        """

        # Computing the point position in camera frame
        point_position_camera = cv2.undistortPoints(np.array(pixel), self.intrinsic, self.distortion)[0][0]

        # Computing the point position in the field frame and solving for given z
        point_position_field = self.camera_to_field([*point_position_camera, 1.0])
        camera_center_field = self.camera_to_field(np.array([0.0, 0.0, 0.0]))
        delta = point_position_field - camera_center_field
        l = (z - camera_center_field[2]) / delta[2]

        return list(camera_center_field + l * delta)[:2]

    def position_to_pixel(self, pos: list) -> list:
        """
        Given a position (3D, will be assumed on the ground if 2D), find its position on the screen

        :param list pos: position in field frame (2D or 3D)
        :return list: position on the screen
        """
        if len(pos) == 2:
            # If no z is provided, assume it is a ground position
            pos = [*pos, 0.0]

        point_position_camera = self.field_to_camera(pos)
        position, J = cv2.projectPoints(
            point_position_camera,
            np.zeros(3),
            np.zeros(3),
            self.intrinsic,
            self.distortion,
        )
        position = position[0][0]

        return [int(position[0]), int(position[1])]

    def pose_of_tag(self, corners: list):
        """
        Returns the position and orientation of a detected tag

        :param list corners: tag's corners
        :return dict|None: a dict with position and orientation or None if not calibrated
        """
        if self.calibrated():
            center = self.pixel_to_position(self.tag_position(corners), constants.robot_height)
            front = self.pixel_to_position(self.tag_position(corners, front=True), constants.robot_height)

            return {
                "position": center,
                "orientation": float(np.arctan2(front[1] - center[1], front[0] - center[0])),
            }
        else:
            return None
