import numpy as np
import cv2

class Field:
    def __init__(self):
        self.corner_tag_size = 0.08
        self.robot_tag_size = 0.08
        self.frame_point_list = None
        self.id_gfx_corners = {}

        self.field_shape = [1.83, 1.22] # Field dimension (length, width)

        self.corner_field_positions = {}
        for (c, sx, sy) in (['c1', 1, 1], ['c2', 1, -1], ['c3', -1, 1], ['c4', -1, -1]):
            cX = sx * self.field_shape[0]/2
            cY = sy * self.field_shape[1]/2

            self.corner_field_positions[c] = [
                (cX + self.corner_tag_size/2, cY + self.corner_tag_size/2),
                (cX + self.corner_tag_size/2, cY - self.corner_tag_size/2),
                (cX - self.corner_tag_size/2, cY - self.corner_tag_size/2),
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
        if len(self.corner_gfx_positions) == len(self.corner_field_positions):
            graphics_positions = []
            field_positions = []
            for key in self.corner_field_positions:
                k = 0
                for gfx, real in zip(self.corner_gfx_positions[key], self.corner_field_positions[key]):
                    graphics_positions.append(gfx)
                    field_positions.append(real)

                    # if k == 3:
                    #     txt = '%.2f, %.2f' % real
                    #     cv2.circle(debug, (int(gfx[0]), int(gfx[1])), 2, (255, 0, 0))
                    #     cv2.putText(debug, txt, (int(gfx[0]), int(gfx[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0))
                    # k += 1

            graphics_positions = np.array(graphics_positions)
            field_positions = np.array(field_positions)
            print(field_positions)
            H, mask = cv2.findHomography(graphics_positions, field_positions)
            self.homography = H
            # print(H)

            # print('~')
            # print(field_positions)
            # print(self.pos_of_gfx(graphics_positions[0]))
            # print(self.pos_of_gfx(graphics_positions[1]))
            # print(self.pos_of_gfx(graphics_positions[2]))
            # print(self.pos_of_gfx(graphics_positions[3]))
        
    def pos_of_gfx(self, pos):
        M = np.ndarray(shape = (3,1), buffer = np.array([[pos[0]], [pos[1]], [1.0]]))
        result = np.dot(self.homography, M)
        return [result[0]/result[2], result[1]/result[2]]

    def pose_of_tag(self, corners):
        if self.calibrated():
            center = self.pos_of_gfx(self.tag_position(corners))
            front = self.pos_of_gfx(self.tag_position(corners, front=True))
            print(center)
            print(front)

            return {
                'position': center,
                'orientation': np.arctan2(front[1] - center[1], front[0] - center[0])
            }
        else:
            return None
