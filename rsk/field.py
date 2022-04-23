import time
import numpy as np
import cv2
from . import field_dimensions
import os 
from . import utils

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

class Field:
    def __init__(self):
        self.corner_tag_size = 0.16
        self.corner_tag_border = 0.025
        self.robot_tag_size = 0.08
        self.frame_point_list = None
        self.id_gfx_corners = {}
        self.should_calibrate = True

        #Dimensions
        self.camera_height = 2
        self.robot_height = 0.076

        self.field_shape = [field_dimensions.length, field_dimensions.width] # Field dimension (length, width)

        self.corner_field_positions = {}
        for (c, sx, sy) in (['c1', 1, 1], ['c2', 1, -1], ['c3', -1, 1], ['c4', -1, -1]):
            cX = sx * (self.field_shape[0]/2 + (self.corner_tag_size/2) + self.corner_tag_border)
            cY = sy * (self.field_shape[1]/2 + (self.corner_tag_size/2) + self.corner_tag_border)

            self.corner_field_positions[c] = [
                # Top left
                (cX + self.corner_tag_size/2, cY + self.corner_tag_size/2),
                # Top right
                (cX + self.corner_tag_size/2, cY - self.corner_tag_size/2),
                # Bottom right
                (cX - self.corner_tag_size/2, cY - self.corner_tag_size/2),
                # Bottom left
                (cX - self.corner_tag_size/2, cY + self.corner_tag_size/2),
            ]

        self.corner_gfx_positions = {}

        self.see_whole_field = False
        
        # Calibration matrices
        self.is_calibrated = False

        # Extrinsic (4x4) transformations
        self.extrinsic = None
        self.extrinsic_inv = None

        # Camera intrinsic and distortion
        self.intrinsic = None
        self.distortion = None
        self.errors = 0

    def calibrated(self):
        return self.is_calibrated

    def tag_position(self, corners, front = False):
        if front:
            pX = (corners[0][0] + corners[1][0])/2.0
            pY = (corners[0][1] + corners[1][1])/2.0
        else:
            pX = (corners[0][0] + corners[2][0])/2.0
            pY = (corners[0][1] + corners[2][1])/2.0

        return pX, pY

    def set_corner_position(self, corner, corners):
        self.corner_gfx_positions[corner] = corners

    def field_to_camera(self, point):
        return (self.extrinsic @ np.array([*point, 1.]))[:3]

    def camera_to_field(self, point):
        return (self.extrinsic_inv @ np.array([*point, 1.]))[:3]

    def update_calibration(self, image):
        if len(self.corner_gfx_positions) >= 4 and self.should_calibrate:
            # Computing point-to-point correspondance
            object_points = []
            graphics_positions = []
            for key in self.corner_gfx_positions:
                k = 0
                for gfx, real in zip(self.corner_gfx_positions[key], self.corner_field_positions[key]):
                    graphics_positions.append(gfx)
                    object_points.append([*real, 0.])

            object_points = np.array(object_points, dtype=np.float32)
            graphics_positions = np.array(graphics_positions, dtype=np.float32)

            # Calibrating camera
            ret, self.intrinsic, self.distortion, rvecs, tvecs = \
                cv2.calibrateCamera([object_points], [graphics_positions], image.shape[:2][::-1], None, None,
                flags=0)
        
            # Computing extrinsic matrices
            transformation = np.eye(4)
            transformation[:3, :3], _ = cv2.Rodrigues(rvecs[0])
            transformation[:3, 3] = tvecs[0].T
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
                x = sx * ((field_dimensions.length / 2) + field_dimensions.border_size)
                y = sy * ((field_dimensions.width / 2) + field_dimensions.border_size)

                img = self.position_to_pixel([x, y, 0.])
                image_points.append((int(img[0]), int(img[1])))

                if img[0] < 0 or img[0] > image_width or \
                    img[1] < 0 or img[1] > image_height:
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
                        print('Calibration seems wrong, re-calibrating')
                        self.should_calibrate = True

        self.corner_gfx_positions = {}
        
    def pixel_to_position(self, pos, z=0, debug=False):
        # Computing the point position in camera frame
        point_position_camera = cv2.undistortPoints(np.array(pos), self.intrinsic, self.distortion)[0][0]

        # Computing the point position in the field frame and solving for given z
        point_position_field = self.camera_to_field([*point_position_camera, 1.])
        camera_center_field = self.camera_to_field(np.array([0., 0., 0.]))
        delta = point_position_field - camera_center_field
        l = (z - camera_center_field[2])/delta[2]
        
        return list(camera_center_field + l*delta)[:2]

    def position_to_pixel(self, pos):
        if len(pos) == 2:
            # If no z is provided, assume it is a ground position
            pos = [*pos, 0.]
        
        point_position_camera = self.field_to_camera(pos)
        position, J = cv2.projectPoints(point_position_camera, np.zeros(3), np.zeros(3), self.intrinsic, self.distortion)
        position = position[0][0]
        
        return [int(position[0]), int(position[1])]

    def pose_of_tag(self, corners):
        if self.calibrated():
            center = self.pixel_to_position(self.tag_position(corners), self.robot_height)
            front = self.pixel_to_position(self.tag_position(corners, front=True), self.robot_height)

            return {
                'position': center,
                'orientation': float(np.arctan2(front[1] - center[1], front[0] - center[0]))
            }
        else:
            return None
