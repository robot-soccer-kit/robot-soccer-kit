import numpy as np
import cv2
import zmq
import time
from .field import Field
from . import constants, config
import os

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"


class Detection:
    def __init__(self):
        self.referee = None

        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.set_hwm(1)
        self.socket.bind("tcp://*:7557")

        # ArUco parameters
        self.arucoDict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        self.arucoParams = cv2.aruco.DetectorParameters_create()
        # arucoParams.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_APRILTAG

        # Goals Colors
        self.team_colors = {"green": (0, 255, 0), "blue": (255, 0, 0)}

        self.canceled_goal_side = None

        self.displaySettings = {
            "aruco": True,
            "goals": True,
            "ball": True,
            "timed_circle": False,
            "sideline": False,
            "landmark": True,
        }

        if "display_settings" in config.config:
            for entry in config.config["display_settings"]:
                self.displaySettings[entry] = config.config["display_settings"][entry]

        self.arucoItems = {
            # Corners
            0: ["c1", (128, 128, 0)],
            1: ["c2", (128, 128, 0)],
            2: ["c3", (128, 128, 0)],
            3: ["c4", (128, 128, 0)],
            # Green
            4: ["green1", (0, 128, 0)],
            5: ["green2", (0, 128, 0)],
            # Blue
            6: ["blue1", (128, 0, 0)],
            7: ["blue2", (128, 0, 0)],
            # Generic objects
            8: ["obj1", (128, 128, 0)],
            9: ["obj2", (128, 128, 0)],
            10: ["obj3", (128, 128, 0)],
            11: ["obj4", (128, 128, 0)],
            12: ["obj5", (128, 128, 0)],
            13: ["obj6", (128, 128, 0)],
            14: ["obj7", (128, 128, 0)],
            15: ["obj8", (128, 128, 0)],
        }

        # Ball detection parameters (HSV thresholds)
        self.lower_orange = np.array([0, 150, 150])
        self.upper_orange = np.array([25, 255, 255])

        # Detection output
        self.markers = {}
        self.last_updates = {}
        self.ball = None
        self.no_ball = 0
        self.field = Field()

    def set_display_settings(self, display_settings: list) -> list:
        display_settings_bool = []
        for i in range(len(display_settings)):
            if display_settings[i] == "on":
                display_settings_bool.append(True)
            else:
                display_settings_bool.append(False)
        self.displaySettings["aruco"] = display_settings_bool[0]
        self.displaySettings["goals"] = display_settings_bool[1]
        self.displaySettings["ball"] = display_settings_bool[2]
        self.displaySettings["timed_circle"] = display_settings_bool[3]
        self.displaySettings["sideline"] = display_settings_bool[4]
        self.displaySettings["landmark"] = display_settings_bool[5]

    def get_display_settings(self):
        display_settings_bool = []
        display_settings_bool.append(self.displaySettings["aruco"])
        display_settings_bool.append(self.displaySettings["goals"])
        display_settings_bool.append(self.displaySettings["ball"])
        display_settings_bool.append(self.displaySettings["timed_circle"])
        display_settings_bool.append(self.displaySettings["sideline"])
        display_settings_bool.append(self.displaySettings["landmark"])
        return display_settings_bool

    def get_default_display_settings(self):
        display_settings_bool = [True, True, True, False, False, True]
        return display_settings_bool

    def save_display_settings(self):
        config.config["display_settings"] = {
            "aruco": self.displaySettings["aruco"],
            "goals": self.displaySettings["goals"],
            "ball": self.displaySettings["ball"],
            "timed_circle": self.displaySettings["timed_circle"],
            "sideline": self.displaySettings["sideline"],
            "landmark": self.displaySettings["landmark"],
        }
        config.save()

    def calibrate_camera(self):
        self.field.should_calibrate = True
        self.field.is_calibrated = False

    def draw_point2square(self, image, center: list, margin: int, color: tuple, thickness: int):
        """
        Helper to draw a square on the image
        """
        pointA = self.field.position_to_pixel([center[0] - margin, center[1] + margin])
        pointB = self.field.position_to_pixel([center[0] + margin, center[1] + margin])
        pointC = self.field.position_to_pixel([center[0] + margin, center[1] - margin])
        pointD = self.field.position_to_pixel([center[0] - margin, center[1] - margin])
        cv2.line(image, pointA, pointB, color, thickness)
        cv2.line(image, pointB, pointC, color, thickness)
        cv2.line(image, pointC, pointD, color, thickness)
        cv2.line(image, pointD, pointA, color, thickness)

    def draw_circle(
        self,
        image,
        center: list,
        radius: float,
        color: tuple,
        thickness: int,
        points: int = 32,
        dashed: bool = False,
    ):
        """
        Helper to draw a circle on the image
        """
        first_point = None
        last_point = None
        k = 0
        for alpha in np.linspace(0, 2 * np.pi, points):
            new_point = [
                center[0] + np.cos(alpha) * radius,
                center[1] + np.sin(alpha) * radius,
                0,
            ]
            if last_point:
                A = self.field.position_to_pixel(last_point)
                B = self.field.position_to_pixel(new_point)
                k += 1
                if not dashed or k % 2 == 0:
                    cv2.line(image, A, B, color, thickness)
            last_point = new_point
            if first_point is None:
                first_point = new_point

    def draw_annotations(self, image_debug):
        """
        Draw extra annotations (lines, circles etc.) to check visually that the informations are matching
        the real images
        """
        if self.field.calibrated() and (image_debug is not None) and (self.referee is not None):
            if self.displaySettings["sideline"]:
                [
                    field_UpRight,
                    field_DownRight,
                    field_DownLeft,
                    field_UpLeft,
                ] = constants.field_corners(constants.field_in_margin)
                A = self.field.position_to_pixel(field_UpRight)
                B = self.field.position_to_pixel(field_DownRight)
                C = self.field.position_to_pixel(field_DownLeft)
                D = self.field.position_to_pixel(field_UpLeft)
                cv2.line(image_debug, A, B, (0, 255, 0), 1)
                cv2.line(image_debug, B, C, (0, 255, 0), 1)
                cv2.line(image_debug, C, D, (0, 255, 0), 1)
                cv2.line(image_debug, D, A, (0, 255, 0), 1)

                [
                    field_UpRight,
                    field_DownRight,
                    field_DownLeft,
                    field_UpLeft,
                ] = constants.field_corners(constants.field_out_margin)
                A = self.field.position_to_pixel(field_UpRight)
                B = self.field.position_to_pixel(field_DownRight)
                C = self.field.position_to_pixel(field_DownLeft)
                D = self.field.position_to_pixel(field_UpLeft)
                cv2.line(image_debug, A, B, (0, 0, 255), 1)
                cv2.line(image_debug, B, C, (0, 0, 255), 1)
                cv2.line(image_debug, C, D, (0, 0, 255), 1)
                cv2.line(image_debug, D, A, (0, 0, 255), 1)

            if self.displaySettings["goals"]:
                for sign, color in [
                    (-1, self.team_colors[self.referee.negative_team]),
                    (1, self.team_colors[self.referee.positive_team]),
                ]:
                    C = self.field.position_to_pixel(
                        [
                            sign * (constants.field_length / 2.0),
                            -sign * constants.goal_width / 2.0,
                        ]
                    )
                    D = self.field.position_to_pixel(
                        [
                            sign * (constants.field_length / 2.0),
                            sign * constants.goal_width / 2.0,
                        ]
                    )
                    E = self.field.position_to_pixel(
                        [
                            sign * (constants.field_length / 2.0),
                            -sign * constants.goal_width / 2.0,
                            constants.goal_virtual_height,
                        ]
                    )
                    F = self.field.position_to_pixel(
                        [
                            sign * (constants.field_length / 2.0),
                            sign * constants.goal_width / 2.0,
                            constants.goal_virtual_height,
                        ]
                    )
                    cv2.line(image_debug, C, D, color, 3)
                    cv2.line(image_debug, E, F, color, 2)
                    cv2.line(image_debug, C, E, color, 2)
                    cv2.line(image_debug, D, F, color, 2)

                    for post in [-1, 1]:
                        A = self.field.position_to_pixel(
                            [
                                sign * (0.05 + constants.field_length / 2.0),
                                post * constants.goal_width / 2.0,
                            ]
                        )
                        B = self.field.position_to_pixel(
                            [
                                sign * (constants.field_length / 2.0),
                                post * constants.goal_width / 2.0,
                            ]
                        )
                        cv2.line(image_debug, A, B, color, 3)

            if self.displaySettings["landmark"]:
                A = self.field.position_to_pixel([0, 0])
                B = self.field.position_to_pixel([0.2, 0])
                cv2.line(image_debug, A, B, (0, 0, 255), 1)
                A = self.field.position_to_pixel([0, 0])
                B = self.field.position_to_pixel([0, 0.2])
                cv2.line(image_debug, A, B, (0, 255, 0), 1)
                A = self.field.position_to_pixel([0, 0, 0])
                B = self.field.position_to_pixel([0, 0, 0.2])
                cv2.line(image_debug, A, B, (255, 0, 0), 1)

            if self.displaySettings["timed_circle"] and self.ball is not None:
                self.draw_circle(
                    image_debug,
                    self.ball,
                    constants.timed_circle_radius,
                    (0, 0, 255),
                    1,
                    dashed=True,
                )

            if self.referee.wait_ball_position is not None:
                self.draw_circle(
                    image_debug,
                    self.referee.wait_ball_position,
                    constants.place_ball_margin,
                    (0, 165, 255),
                    2,
                    16,
                )

    def detect_markers(self, image, image_debug=None):
        """
        Detect the fiducial markers on the image, they are passed to the field for calibration
        """
        (corners, ids, rejected) = cv2.aruco.detectMarkers(image, self.arucoDict, parameters=self.arucoParams)
        new_markers = {}

        if len(corners) > 0:
            for (markerCorner, markerID) in zip(corners, ids.flatten()):
                if markerID not in self.arucoItems:
                    continue

                corners = markerCorner.reshape((4, 2))

                # Draw the bounding box of the ArUCo detection
                item = self.arucoItems[markerID][0]

                if item[0] == "c":
                    self.field.set_corner_position(item, corners)

                if image_debug is not None:
                    (topLeft, topRight, bottomRight, bottomLeft) = corners
                    topRight = (int(topRight[0]), int(topRight[1]))
                    bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
                    bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
                    topLeft = (int(topLeft[0]), int(topLeft[1]))
                    itemColor = self.arucoItems[markerID][1]
                    if self.displaySettings["aruco"]:
                        cv2.line(image_debug, topLeft, topRight, itemColor, 2)
                        cv2.line(image_debug, topRight, bottomRight, itemColor, 2)
                        cv2.line(image_debug, bottomRight, bottomLeft, itemColor, 2)
                        cv2.line(image_debug, bottomLeft, topLeft, itemColor, 2)

                        # Compute and draw the center (x, y)-coordinates of the
                        # ArUco marker
                        cX = int((topLeft[0] + bottomRight[0]) / 2.0)
                        cY = int((topLeft[1] + bottomRight[1]) / 2.0)
                        cv2.circle(image_debug, (cX, cY), 4, (0, 0, 255), -1)
                        fX = int((topLeft[0] + topRight[0]) / 2.0)
                        fY = int((topLeft[1] + topRight[1]) / 2.0)
                        cv2.line(
                            image_debug,
                            (cX, cY),
                            (cX + 2 * (fX - cX), cY + 2 * (fY - cY)),
                            (0, 0, 255),
                            2,
                        )

                        text = item
                        if item.startswith("blue") or item.startswith("green"):
                            text = item[-1]
                        cv2.putText(
                            image_debug,
                            text,
                            (cX - 4, cY + 4),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (255, 255, 255),
                            6,
                        )
                        cv2.putText(
                            image_debug,
                            text,
                            (cX - 4, cY + 4),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            itemColor,
                            2,
                        )

                if self.field.calibrated() and item[0] != "c":
                    new_markers[item] = self.field.pose_of_tag(corners)
                    self.last_updates[item] = time.time()

        self.field.update_calibration(image)
        self.markers = new_markers

    def detect_ball(self, image, image_debug):
        """
        Detects the ball in the image
        """

        # Converts the image to HSV and apply a threshold
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_orange, self.upper_orange)

        # Detect connected components
        output = cv2.connectedComponentsWithStats(mask, 8, cv2.CV_32S)
        num_labels = output[0]
        stats = output[2]
        centroids = output[3]

        # Walk through candidates
        candidates = []
        for k in range(1, num_labels):
            if stats[k][4] > 3:
                candidates.append(list(centroids[k]))
                if len(candidates) > 16:
                    break

        # For each candidate, we will then check which one is the best (closest to previous estimation)
        if len(candidates):
            best = None
            bestPx = None
            bestDist = None
            self.no_ball = 0

            for point in candidates:
                if self.field.calibrated():
                    pos = self.field.pixel_to_position(point, constants.ball_height)
                else:
                    pos = point

                if self.ball:
                    dist = np.linalg.norm(np.array(pos) - np.array(self.ball))
                else:
                    dist = 0

                if best is None or dist < bestDist:
                    bestDist = dist
                    best = pos
                    bestPx = point

            if self.displaySettings["ball"]:
                if image_debug is not None and best:
                    cv2.circle(
                        image_debug,
                        (int(bestPx[0]), int(bestPx[1])),
                        3,
                        (255, 255, 0),
                        3,
                    )

            if self.field.calibrated():
                self.ball = best
        else:
            self.no_ball += 1
            if self.no_ball > 10:
                self.ball = None

    def get_detection(self) -> dict:
        """
        Returns the detection informations

        :return dict: detection informations (ball, markers, field calibration status)
        """
        return {
            "ball": self.ball,
            "markers": self.markers,
            "calibrated": self.field.calibrated(),
            "see_whole_field": self.field.see_whole_field,
            "referee": self.referee.get_game_state(full=False),
        }

    def publish(self) -> None:
        """
        Publish the detection informations on the network
        """
        info = self.get_detection()

        self.socket.send_json(info, flags=zmq.NOBLOCK)

        if self.referee is not None:
            self.referee.detection_info = info
