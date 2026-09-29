"""
splat_link.py -- non-blocking BLE link to one Splat
===================================================
SplatLink subclasses OpenSplat (lib/ble_splat.py, a byte copy of
Bag3/Code/lib/ble_splat.py) and
replaces its blocking connect() with a state machine advanced by
service(now), so the main loop keeps polling ESP-NOW while BLE scans,
connects, discovers services, and reconnects.

Splat button notifications arrive in the BLE IRQ handler. SplatLink
overrides OpenSplat._handle_button so the IRQ only records raw state
changes with their time. service() debounces them in the main loop and
queues accepted events (1 = press, 0 = release); take_events() hands them
to the caller. After a rejected change the latest raw state is re-checked
once DEBOUNCE_MS has passed, so a tap shorter than DEBOUNCE_MS still ends
in a release without waiting for another notification.

States: IDLE -> CONNECTING -> SETTLING -> READY. A CONNECTING attempt that
is not ready after CONNECT_TIMEOUT_MS is torn down and retried after
RETRY_BACKOFF_MS. A drop from READY starts a new attempt immediately.

scan_gate, when set (splat_hub.SplatHub sets it), is called as
scan_gate(link) before every new attempt; while it returns False the link
waits in IDLE/BACKOFF. The hub uses it so only one link scans at a time.
"""

import errno
import time

from ble_splat import OpenSplat


CONNECT_TIMEOUT_MS = 20000
RETRY_BACKOFF_MS = 2000
READY_SETTLE_MS = 200        # lets the IRQ's CCCD subscribe write go out first
EVENT_QUEUE_MAX = 16
DEBOUNCE_MS = 80             # same window as ble_splat._DEBOUNCE_MS

ST_IDLE = 0
ST_CONNECTING = 1
ST_SETTLING = 2
ST_READY = 3
ST_BACKOFF = 4

STATE_NAMES = ("idle", "connecting", "settling", "ready", "backoff")


class SplatLink(OpenSplat):
    def __init__(self, mac_address=None, verbose=False):
        super().__init__(mac_address=mac_address, verbose=verbose)
        # A pinned link keeps its address; an unpinned one forgets the
        # Splat it picked after a failed attempt, so the next attempt can
        # pick another. A drop from READY keeps it (reconnect to the same).
        self.pinned = mac_address is not None
        self._raw_q = []             # (ticks_ms, pressed), appended in the IRQ
        self._irq_raw = False        # last raw state seen by the IRQ
        self._raw = False            # last raw state seen by the main loop
        self._last_change = 0
        self._events = []
        self.state = ST_IDLE
        self._t = 0
        self.attempts = 0
        self.connects = 0
        self.drops = 0
        self.failed_attempts = 0
        self.events_dropped = 0
        self.scan_already = 0
        self.scan_gate = None
        # gap_scan (interval_us, window_us). Equal values scan continuously,
        # which is right with no connection up; SplatHub lowers the duty
        # while another Splat is connected so its link is not starved.
        self.scan_params = (30000, 30000)

    # ─── IRQ side ─────────────────────────────

    def _handle_button(self, value):
        """Override: runs in the BLE IRQ. Records raw changes only."""
        pressed = bool(value & 0x0F)
        if pressed == self._irq_raw:
            return
        self._irq_raw = pressed
        if len(self._raw_q) >= EVENT_QUEUE_MAX:
            self.events_dropped += 1
            return
        self._raw_q.append((time.ticks_ms(), pressed))

    # ─── Main-loop side ───────────────────────

    @property
    def ready(self):
        return self.state == ST_READY

    def state_name(self):
        return STATE_NAMES[self.state]

    def _debounce(self, now):
        q = self._raw_q
        if q:
            self._raw_q = []
            for t, pressed in q:
                self._raw = pressed
                self._accept(t)
        self._accept(now)

    def _accept(self, t):
        if (self._raw != self.splat_pressed and
                time.ticks_diff(t, self._last_change) >= DEBOUNCE_MS):
            self.splat_pressed = self._raw
            self._last_change = t
            self._events.append(1 if self._raw else 0)

    def take_events(self):
        """Return button events accepted since the last call (oldest first)."""
        ev = self._events
        if not ev:
            return ()
        self._events = []
        return ev

    def _may_begin(self):
        return self.scan_gate is None or self.scan_gate(self)

    def service(self, now):
        st = self.state
        if st == ST_READY:
            if not self.connected:
                self.drops += 1
                print("  SplatLink: connection to %s lost (drops=%d)"
                      % (self.mac_address, self.drops))
                self.state = ST_IDLE
                if self._may_begin():
                    self._begin(now)
            else:
                self._debounce(now)
            return
        if st == ST_IDLE:
            if self._may_begin():
                self._begin(now)
        elif st == ST_BACKOFF:
            if (time.ticks_diff(now, self._t) >= RETRY_BACKOFF_MS
                    and self._may_begin()):
                self._begin(now)
        elif st == ST_CONNECTING:
            if self.connected and self._tx_char_handle and self._rx_char_handle:
                self.state = ST_SETTLING
                self._t = now
            elif time.ticks_diff(now, self._t) >= CONNECT_TIMEOUT_MS:
                self._give_up(now)
            elif not self.connected and not self._scanning and not self._connecting:
                # The IRQ stops the scan when it first sees a "Splat" by name
                # and records its MAC; the next scan connects to that MAC.
                self._scan(now)
        elif st == ST_SETTLING:
            if not self.connected:
                self.drops += 1
                print("  SplatLink: dropped while settling")
                self.state = ST_IDLE
                if self._may_begin():
                    self._begin(now)
            elif time.ticks_diff(now, self._t) >= READY_SETTLE_MS:
                self.state = ST_READY
                self.connects += 1
                print("  SplatLink: ready, Splat %s (connects=%d)"
                      % (self.mac_address, self.connects))

    def _begin(self, now):
        self._ble.active(True)
        self._reset_connection_state()
        self._raw_q = []
        self._irq_raw = self._raw = self.splat_pressed = False
        self._events = []
        self.attempts += 1
        self.state = ST_CONNECTING
        self._t = now
        self._scan(now)

    def _scan(self, now):
        try:
            self._start_scan(0, self.scan_params[0], self.scan_params[1])
        except OSError as e:
            if e.args and e.args[0] == errno.EALREADY:
                # The radio is still scanning (another caller's scan, or
                # one this driver lost track of): counted, retried next
                # service().
                self.scan_already += 1
                print("  SplatLink: gap_scan EALREADY (count=%d)" % self.scan_already)
                return
            print("  SplatLink: gap_scan failed: %s" % str(e))
            self._give_up(now)

    def _give_up(self, now):
        self.failed_attempts += 1
        if not self.pinned:
            self.mac_address = None
        print("  SplatLink: attempt %d not ready after %d ms (failed=%d), "
              "retry in %d ms" % (self.attempts, time.ticks_diff(now, self._t),
                                  self.failed_attempts, RETRY_BACKOFF_MS))
        self._teardown()
        self.state = ST_BACKOFF
        self._t = now

    def _teardown(self):
        self._stop_scan()
        if self._connecting and not self.connected:
            try:
                self._ble.gap_connect(None)     # cancel the pending connect
            except OSError as e:
                print("  SplatLink: cancel connect failed: %s" % str(e))
        if self._conn_handle is not None:
            try:
                self._ble.gap_disconnect(self._conn_handle)
            except OSError as e:
                print("  SplatLink: disconnect failed: %s" % str(e))
        self._reset_connection_state()

    def close(self):
        """Disconnect. The next service() call starts a new attempt."""
        self._teardown()
        self.state = ST_IDLE
