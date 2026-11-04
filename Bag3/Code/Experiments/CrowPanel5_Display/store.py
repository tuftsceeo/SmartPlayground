"""Groups, nicknames and the NFC Write History, kept as JSON on flash."""

import json

PATH = "/flash/panel.json"
HISTORY = 6


class Store:
    def __init__(self):
        self.names = {}     # mac -> nickname
        self.groups = {}    # group name -> [mac]
        self.history = []   # texts written on the NFC Write tab, newest first
        try:
            with open(PATH) as f:
                d = json.loads(f.read())
            self.names = d.get("names", {})
            self.groups = d.get("groups", {})
            self.history = d.get("history", [])
        except Exception:
            pass

    def save(self):
        try:
            with open(PATH, "w") as f:
                f.write(json.dumps({"names": self.names, "groups": self.groups, "history": self.history}))
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

    def remember(self, text):
        """Put text at the top of the Write History."""
        if text in self.history:
            self.history.remove(text)
        self.history.insert(0, text)
        del self.history[HISTORY:]
        self.save()
