"""
code_link.py -- serve game code to wands over ESP-NOW through the EUM modem.

Takes the place of BDialFirmware/code_server.py (SoftAP + TCP). The Dial
has no radio of its own in use: espnow_manager.py talks to an external
ESP-NOW UART modem (EspnowModem/modem/main.py) over UART1, and
code_sender.CodeSender answers code_req / code_get / code_done from wands
running EspnowModem/MockWandEUM firmware. Stock wands (WiFi code_puller.py)
cannot pull from this Dial.

Serving is continuous: the main loop calls service() every tick in every
mode. There is nothing to arm or disarm.

Host pinning: getcode cards carry "@<HOST_ID>", the wand forwards it in
code_req, and the sender here ignores requests pinned to another id.
HOST_ID is the same value the WiFi Dial derives (last two bytes of
machine.unique_id()), so a card written by either build names this board.
"""

import time
import machine
from binascii import hexlify

import espnow_manager
from espnow_manager import ESPNowManager
from code_sender import CodeSender
from dial_board import EUM_UART_TX, EUM_UART_RX

HOST_ID = hexlify(machine.unique_id()[-2:]).decode()

# Messages handled per service() call. The modem ring holds 128; every
# room broadcast (remotes, status polls) lands there too, so drain several
# per tick rather than one.
MAX_PER_TICK = 8
# While the modem is missing, retry init() this often with a short HELLO
# wait, so a retry costs the UI ~RETRY_HELLO_MS rather than the 2 s boot wait.
RETRY_MS = 5000
RETRY_HELLO_MS = 150


class CodeLink:
    """ESPNowManager + CodeSender, driven from the Dial's main loop.

    on_event(kind, info) receives CodeSender's events ("serving", "done",
    "dropped") plus "modem" (info: {"up": bool, "why": str}) when the modem
    link is established or lost.
    """

    def __init__(self, on_event=None):
        self.on_event = on_event
        # The manager reads the UART pins when the link is first built.
        espnow_manager.UART_TX = EUM_UART_TX
        espnow_manager.UART_RX = EUM_UART_RX
        self.mgr = ESPNowManager()
        self.sender = CodeSender(self.mgr, verbose=True, host_id=HOST_ID,
                                 on_event=self._on_sender_event)
        self.modem_ok = False
        self.modem_error = ""
        self._next_retry = 0

    # ─── modem link ───────────────────────────

    def begin(self):
        """Bring up the modem link. Returns True if the modem answered.

        A missing modem is reported, not raised: card writing still works
        without it, and service() keeps retrying.
        """
        return self._try_init(espnow_manager.HELLO_WAIT_MS)

    def _try_init(self, hello_ms):
        saved = espnow_manager.HELLO_WAIT_MS
        espnow_manager.HELLO_WAIT_MS = hello_ms
        try:
            self.mgr.init()
        except OSError as e:
            self._set_modem(False, str(e))
            self._next_retry = time.ticks_add(time.ticks_ms(), RETRY_MS)
            return False
        finally:
            espnow_manager.HELLO_WAIT_MS = saved
        self._set_modem(True, "")
        return True

    def _set_modem(self, up, why):
        changed = up != self.modem_ok or why != self.modem_error
        self.modem_ok = up
        self.modem_error = why
        if changed:
            print("# [eum] modem %s%s" % ("up" if up else "DOWN",
                                         (": " + why) if why else ""))
            self._emit("modem", {"up": up, "why": why})

    def _link_down(self):
        link = espnow_manager._link
        return link is not None and link.down

    # ─── per-tick service ─────────────────────

    def service(self):
        """Handle up to MAX_PER_TICK queued ESP-NOW messages. Never blocks
        longer than one modem round trip per message (plus the frames a
        code_get asks for)."""
        if not self.modem_ok:
            if time.ticks_diff(time.ticks_ms(), self._next_retry) >= 0:
                self._try_init(RETRY_HELLO_MS)
            return
        for _ in range(MAX_PER_TICK):
            mt, data, mac = self.mgr.poll()
            if mt is None:
                break
            self.sender.handle(mt, data, mac)
        # The manager reconnects on its own while the link is down; mirror
        # its state so the screen and `info` can say so.
        down = self._link_down()
        if down and not self.modem_error:
            self.modem_error = "link down"
            print("# [eum] modem link down (reconnecting)")
            self._emit("modem", {"up": True, "why": "link down"})
        elif not down and self.modem_error == "link down":
            self.modem_error = ""
            print("# [eum] modem link restored")
            self._emit("modem", {"up": True, "why": ""})

    @property
    def linked(self):
        """True when the modem answered init() and the link is not down."""
        return self.modem_ok and not self.modem_error

    @property
    def serving_count(self):
        return len(self.sender.sessions)

    def stats(self):
        """Counters for the Dial's `info` reply."""
        return {
            "modem": self.linked,
            "modem_error": self.modem_error or None,
            "wands": self.serving_count,
            "served": self.sender.served,
            "failed": self.sender.failed,
            "busy_replies": self.sender.busy_replies,
            "ignored": self.sender.ignored,
        }

    def shutdown(self):
        """Close open sessions and deactivate the modem's RX queue."""
        for s in self.sender.sessions.values():
            s.close()
        self.sender.sessions.clear()
        if self.modem_ok:
            self.mgr.shutdown()

    # ─── events ───────────────────────────────

    def _on_sender_event(self, kind, info):
        self._emit(kind, info)

    def _emit(self, kind, info):
        if self.on_event is not None:
            self.on_event(kind, info)
