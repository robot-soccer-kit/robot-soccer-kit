import numpy as np
import cv2
from field import Field
import zmq

# Publishing server
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:7557")

# ArUco parameters
arucoDict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
arucoParams = cv2.aruco.DetectorParameters_create()

arucoItems = { 
    # Corners
    0: ['c1', (0, 255, 0)],
    1: ['c2', (0, 255, 0)],
    2: ['c3', (0, 255, 0)],
    3: ['c4', (0, 255, 0)],
    
    # Red
    4: ['red1', (0, 0, 128)],
    5: ['red2', (0, 0, 128)],
    
    # Blue
    6: ['blue1', (128, 0, 0)],
    7: ['blue2', (128, 0, 0)],
}

# Ball parameters
lower_orange = np.array([5, 150, 150])
upper_orange = np.array([25, 255, 255])

# Detection output
markers = {}
ball = None
no_ball = 0
field = Field()

def detectAruco(image, draw_debug):
    global markers

    (corners, ids, rejected) = cv2.aruco.detectMarkers(image,
                                                           arucoDict,
                                                           parameters=arucoParams)                                               
    new_markers = {}

    if len(corners) > 0:
        for (markerCorner, markerID) in zip(corners, ids.flatten()):
            if markerID not in arucoItems:
                continue

            corners = markerCorner.reshape((4, 2))
        
            # Draw the bounding box of the ArUCo detection
            item = arucoItems[markerID][0]

            if item[0] == 'c':
                field.set_corner_position(item, corners)

            if draw_debug:
                (topLeft, topRight, bottomRight, bottomLeft) = corners
                topRight = (int(topRight[0]), int(topRight[1]))
                bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
                bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
                topLeft = (int(topLeft[0]), int(topLeft[1]))
                itemColor = arucoItems[markerID][1]
                cv2.line(image, topLeft, topRight, itemColor, 2)
                cv2.line(image, topRight, bottomRight, itemColor, 2)
                cv2.line(image, bottomRight, bottomLeft, itemColor, 2)
                cv2.line(image, bottomLeft, topLeft, itemColor, 2)

                # Compute and draw the center (x, y)-coordinates of the
                # ArUco marker
                cX = int((topLeft[0] + bottomRight[0]) / 2.0)
                cY = int((topLeft[1] + bottomRight[1]) / 2.0)
                cv2.circle(image, (cX, cY), 4, (0, 0, 255), -1)
                fX = int((topLeft[0] + topRight[0]) / 2.0)
                fY = int((topLeft[1] + topRight[1]) / 2.0)
                cv2.line(image, (cX, cY), (fX, fY), (0, 0, 255), 2)

                cv2.putText(image, item, (cX-8, cY+4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, itemColor, 2)

            if field.calibrated() and item[0] != 'c':
                new_markers[item] = field.pose_of_tag(corners)

    field.update_homography(image)

    markers = new_markers

def detectBall(image, draw_debug):
    global ball, no_ball

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_orange, upper_orange)
    result = cv2.bitwise_and(image, image, mask = mask)
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    blob_params = cv2.SimpleBlobDetector_Params()
    blob_params.minThreshold = 1
    blob_params.maxThreshold = 255
    blob_params.filterByCircularity = False
    blob_params.filterByConvexity = False
    blob_params.filterByInertia = False
    blob_params.filterByColor = True
    blob_params.blobColor = 255
    blob_params.minDistBetweenBlobs = 50
    detector = cv2.SimpleBlobDetector_create(blob_params)
    keypoints = detector.detect(gray)

    if len(keypoints):
        best = None
        bestPx = None
        bestDist = None
        no_ball = 0

        for point in keypoints:
            if field.calibrated():
                pos = field.pos_of_gfx(point.pt)
            else:
                pos = point.pt

            if ball:
                dist = np.linalg.norm(np.array(pos) - np.array(ball))
            else:
                dist = 0

            if best is None or dist < bestDist:
                bestDist = dist
                best = pos
                bestPx = point.pt

        ball = best

        if draw_debug and ball:
            cv2.circle(image, (int(bestPx[0]), int(bestPx[1])), 3, (255, 255, 0), 3)
    else:
        no_ball += 1
        if no_ball > 10:
            ball = None

def getDetection():
    global ball, markers

    return {'ball': ball, 'markers': markers, 'calibrated': field.calibrated()}

def publish():
    socket.send_json(getDetection(), flags=zmq.NOBLOCK)
