"""Fake `espnow` module — import safety only."""


class ESPNow:
    def __init__(self, *a, **k):
        pass

    def active(self, *a, **k):
        return True

    def send(self, *a, **k):
        return None

    def recv(self, *a, **k):
        return None

    def irq(self, *a, **k):
        pass

    def peers_table(self):
        return {}

    def add_peer(self, *a, **k):
        pass

    def del_peer(self, *a, **k):
        pass
