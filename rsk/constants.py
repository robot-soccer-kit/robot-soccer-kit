import numpy as np 

"""
This file contains all relevant constants. It can be dimension of items or values from
the rules.
"""

# Field dimension
field_length:float = 1.83 # [m] (x axis)
field_width:float = 1.22 # [m] (y axis)

# Width of the goal
goal_width:float = 0.6 # [m]

# Side of the (green) border we should be able to see around the field
border_size:float = 0.3 # [m]

# Dots coordinates (x, y)
dots_x:float = 0.445 # [m]
dots_y:float = 0.29 # [m]

# Defense area
defense_area_width = 0.9 # [m]
defense_area_length = 0.3 # [m]

# Timed circle radius and maximum time before being penalized
timed_circle_radius:float = 0.25 # [s]
timed_circle_time:float = 5 # [s]

# Margin for ball re-placement (on the center or on dots)
place_ball_margin:float = 0.05 # [m]

# Margins for being in and out the field
field_in_margin:float = -0.08 # [m]
field_out_margin:float = 0.02 # [m]

# Tag sizes
corner_tag_size:float = 0.16 # [m]
corner_tag_border:float = 0.025 # [m]
robot_tag_size:float = 0.08 # [m]

# Heights
robot_height:float = 0.076 # [m]
ball_height:float = 0.042 # [m]

# Goals coordinates
def goal_posts(x_positive:bool = True) -> np.ndarray:
    sign = 1 if x_positive else -1
    
    return np.array([
        [sign * field_length/2, -goal_width/2.],
        [sign * field_length/2, goal_width/2]
    ])

# Field coordinates with margins (For goals and sideline)
def field_corners(margin: float=0) -> np.ndarray:
    return [
        np.array([sign1*((field_length / 2.)+margin), sign2*((field_width / 2.)+margin)])
        for sign1, sign2 in
        [[1, 1], [1, -1], [-1, -1], [-1, 1]]
    ]

# Returns the defense area rectangle
def defense_area(x_positive:bool = True) -> np.ndarray:
    if x_positive:
        return [
            [field_length/2 - defense_area_length, -defense_area_width/2],
            [field_length/2 + defense_area_length, defense_area_width/2],
        ]
    else:
        return [
            [-field_length/2 - defense_area_length, -defense_area_width/2],
            [-field_length/2 + defense_area_length, defense_area_width/2],
        ]