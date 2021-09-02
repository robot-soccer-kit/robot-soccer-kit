import numpy as np
import cv2

# ArUco parameters
arucoDict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
arucoParams = cv2.aruco.DetectorParameters_create()
arucoItems = {
    0: 'c1',
    1: 'c2',
    2: 'c3',
    3: 'c4',
    
    4: 'r1',
    5: 'r2',
    
    6: 'b1',
    7: 'b2',
}
arucoColors = {
    'c': (0, 255, 0),
    'r': (0, 0, 128),
    'b': (128, 0, 0)
}

# Ball parameters
lower_orange = np.array([5, 200, 200])
upper_orange = np.array([20, 255, 255])

# Detection output
markers = {}
ball = None

def detectAruco(image):
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
            (topLeft, topRight, bottomRight, bottomLeft) = corners
            # convert each of the (x, y)-coordinate pairs to integers
            topRight = (int(topRight[0]), int(topRight[1]))
            bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
            bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
            topLeft = (int(topLeft[0]), int(topLeft[1]))

            # field.set_id_gfx_corners(int(markerID),
            #                             {
            #                                 'topRight' : (float(topRight[0]), float(topRight[1])),
            #                                 'bottomRight' : (float(bottomRight[0]), float(bottomRight[1])),
            #                                 'bottomLeft' : (float(bottomLeft[0]), float(bottomLeft[1])),
            #                                 'topLeft' : (float(topLeft[0]), float(topLeft[1]))
            #                             })
        
            # Draw the bounding box of the ArUCo detection
            item = arucoItems[markerID]
            itemColor = arucoColors[item[0]]
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

            new_markers[item] = [cX, cY]

    if len(new_markers):
        markers = new_markers

def detectBall(image):
    global ball

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_orange, upper_orange)
    result = cv2.bitwise_and(image, image, mask = mask)
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    blob_params = cv2.SimpleBlobDetector_Params()
    blob_params.minThreshold = 1
    blob_params.maxThreshold = 255
    blob_params.filterByArea = False
    blob_params.filterByCircularity = False
    blob_params.filterByConvexity = False
    blob_params.filterByInertia = False
    blob_params.filterByColor = True
    blob_params.blobColor = 255
    detector = cv2.SimpleBlobDetector_create(blob_params)
    keypoints = detector.detect(gray)
    cv2.drawKeypoints(image, keypoints, image, (255, 255, 255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

    if len(keypoints):
        position = keypoints[0].pt
        ball = [int(position[0]), int(position[1])]

def getDetection():
    global ball, markers

    return {'ball': ball, 'markers': markers}