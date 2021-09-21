import numpy as np
import cv2

length = 1.83
width = 1.22

class Field:
    def __init__(self):
        self.corner_tag_size = 0.08
        self.corner_tag_border = 0.01
        self.robot_tag_size = 0.08
        self.frame_point_list = None
        self.id_gfx_corners = {}

        self.field_shape = [length, width] # Field dimension (length, width)

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

        self.homography = None

    def calibrated(self):
        return self.homography is not None

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

    def update_homography(self, debug):
        if len(self.corner_gfx_positions) >= 3: # We allow to compute homography with only 3 corners
            graphics_positions = []
            field_positions = []
            for key in self.corner_gfx_positions:
                k = 0
                for gfx, real in zip(self.corner_gfx_positions[key], self.corner_field_positions[key]):
                    graphics_positions.append(gfx)
                    field_positions.append(real)


            graphics_positions = np.array(graphics_positions)
            field_positions = np.array(field_positions)
            H, mask = cv2.findHomography(graphics_positions, field_positions)
            self.homography = H

        # We check that homography is consistent, note that this can happen (and should happen)
        # with only one or two corners!
        if self.homography is not None:
            bad_homography = False
            for key in self.corner_gfx_positions:
                for gfx, real in zip(self.corner_gfx_positions[key], self.corner_field_positions[key]):
                    projected = self.pos_of_gfx(gfx)
                    dist = np.linalg.norm(np.array(real) - np.array(projected))
                    if dist > 0.1:
                        bad_homography = True
            if bad_homography:
                self.homography = None

        self.corner_gfx_positions = {}
        
    def pos_of_gfx(self, pos):
        M = np.ndarray(shape = (3,1), buffer = np.array([[pos[0]], [pos[1]], [1.0]]))
        result = np.dot(self.homography, M)
        return [float(result[0]/result[2]), float(result[1]/result[2])]

    def pose_of_tag(self, corners):
        if self.calibrated():
            center = self.pos_of_gfx(self.tag_position(corners))
            front = self.pos_of_gfx(self.tag_position(corners, front=True))

            return {
                'position': center,
                'orientation': float(np.arctan2(front[1] - center[1], front[0] - center[0]))
            }
        else:
            return None