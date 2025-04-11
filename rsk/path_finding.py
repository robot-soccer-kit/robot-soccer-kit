import numpy as np
import astar
from . import constants

class PathFinding(astar.AStar):
    def __init__(self, discretization: int = 8, avoid_margin = 0.1):
        self.discretization: int = discretization
        self.avoid_margin: float = avoid_margin
        self.reset()

    def reset(self):
        # Obstacles list
        self.obstacles = []
        self.nodes = []

    def angles(self):
        return [k*(2*np.pi/self.discretization) for k in range(self.discretization)]

    def add_obstacle(self, x: float, y: float, radius: float):
        # Storing all obstacles
        self.obstacles.append([x, y, radius])
        for k in self.angles():
            # Storing all nodes
            self.add_node(x + (radius + self.avoid_margin)*np.cos(k), y + (radius + self.avoid_margin)*np.sin(k))

    def add_node(self, x:float, y: float) -> int:
        # Nodes can only be on the field
        x = np.clip(x, -constants.carpet_length/2, constants.carpet_length/2)
        y = np.clip(y, -constants.carpet_width/2, constants.carpet_width/2)

        node = [x, y]
        self.nodes.append(node)
        return len(self.nodes) - 1
    
    def astar(self, start: int, goal: int) -> list:
        self.obstacles = np.array(self.obstacles)
        path = list(super().astar(start, goal))

        for k, node_idx in enumerate(path):
            path[k] = np.array(self.nodes[node_idx])

        return path
    
    def find_target(self, start: int, goal: int, target_distance: float = 0.25) -> list:
        path = self.astar(start, goal)
        if path is None:
            return None
        
        distance = 0.0
        k = 0

        while distance < target_distance and k < len(path) - 1:
            current_target = path[k]
            new_target = path[k+1]
            segment_length = np.linalg.norm(new_target - current_target)
            if distance + segment_length > target_distance:
                remaining = target_distance - distance
                ratio = remaining / segment_length
                return current_target + ratio * (new_target - current_target)
            else:
                distance += segment_length
            k += 1

        return path[k]

    def neighbors(self, node: int) -> list:
        return set(range(len(self.nodes))) - {node}
    
    def distance_between(self, n1: int, n2: int) -> float:
        node1_xy = self.nodes[n1]
        node2_xy = self.nodes[n2]
        distance = np.linalg.norm(np.array(node1_xy) - np.array(node2_xy))

        if len(self.obstacles):
            intersect_ratio = 0
            for obstacle in self.obstacles:
                segment_dx = node2_xy[0] - node1_xy[0]
                segment_dy = node2_xy[1] - node1_xy[1]
                a = segment_dx**2 + segment_dy**2
                x_ca = node1_xy[0] - obstacle[0]
                y_ca = node1_xy[1] - obstacle[1]
                b = 2*(x_ca*segment_dx + y_ca*segment_dy)
                c = x_ca**2 + y_ca**2 - (obstacle[2])**2
                d = b**2 - 4*a*c 
                if d > 0:
                    d = np.sqrt(d)
                    t1 = np.clip((-b - d) / (2*a), 0, 1)
                    t2 = np.clip((-b + d) / (2*a), 0, 1)
                    intersect_ratio = max(intersect_ratio, np.abs(t2 - t1))
                
            distance += 10*intersect_ratio*distance
                
        return distance
    
    def heuristic_cost_estimate(self, current: int, goal: int) -> float:
        node1_xy = self.nodes[current]
        node2_xy = self.nodes[goal]
        return np.linalg.norm(np.array(node1_xy) - np.array(node2_xy))

    
