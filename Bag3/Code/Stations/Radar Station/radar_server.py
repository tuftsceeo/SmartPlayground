"""
radar_server.py -- command dispatcher and main loop for the Radar
Station, mirroring the shape of the Icon Display Station's
icon_server.py (see json_link.py's docstring and the top-level plan).

Wire contract: every reply is exactly one JSON object per line. `id`, if
present on a command, is echoed back so the browser can correlate a
response to the request that caused it. While streaming, three message
types go out unsolicited at ~10Hz: `targets` (raw per-sensor detections),
`tracks` (stable tracked objects), and `events` (derived presence/zone/
speed signals) -- kept as separate lines so the web app can show the raw
and derived layers side by side, which is what makes tracker bugs visible
instead of invisible. See the plan's "Wire protocol" section for the
full message shapes.
"""

import time
import gc

from machine import UART

import config
import ld2450
from tracker import Tracker
from events import EventEngine
from json_link import JsonLink

VERSION = "1.0.0"
HEARTBEAT_MS = 5000
STREAM_HZ_DEFAULT = 10
GC_EVERY_N_FRAMES = 64


class RadarServer:
    def __init__(self, debug=False):
        self.uart = UART(
            config.UART_ID, baudrate=config.UART_BAUD,
            bits=8, parity=None, stop=1,
            tx=config.UART_TX, rx=config.UART_RX,
        )
        self.radar = ld2450.LD2450(self.uart, sign_x=config.SIGN_X, sign_y=config.SIGN_Y)
        self.tracker = Tracker(dt_s=1.0 / STREAM_HZ_DEFAULT)
        self.events = EventEngine()
        self.link = JsonLink(self.dispatch, debug=debug)
        self.running = True
        self.streaming = False
        self.raw_mode = False
        self._frames = 0
        self._reboot_hard = False

        self.handlers = {
            "hello": self.do_hello,
            "info": self.do_info,
            "stream": self.do_stream,
            "raw": self.do_raw,
            "mode": self.do_mode,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
        }

    # -- dispatch ------------------------------------------------------
    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        handler = self.handlers.get(name)
        if handler is None:
            self.link.send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        handler(cmd, rid)

    # -- handlers --------------------------------------------------------
    def do_hello(self, cmd, rid):
        self._send_hello(rid)

    def do_info(self, cmd, rid):
        self.link.send({
            "type": "info", "id": rid, "version": VERSION,
            "mem": gc.mem_free(), "streaming": self.streaming,
            "frames_ok": self.radar.frames_ok,
            "frames_dropped": self.radar.frames_dropped,
            "resyncs": self.radar.resyncs,
            "up": time.ticks_ms(),
        })

    def do_stream(self, cmd, rid):
        self.streaming = bool(cmd.get("on", True))
        self.link.send({"type": "stream", "id": rid, "on": self.streaming})

    def do_raw(self, cmd, rid):
        """Hex-dump mode for protocol debugging -- see the plan's Gate A.
        Off by default; not needed once frame_stats/hexdump in
        radar_test.py have confirmed the link is clean."""
        self.raw_mode = bool(cmd.get("on", True))
        self.link.send({"type": "raw", "id": rid, "on": self.raw_mode})

    def do_mode(self, cmd, rid):
        which = cmd.get("value", "multi")
        self.radar.enable_config()
        if which == "single":
            self.radar.set_single_target()
        else:
            self.radar.set_multi_target()
        self.radar.end_config()
        self.link.send({"type": "mode", "id": rid, "value": which})

    def do_repl(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid})
        self.running = False

    def do_reboot(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid, "reboot": "hard" if cmd.get("hard") else "soft"})
        self.running = False
        self._reboot_hard = bool(cmd.get("hard"))

    # -- boot / loop -----------------------------------------------------
    def _send_hello(self, rid=None):
        self.link.send({
            "type": "hello", "id": rid, "version": VERSION,
            "sensors": 1, "baud": config.UART_BAUD,
        })

    def _emit_frame(self, now, targets):
        if self.raw_mode:
            self.link.send({
                "type": "targets", "t": now, "s": 0, "n": len(targets),
                "tg": [{"i": t.i, "x": t.x, "y": t.y, "v": t.speed, "r": t.resolution} for t in targets],
            })
        tracks = self.tracker.update(targets)
        self.link.send({"type": "tracks", "t": now, "tr": [t.to_dict() for t in tracks]})
        ev = self.events.update(tracks)
        ev["type"] = "events"
        ev["t"] = now
        self.link.send(ev)
        self._frames += 1
        if self._frames % GC_EVERY_N_FRAMES == 0:
            gc.collect()

    def run(self):
        self._send_hello()
        last_hb = time.ticks_ms()
        try:
            while self.running:
                self.link.pump(idle_ms=20, drain_ms=40)
                for targets in self.radar.poll():
                    if self.streaming:
                        self._emit_frame(time.ticks_ms(), targets)
                now = time.ticks_ms()
                if time.ticks_diff(now, last_hb) > HEARTBEAT_MS:
                    self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                    last_hb = now
        except KeyboardInterrupt:
            # Deliberately silent: a bare Ctrl-C is almost always a tool
            # (mpremote entering raw REPL, e.g. for `fs cp`) rather than a
            # human at a terminal, and mpremote's raw-REPL handshake sends
            # Ctrl-C expecting silence back -- any stray print here races
            # its parser and was observed to corrupt it (garbled bytes fed
            # back as Python source, `fs cp` failing to enter raw repl).
            # do_repl/do_reboot already sent their own "bye" before this
            # exception path is ever reached, so nothing is lost here.
            pass
        finally:
            if self._reboot_hard:
                import machine
                machine.reset()
