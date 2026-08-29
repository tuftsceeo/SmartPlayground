"""
radar_server.py -- command dispatcher and main loop, NDJSON over USB
serial. Every reply is one JSON object per line; `id` on a command is
echoed in its reply. While streaming, at ~10Hz: `targets` (raw
detections, raw_mode only), `tracks` (tracked objects), `events`
(derived signals) -- three separate lines.
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
GC_EVERY_N_FRAMES = 64


class RadarServer:
    def __init__(self, debug=False):
        self.uart = UART(
            config.UART_ID, baudrate=config.UART_BAUD,
            bits=8, parity=None, stop=1,
            tx=config.UART_TX, rx=config.UART_RX,
        )
        self.radar = ld2450.LD2450(self.uart, sign_x=config.SIGN_X, sign_y=config.SIGN_Y)
        self.tracker = Tracker()
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
            "tune": self.do_tune,
            "version": self.do_version,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
        }

    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        handler = self.handlers.get(name)
        if handler is None:
            self.link.send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        handler(cmd, rid)

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

    def do_version(self, cmd, rid):
        v = self.radar.read_version()
        v["type"] = "version"
        v["id"] = rid
        self.link.send(v)

    def do_tune(self, cmd, rid):
        """Live-adjust tracker/event thresholds. Any field omitted keeps
        its current value; {"cmd":"tune"} alone is a pure read. Tracker
        params (alpha/gate_mm/max_misses) go through Tracker.set_params();
        event thresholds (speed_walk/speed_run/presence_drop) mutate the
        config module directly -- events.py reads them fresh every call,
        no caching to invalidate."""
        self.tracker.set_params(
            gate_mm=cmd.get("gate_mm"),
            max_misses=cmd.get("max_misses"),
            alpha=cmd.get("alpha"),
        )
        if "speed_walk" in cmd:
            config.SPEED_WALK_MM_S = cmd["speed_walk"]
        if "speed_run" in cmd:
            config.SPEED_RUN_MM_S = cmd["speed_run"]
        if "presence_drop" in cmd:
            config.PRESENCE_DROP_FRAMES = cmd["presence_drop"]
        self.link.send({
            "type": "tune", "id": rid,
            "alpha": self.tracker.alpha,
            "gate_mm": int(self.tracker.gate2 ** 0.5),
            "max_misses": self.tracker.max_misses,
            "speed_walk": config.SPEED_WALK_MM_S,
            "speed_run": config.SPEED_RUN_MM_S,
            "presence_drop": config.PRESENCE_DROP_FRAMES,
        })

    def do_repl(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid})
        self.running = False

    def do_reboot(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid, "reboot": "hard" if cmd.get("hard") else "soft"})
        self.running = False
        self._reboot_hard = bool(cmd.get("hard"))

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
        tracks = self.tracker.update(targets, now)
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
                time.sleep_ms(1)  # AGENTS.md: interruptible loops
        except KeyboardInterrupt:
            pass  # no print: races mpremote's raw-REPL handshake
        finally:
            if self._reboot_hard:
                import machine
                machine.reset()
