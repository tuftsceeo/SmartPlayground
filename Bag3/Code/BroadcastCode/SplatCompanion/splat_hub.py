"""
splat_hub.py -- BLE links to one or more Splats on one radio
=============================================================
ubluetooth.BLE() is a singleton with one IRQ handler, and lib/ble_splat.py's
OpenSplat (kept an unmodified byte copy) registers its own handler per
instance and does not filter events by connection. SplatHub builds N
SplatLinks, then takes the IRQ over and routes each event to the one link
it belongs to:

  scan result / scan done (5, 6)   the link currently scanning, after
                                   dropping any address another link owns
                                   and, once the link has a target (pinned,
                                   or learned from a first "Splat"
                                   advertisement), any address but that one
  peripheral connect (7)           the link whose mac_address matches
  disconnect, GATT events (8-18)   the link whose conn_handle matches
                                   (8 falls back to the address)

Only one link scans at a time (SplatLink.scan_gate); the others wait in
IDLE/BACKOFF until it is connected or has given up.

The connection count is capped at BLE_MAX_CONNECTIONS, the stock
MicroPython ESP32 build's CONFIG_BT_NIMBLE_MAX_CONNECTIONS (4, in
ports/esp32/boards/sdkconfig.ble). The companion is BLE central only, so
all of them can be Splats. A firmware built with a larger value can raise
it here. UNVERIFIED on hardware for more than one Splat.
"""

from splat_link import SplatLink, ST_CONNECTING

BLE_MAX_CONNECTIONS = 4

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6
_IRQ_PERIPHERAL_CONNECT = 7
_IRQ_PERIPHERAL_DISCONNECT = 8


def _addr_str(addr):
    return ':'.join(['%02X' % b for b in addr])


class SplatHub:
    def __init__(self, count=1, macs=None):
        """count: Splats to connect (1..BLE_MAX_CONNECTIONS).
        macs: None to take the first Splats found by name, or a list of
        MAC strings ("AB:42:00:00:7E:B6") to pin specific units, in order;
        when given, its length is the count."""
        if macs:
            macs = [m.upper() for m in macs]
            if count != len(macs):
                print("  [WARN] SplatHub: max_splats=%d but %d splat_macs given;"
                      " using %d" % (count, len(macs), len(macs)))
            count = len(macs)
        if count > BLE_MAX_CONNECTIONS:
            print("  [ERR] SplatHub: %d Splats requested, this firmware allows %d"
                  " BLE connections; using %d"
                  % (count, BLE_MAX_CONNECTIONS, BLE_MAX_CONNECTIONS))
            count = BLE_MAX_CONNECTIONS
            if macs:
                macs = macs[:count]
        if count < 1:
            print("  [ERR] SplatHub: %d Splats requested; using 1" % count)
            count = 1
        self.pinned = list(macs) if macs else [None] * count
        self.links = [SplatLink(mac_address=self.pinned[i]) for i in range(count)]
        for link in self.links:
            link.scan_gate = self._may_scan
        self.misrouted = 0
        # Registered last: each OpenSplat.__init__ above set its own.
        self._ble = self.links[0]._ble
        self._ble.irq(self._irq)

    @property
    def count(self):
        return len(self.links)

    def _may_scan(self, link):
        for other in self.links:
            if other is not link and other.state == ST_CONNECTING:
                return False
        return True

    def _scanner(self):
        for link in self.links:
            if link.state == ST_CONNECTING and not link.connected:
                return link
        return None

    def _owned_by_other(self, link, addr):
        for other in self.links:
            if other is not link and other.mac_address == addr:
                return True
        return False

    def _by_conn(self, conn_handle):
        for link in self.links:
            if link._conn_handle == conn_handle:
                return link
        return None

    def _by_addr(self, addr):
        for link in self.links:
            if link.mac_address == addr:
                return link
        return None

    def _irq(self, event, data):
        """BLE IRQ: route to exactly one link, or drop."""
        if event == _IRQ_SCAN_RESULT:
            link = self._scanner()
            if link is None:
                return
            addr = _addr_str(data[1])
            # Lock on: OpenSplat re-picks its target on every "Splat"
            # advertisement until it connects, so with several Splats in
            # range it would chase whichever advertised last.
            if link.mac_address is not None and addr != link.mac_address:
                return
            if self._owned_by_other(link, addr):
                return
            link._irq_handler(event, data)
        elif event == _IRQ_SCAN_DONE:
            for link in self.links:
                if link._scanning:
                    link._irq_handler(event, data)
        elif event == _IRQ_PERIPHERAL_CONNECT:
            link = self._by_addr(_addr_str(data[2]))
            if link is None:
                self.misrouted += 1
                return
            link._irq_handler(event, data)
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            link = self._by_conn(data[0]) or self._by_addr(_addr_str(data[2]))
            if link is None:
                self.misrouted += 1
                return
            link._irq_handler(event, data)
        elif 9 <= event <= 18:
            link = self._by_conn(data[0])
            if link is None:
                self.misrouted += 1
                return
            link._irq_handler(event, data)
