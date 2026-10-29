"""Groups and nicknames, kept as JSON on flash."""

import json

PATH = "/flash/panel.json"


class Store:
    def __init__(self):
        self.names = {}     # mac -> nickname
        self.groups = {}    # group name -> [mac]
        try:
            with open(PATH) as f:
                d = json.loads(f.read())
            self.names = d.get("names", {})
            self.groups = d.get("groups", {})
        except Exception:
            pass

    def save(self):
        try:
            with open(PATH, "w") as f:
                f.write(json.dumps({"names": self.names, "groups": self.groups}))
        except Exception as e:
            print(f"# store save failed: {e}")

    def rename(self, mac, name):
        if name:
            self.names[mac] = name
        else:
            self.names.pop(mac, None)
        self.save()

    def add_group(self, name, macs):
        self.groups[name] = list(macs)
        self.save()
