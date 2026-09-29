"""
splat_hub.py -- BLE links to one or more Splats on one radio
=============================================================
ubluetooth.BLE() is a singleton with one IRQ handler, and every
lib/ble_splat.py OpenSplat instance registers its own in __init__, so the
last one built would receive every event. SplatHub builds N SplatLinks,
then takes the IRQ over and routes each event to the one link it belongs
to (OpenSplat also ignores disconnect/GATT events for other connections).

Discover, then connect -- never scan beside a live connection:

1. Discovery: only while no link is connecting, settling or ready, the hub
   runs one scan until it has found an address for every link (pinned
   splat_macs, else the first Splats advertising by name) or DISCOVER_MS
   passes. Found addresses (with their address type) go to the links, in
   order, which then switch to direct mode (SplatLink.direct).
2. Connect: one link at a time, each by connect_direct() to its own
   address -- no scan. A dropped link reconnects the same way.
3. A link whose Splat was not found waits; discovery runs again only once
   no link is up. Switch every Splat on before the hub boots.

Hardware (2026-09-29, XIAO C6): a continuous scan beside a connected
Splat lost that link within about a second, while a 20% duty scan did not
(bench/3b_scan_while_connected.py). With two Splats, starting the second
connection lost the first about 0.1 s later, every time
(docs_and_design/2026-09-29-splat-hub-logs/); cause not yet known --
bench/3c_two_links.py records the negotiated connection parameters.

The connection count is capped at BLE_MAX_CONNECTIONS, the stock
MicroPython ESP32 build's CONFIG_BT_NIMBLE_MAX_CONNECTIONS (4, in
ports/esp32/boards/sdkconfig.ble). A firmware built with a larger value
can raise it here. UNVERIFIED on hardware for more than one Splat.
"""

import time

from splat_link import SplatLink, ST_CONNECTING, ST_SETTLING, ST_READY

BLE_MAX_CONNECTIONS = 4

DISCOVER_MS = 8000             # one discovery scan's longest run
DISCOVER_SCAN = (30000, 30000) # (interval_us, window_us): no link is up

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
        self.discovering = False
        self._disc_until = 0
        self._found = []             # [(addr_str, addr_type, addr_bytes)]
        self.discoveries = 0
        # Registered last: each OpenSplat.__init__ above set its own.
        self._ble = self.links[0]._ble
        self._ble.irq(self._irq)

    @property
    def count(self):
        return len(self.links)

    def _any_up(self):
        for link in self.links:
            if link.state in (ST_CONNECTING, ST_SETTLING, ST_READY):
                return True
        return False

    def _may_scan(self, link):
        """scan_gate for every link: True lets this link start an attempt."""
        if link.direct:
            if self.discovering:
                return False
            for other in self.links:
                if other is not link and other.state in (ST_CONNECTING, ST_SETTLING):
                    return False
            return True
        # No address yet: discovery, which never runs beside a live link.
        if self.discovering:
            self._check_discovery()
        elif not self._any_up():
            self._start_discovery()
        return False

    def _start_discovery(self):
        self._found = []
        try:
            self.links[0]._start_scan(0, DISCOVER_SCAN[0], DISCOVER_SCAN[1])
        except OSError as e:
            print("  SplatHub: discovery scan failed to start: %s" % e)
            return
        self.discovering = True
        self.discoveries += 1
        self._disc_until = time.ticks_add(time.ticks_ms(), DISCOVER_MS)
        print("  SplatHub: discovering (%d Splat(s) wanted)" % self._wanted())

    def _wanted(self):
        return sum(1 for link in self.links if not link.direct)

    def _check_discovery(self):
        if (len(self._found) < self._wanted()
                and time.ticks_diff(self._disc_until, time.ticks_ms()) > 0):
            return
        self.links[0]._stop_scan()
        self.discovering = False
        found = list(self._found)
        for i, link in enumerate(self.links):
            if link.direct:
                continue
            pick = None
            for f in found:
                if self.pinned[i] is None or f[0] == self.pinned[i]:
                    pick = f
                    break
            if pick is None:
                print("  [WARN] SplatHub: no Splat found for unit %d%s; "
                      "discovery runs again when no Splat is connected"
                      % (i, "" if self.pinned[i] is None else " (" + self.pinned[i] + ")"))
                continue
            found.remove(pick)
            link.mac_address, link._addr_type, link.addr = pick
            link.direct = True
            print("  SplatHub: unit %d -> %s" % (i, pick[0]))

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
            if not self.discovering:
                return
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_s = _addr_str(addr)
            for f in self._found:
                if f[0] == addr_s:
                    return
            for link in self.links:
                if link.direct and link.mac_address == addr_s:
                    return          # already assigned to a link
            if addr_s in self.pinned:
                self._found.append((addr_s, addr_type, bytes(addr)))
            elif (None in self.pinned
                    and self.links[0]._parse_adv_name(adv_data) == 'Splat'):
                self._found.append((addr_s, addr_type, bytes(addr)))
        elif event == _IRQ_SCAN_DONE:
            for link in self.links:
                if link._scans_pending > 0:
                    link._irq_handler(event, data)
                    return
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
