import numpy as np
import cv2

class Field:
    def __init__(self):
        self.corner_tag_size = 0.072
        self.robot_tag_size = 0.08
        self.corner_ids = [0,5,25,20]
        self.field_shape = [1.2,1.82]
        self.frame_point_list = None
        self.id_gfx_corners = {}
        self.homography = None
        
    def set_id_gfx_corners(self, id, corners):
        self.id_gfx_corners[id] = corners

    def update_homography(self):
        gframe = self.get_gfx_frame()
        if gframe is not None:
            H,mask = cv2.findHomography(gframe, self.get_frame_point_list())
            if self.homography is None:
                print('- homography ready')
                self.homography = H
        
    def pos_of_gfx(self, pos):
        M = np.ndarray(shape=(3,1), buffer = np.array([[pos[0]], [pos[1]], [1.0]]))
        result = np.dot(self.homography,M)
        return [ result[0], result[1] ]

    def pose_of_tag(self, id):
        try:
            if id not in self.id_gfx_corners: return None
            if self.homography is None: return None
            pts = self.id_gfx_corners[id]
            def f(v): return np.array(self.pos_of_gfx(np.array([v[0], v[1]])))
            pts = dict(map(lambda kv: (kv[0], f(kv[1])), self.id_gfx_corners[id].items()))
            center = (pts['topLeft'] + pts['bottomRight'])/2
            dir = (pts['topLeft'] + pts['topRight'])/2 - center
            orient = np.degrees(np.arctan2(dir[1], dir[0]))
            return { 'center' : (float(center[0]) - self.field_shape[1]/2, float(center[1]) - self.field_shape[0]/2),
                     'orient' : float(orient[0]) }
        except:
            raise
            return None
        
    def get_frame_point_list(self):
        if self.frame_point_list is not None:
            return self.frame_point_list 
        pts = []
        for (x,y) in [ (0,0), (0,1), (1,1), (1,0) ]:
            def npa(a,b): return np.array([a,b])
            h = self.corner_tag_size / 2
            lx = self.field_shape[1]
            ly = self.field_shape[0]
            C = np.array([x*lx, y*ly])
            pts.append(C-npa(-h,-h))
            pts.append(C-npa(-h,h))
            pts.append(C-npa(h,h))
            pts.append(C-npa(h,-h))
        pts = list(map(lambda p: [p[0],p[1]], pts))
        self.frame_point_list = np.array(pts)
        return self.frame_point_list

    def get_gfx_frame(self):
        pts = []
        for c in self.corner_ids:
            if c not in self.id_gfx_corners: return None
            pts.append(self.id_gfx_corners[c]['topLeft'])
            pts.append(self.id_gfx_corners[c]['topRight'])
            pts.append(self.id_gfx_corners[c]['bottomRight'])
            pts.append(self.id_gfx_corners[c]['bottomLeft'])
        return np.array(pts)
