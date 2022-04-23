import numpy as np
import cv2
import zmq
import time
from .field import Field
from . import field_dimensions, config
import os 

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

class Detection:
    def __init__(self):
        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.set_hwm(1)
        self.socket.bind("tcp://*:7557")

        # ArUco parameters
        self.arucoDict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        self.arucoParams = cv2.aruco.DetectorParameters_create()
        # arucoParams.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_APRILTAG

        #Goals Colors
        self.color_xpos = (0, 255, 0)
        self.color_xneg = (255, 0, 0)
        
        self.displaySettings = {
            'aruco': True,
            'goals': True,
            'ball': True,
            'exclusion_circle': False,
            'sideline': False,
            'landmark': True
        }

        if 'display_settings' in config.config:
            for entry in config.config['display_settings']:
                self.displaySettings[entry] = config.config['display_settings'][entry]

        self.arucoItems = {
            # Corners
            0: ['c1', (128, 128, 0)],
            1: ['c2', (128, 128, 0)],
            2: ['c3', (128, 128, 0)],
            3: ['c4', (128, 128, 0)],

            # Green
            4: ['green1', (0, 128, 0)],
            5: ['green2', (0, 128, 0)],

            # Blue
            6: ['blue1', (128, 0, 0)],
            7: ['blue2', (128, 0, 0)],

            # Generic objects
            8: ['obj1', (128, 128, 0)],
            9: ['obj2', (128, 128, 0)],
            10: ['obj3', (128, 128, 0)],
            11: ['obj4', (128, 128, 0)],
            12: ['obj5', (128, 128, 0)],
            13: ['obj6', (128, 128, 0)],
            14: ['obj7', (128, 128, 0)],
            15: ['obj8', (128, 128, 0)],
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

        self.on_update = None

        self.ball_height = 0.042
        if 'camera_height' in config.config:
            if 'camera_height' in config.config['camera_height']:
                self.field.camera_height = config.config['camera_height']['camera_height']

    def setDisplaySettings(self, display_settings: list) -> list: 
        display_settings_bool = []
        for i in range(len(display_settings)):
            if display_settings[i] == 'on':
                display_settings_bool.append(True)
            else :
                display_settings_bool.append(False)
        self.displaySettings['aruco'] = display_settings_bool[0]
        self.displaySettings['goals'] = display_settings_bool[1]
        self.displaySettings['ball'] = display_settings_bool[2]
        self.displaySettings['exclusion_circle'] = display_settings_bool[3]
        self.displaySettings['sideline'] = display_settings_bool[4]
        self.displaySettings['landmark'] = display_settings_bool[5]

    def getDisplaySettings(self):
        display_settings_bool = []
        display_settings_bool.append(self.displaySettings['aruco'])
        display_settings_bool.append(self.displaySettings['goals'])
        display_settings_bool.append(self.displaySettings['ball'])
        display_settings_bool.append(self.displaySettings['exclusion_circle'])
        display_settings_bool.append(self.displaySettings['sideline'])
        display_settings_bool.append(self.displaySettings['landmark'])
        return(display_settings_bool)

    def getDefaultDisplaySettings(self):
        display_settings_bool = [True, True, True, False, False, True]
        return(display_settings_bool)

    def saveDisplaySettings(self):
        config.config['display_settings'] = {
            'aruco': self.displaySettings['aruco'],
            'goals': self.displaySettings['goals'],
            'ball': self.displaySettings['ball'],
            'exclusion_circle': self.displaySettings['exclusion_circle'],
            'sideline':  self.displaySettings['sideline'],
            'landmark': self.displaySettings['landmark']
        }
        config.save()

    def calibrateCamera(self):
        self.field.should_calibrate = True
    
    def MidTimeChangeColorField(self):
        if self.color_xpos == (0, 255, 0):
            self.color_xpos = (255, 0, 0)
            self.color_xneg = (0, 255, 0)
            return "blue"
        else:
            self.color_xpos = (0, 255, 0)
            self.color_xneg = (255, 0, 0)
            return "green"


    def detectAruco(self, image, image_debug = None):

        (corners, ids, rejected) = cv2.aruco.detectMarkers(image,
                                                           self.arucoDict,
                                                           parameters=self.arucoParams)
        new_markers = {}



        if self.field.calibrated() and image_debug is not None:
            if self.displaySettings['sideline']:
                [field_UpRight, field_DownRight, field_DownLeft, field_UpLeft] = field_dimensions.fieldCoordMargin(-0.1)
                A = self.field.position_to_pixel(field_UpRight)
                B = self.field.position_to_pixel(field_DownRight)
                C = self.field.position_to_pixel(field_DownLeft)
                D = self.field.position_to_pixel(field_UpLeft)
                cv2.line(image_debug, A, B, (0, 255, 0), 1)
                cv2.line(image_debug, B, C, (0, 255, 0), 1)
                cv2.line(image_debug, C, D, (0, 255, 0), 1)
                cv2.line(image_debug, D, A, (0, 255, 0), 1)

                [field_UpRight, field_DownRight, field_DownLeft, field_UpLeft] = field_dimensions.fieldCoordMargin(0.02)
                A = self.field.position_to_pixel(field_UpRight)
                B = self.field.position_to_pixel(field_DownRight)
                C = self.field.position_to_pixel(field_DownLeft)
                D = self.field.position_to_pixel(field_UpLeft)
                cv2.line(image_debug, A, B, (0, 0, 255), 1)
                cv2.line(image_debug, B, C, (0, 0, 255), 1)
                cv2.line(image_debug, C, D, (0, 0, 255), 1)
                cv2.line(image_debug, D, A, (0, 0, 255), 1)

            if self.displaySettings['goals']:
                for sign, color in [(-1, self.color_xneg), (1, self.color_xpos)]:
                    C = self.field.position_to_pixel([sign*(field_dimensions.length / 2.), -sign*field_dimensions.goal_width / 2.])
                    D = self.field.position_to_pixel([sign*(field_dimensions.length / 2.), sign*field_dimensions.goal_width / 2.])
                    cv2.line(image_debug, C, D, color, 5)
                    for post in [-1, 1]:
                        A = self.field.position_to_pixel([sign*(.05 + field_dimensions.length / 2.), post*field_dimensions.goal_width / 2.])
                        B = self.field.position_to_pixel([sign*(field_dimensions.length / 2.), post*field_dimensions.goal_width / 2.])
                        cv2.line(image_debug, A, B, color, 5)
            if self.displaySettings['landmark']:
                A = self.field.position_to_pixel([0, 0])
                B = self.field.position_to_pixel([0.2, 0])
                cv2.line(image_debug, A, B, (0, 0, 255), 1)
                A = self.field.position_to_pixel([0, 0])
                B = self.field.position_to_pixel([0, 0.2])
                cv2.line(image_debug, A, B, (0, 255, 0), 1)


                
        if len(corners) > 0:
            for (markerCorner, markerID) in zip(corners, ids.flatten()):
                if markerID not in self.arucoItems:
                    continue

                corners = markerCorner.reshape((4, 2))

                # Draw the bounding box of the ArUCo detection
                item = self.arucoItems[markerID][0]

                if item[0] == 'c':
                    self.field.set_corner_position(item, corners)

                if image_debug is not None:
                    (topLeft, topRight, bottomRight, bottomLeft) = corners
                    topRight = (int(topRight[0]), int(topRight[1]))
                    bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
                    bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
                    topLeft = (int(topLeft[0]), int(topLeft[1]))
                    itemColor = self.arucoItems[markerID][1]
                    if self.displaySettings['aruco']:
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
                        cv2.line(image_debug, (cX, cY), (cX+2*(fX-cX), cY+2*(fY-cY)), (0, 0, 255), 2)

                        text = item
                        if item.startswith('blue') or item.startswith('green'):
                            text = item[-1]
                        cv2.putText(image_debug, text, (cX-4, cY+4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 6)
                        cv2.putText(image_debug, text, (cX-4, cY+4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, itemColor, 2)

                if self.field.calibrated() and item[0] != 'c':
                    new_markers[item] = self.field.pose_of_tag(corners)
                    self.last_updates[item] = time.time()

        self.field.update_calibration(image)
        self.markers = new_markers

    def detectBall(self, image, image_debug):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_orange, self.upper_orange)
        
        output = cv2.connectedComponentsWithStats(mask, 8, cv2.CV_32S)
        num_labels = output[0]
        stats = output[2]
        centroids = output[3]

        candidates = []
        for k in range(1, num_labels):
            if stats[k][4] > 3:
                candidates.append(list(centroids[k]))
                if len(candidates) > 16:
                    break

        if len(candidates):
            best = None
            bestPx = None
            bestDist = None
            self.no_ball = 0

            for point in candidates:
                if self.field.calibrated():
                    pos = self.field.pixel_to_position(point, self.ball_height)
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

            if self.displaySettings['ball']:
                if image_debug is not None and best:
                    cv2.circle(image_debug, (int(bestPx[0]), int(
                        bestPx[1])), 3, (255, 255, 0), 3)

            if self.field.calibrated():
                self.ball = best
        else:
            self.no_ball += 1
            if self.no_ball > 10:
                self.ball = None

    def getDetection(self):
        return {
            'ball': self.ball,
            'markers': self.markers,
            'calibrated': self.field.calibrated(),
            'see_whole_field': self.field.see_whole_field,
        }

    def publish(self):
        info = self.getDetection()

        self.socket.send_json(info, flags=zmq.NOBLOCK)
        if self.on_update is not None:
            self.on_update(info)

    def setCameraheight(self, camera_height):
        self.field.camera_height = camera_height
        config.config['camera_height'] = {
            'camera_height': self.field.camera_height
        }
        config.save()

    def getCameraheight(self):
        return self.field.camera_height
