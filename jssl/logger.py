import place
import time
import pandas as pd

data = {'t': [], 'x': [], 'y': []}

start = time.time()
place.controllers['red'].robots[1].kick()
while time.time() - start < 5:
    ball = place.controllers['red'].ball
    if ball is not None:
        data['t'].append(time.time() - start)
        data['x'].append(ball[0])
        data['y'].append(ball[1])
    time.sleep(0.05)

df = pd.DataFrame(data)
df.to_csv('ball.csv')

place.stop_all()