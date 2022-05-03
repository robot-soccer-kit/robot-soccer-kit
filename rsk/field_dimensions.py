import numpy as np 

# Field dimension
length = 1.83  # x axis
width = 1.22   # y axis

# Width of the goal
goal_width = 0.6

# Side of the (green) border we should be able to see around the field
border_size = 0.3

# Dots coordinates
dots_x = 0.445
dots_y = 0.29

# Timed circle
timed_circle_radius = 0.25

# Defense area
defense_area_width = 0.9
defense_area_length = 0.3

# Goals coordinates
def goalsCoord(x_positive:bool = True) -> np.ndarray:
    sign = 1 if x_positive else -1
    
    return np.array([
        [sign * length/2, -goal_width/2.],
        [sign * length/2, goal_width/2]
    ])

# Field coordinates with margins (For goals and sideline)
def fieldCoord(margin: float=0) -> np.ndarray:
    return [
        np.array([sign1*((length / 2.)+margin), sign2*((width / 2.)+margin)])
        for sign1, sign2 in
        [[1, 1], [1, -1], [-1, -1], [-1, 1]]
    ]

def defenseArea(x_positive:bool = True) -> np.ndarray:
    if x_positive:
        return [
            [length/2 - defense_area_length, -defense_area_width/2],
            [length/2 + defense_area_length, defense_area_width/2],
        ]
    else:
        return [
            [-length/2 - defense_area_length, -defense_area_width/2],
            [-length/2 + defense_area_length, defense_area_width/2],
        ]