import yaml
import rsk
import sys
import time

with rsk.Client() as client:

    def show(client, elapsed):
        data = "\n" * 8 + yaml.dump(client.referee, allow_unicode=True, default_flow_style=False)
        sys.stdout.write(data)
        sys.stdout.flush()

    client.on_update = show

    while True:
        time.sleep(1)
