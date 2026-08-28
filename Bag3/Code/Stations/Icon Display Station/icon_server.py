"""
icon_server.py -- the command dispatcher and main loop. See the top-level
plan for the full protocol table; this module is the implementation of it.

Wire contract: every reply is exactly one JSON object per line. `id`, if
present on a command, is echoed back so the browser can correlate a
response to the request that caused it.
"""

import time
import gc
import binascii

import icon_store as store
from icon_matrix import Matrix, DEFAULT_INTENSITY, MAX_INTENSITY, W, H, N
from json_link import JsonLink

VERSION = "1.0.0"
HEARTBEAT_MS = 5000
BUSY_QUIET_MS = 2000  # suppress heartbeat if a frame arrived more recently than this
GC_EVERY_N_FRAMES = 32


class IconServer:
    def __init__(self, debug=False):
        self.m = Matrix(intensity=DEFAULT_INTENSITY)
        self.link = JsonLink(self.dispatch, debug=debug)
        self.running = True
        self.cycle_on = False
        self.cycle_names = None
        self.cycle_idx = 0
        self.cycle_hold_ms = 4000
        self.cycle_next = 0
        self.last_frame_ms = time.ticks_ms()
        self._frames = 0

        self.handlers = {
            "hello": self.do_hello,
            "info": self.do_info,
            "frame": self.do_frame,
            "px": self.do_px,
            "intensity": self.do_intensity,
            "clear": self.do_clear,
            "list": self.do_list,
            "show": self.do_show,
            "save": self.do_save,
            "delete": self.do_delete,
            "cycle": self.do_cycle,
            "orient": self.do_orient,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
        }

    # ── dispatch ────────────────────────────────────────────────────
    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        handler = self.handlers.get(name)
        if handler is None:
            self.link.send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        handler(cmd, rid)

    # ── handlers ────────────────────────────────────────────────────
    def do_hello(self, cmd, rid):
        self._send_hello(rid)

    def do_info(self, cmd, rid):
        self.link.send({
            "type": "info", "id": rid, "version": VERSION,
            "intensity": self.m.intensity, "mem": gc.mem_free(),
            "icons": len(store.list_icons()), "cycle": self.cycle_on,
            "up": time.ticks_ms(),
        })

    def do_frame(self, cmd, rid):
        t0 = time.ticks_ms()
        try:
            src = binascii.a2b_base64(cmd.get("d", ""))
        except Exception:
            self.link.send({"type": "error", "id": rid, "code": "bad_frame", "msg": "base64 decode failed"})
            return
        # A frame may declare its own size, so a smaller panel's icon (a 5x5
        # wand glyph on this 16x16) can be sent as-is and scaled here rather
        # than making every client know this panel's geometry.
        fw = int(cmd.get("w", W))
        fh = int(cmd.get("h", H))
        if len(src) != fw * fh * 3:
            self.link.send({"type": "error", "id": rid, "code": "bad_frame",
                             "msg": "%d bytes, expected %d for %dx%d" % (len(src), fw * fh * 3, fw, fh)})
            return
        if fw != W or fh != H:
            try:
                src = store.scale_into(src, fw, fh, bytearray(N * 3), W, H)
            except ValueError as e:
                self.link.send({"type": "error", "id": rid, "code": "bad_frame", "msg": str(e)})
                return
        self.cycle_on = False
        self.m.draw_bytes(src)
        self.last_frame_ms = time.ticks_ms()
        self._frames += 1
        if self._frames % GC_EVERY_N_FRAMES == 0:
            gc.collect()  # ~3KB transient churn per frame; keeps the heap flat
        if cmd.get("ack", True):
            self.link.send({"type": "frame_ok", "id": rid, "ms": time.ticks_diff(time.ticks_ms(), t0)})

    def do_px(self, cmd, rid):
        pts = cmd.get("p") or []
        try:
            triples = [(int(p[0]), int(p[1]), int(p[2]), int(p[3])) for p in pts]
        except Exception:
            self.link.send({"type": "error", "id": rid, "code": "bad_frame", "msg": "malformed p[]"})
            return
        self.cycle_on = False
        self.m.set_pixels(triples)
        self.last_frame_ms = time.ticks_ms()
        self.link.send({"type": "px_ok", "id": rid, "n": len(triples)})

    def do_intensity(self, cmd, rid):
        want = cmd.get("value", DEFAULT_INTENSITY)
        got = self.m.set_intensity(want)
        self.m.redraw()
        self.link.send({"type": "intensity", "id": rid, "value": got, "clamped": got != want})

    def do_orient(self, cmd, rid):
        """Panel orientation -- see icon_matrix.py's MIRROR_X note. Omitting a
        field leaves it unchanged, so {"cmd":"orient"} is a read."""
        mx, fy, sp = self.m.set_orientation(
            cmd.get("mirror_x"), cmd.get("flip_y"), cmd.get("serpentine")
        )
        self.m.redraw()
        self.link.send({"type": "orient", "id": rid, "mirror_x": mx, "flip_y": fy, "serpentine": sp})

    def do_clear(self, cmd, rid):
        self.cycle_on = False
        self.m.clear()
        self.link.send({"type": "ok", "id": rid, "cmd": "clear"})

    def do_list(self, cmd, rid):
        self.link.send({"type": "icons", "id": rid, "list": store.list_icons()})

    def do_show(self, cmd, rid):
        name = cmd.get("name")
        try:
            store.read_icon(name, into=self.m.src)
        except (OSError, ValueError) as e:
            self.link.send({"type": "error", "id": rid, "code": "not_found", "name": name, "msg": str(e)})
            return
        self.cycle_on = False
        self.m.draw_bytes(self.m.src)
        self.last_frame_ms = time.ticks_ms()
        self.link.send({"type": "shown", "id": rid, "name": name})

    def do_save(self, cmd, rid):
        name = cmd.get("name")
        try:
            n = store.safe_name(name)
        except ValueError:
            self.link.send({"type": "error", "id": rid, "code": "bad_name", "name": name})
            return
        if store.exists(n) and not cmd.get("overwrite"):
            self.link.send({"type": "error", "id": rid, "code": "exists", "name": n})
            return
        d = cmd.get("d")
        if d:
            try:
                src = binascii.a2b_base64(d)
            except Exception:
                self.link.send({"type": "error", "id": rid, "code": "bad_frame"})
                return
            fw = int(cmd.get("w", W))
            fh = int(cmd.get("h", H))
            if len(src) != fw * fh * 3:
                self.link.send({"type": "error", "id": rid, "code": "bad_frame",
                                 "msg": "%d bytes, expected %d for %dx%d" % (len(src), fw * fh * 3, fw, fh)})
                return
            if fw != W or fh != H:
                src = store.scale_into(src, fw, fh, bytearray(N * 3), W, H)
            self.m.draw_bytes(src)
        else:
            src = self.m.src
        try:
            size = store.write_icon(n, src)
        except OSError as e:
            self.link.send({"type": "error", "id": rid, "code": "io", "msg": str(e)})
            return
        self.link.send({"type": "saved", "id": rid, "name": n, "bytes": size})

    def do_delete(self, cmd, rid):
        name = cmd.get("name")
        try:
            n = store.delete_icon(name)
        except ValueError:
            self.link.send({"type": "error", "id": rid, "code": "bad_name", "name": name})
            return
        except OSError:
            self.link.send({"type": "error", "id": rid, "code": "not_found", "name": name})
            return
        self.link.send({"type": "deleted", "id": rid, "name": n})

    def do_cycle(self, cmd, rid):
        on = bool(cmd.get("on"))
        self.cycle_hold_ms = int(cmd.get("hold_ms", 4000))
        names = cmd.get("names")
        self.cycle_names = list(names) if names else None
        self.cycle_on = on
        self.cycle_idx = 0
        self.cycle_next = time.ticks_ms()
        icons = self.cycle_names if self.cycle_names else [e["name"] for e in store.list_icons()]
        self.link.send({"type": "cycle", "id": rid, "on": on, "count": len(icons), "hold_ms": self.cycle_hold_ms})

    def do_repl(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid})
        self.running = False

    def do_reboot(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid, "reboot": "hard" if cmd.get("hard") else "soft"})
        self.running = False
        self._reboot_hard = bool(cmd.get("hard"))

    # ── cycle mode (replaces the old main.py's cycle_icons loop) ───────
    def _cycle_step(self, now):
        icons = self.cycle_names if self.cycle_names else [e["name"] for e in store.list_icons()]
        if not icons:
            self.cycle_on = False
            return
        name = icons[self.cycle_idx % len(icons)]
        try:
            store.read_icon(name, into=self.m.src)
            self.m.draw_bytes(self.m.src)
            self.last_frame_ms = now
        except (OSError, ValueError):
            pass  # skip a bad/missing file, keep cycling
        self.cycle_idx += 1
        self.cycle_next = time.ticks_add(now, self.cycle_hold_ms)

    # ── boot / loop ─────────────────────────────────────────────────
    def _send_hello(self, rid=None):
        self.link.send({
            "type": "hello", "id": rid, "version": VERSION, "w": 16, "h": 16,
            "intensity": self.m.intensity, "max_intensity": MAX_INTENSITY,
            "model": "trunc", "fast": self.m.fast,
            "mirror_x": self.m.mirror_x, "flip_y": self.m.flip_y,
            "serpentine": self.m.serpentine,
        })

    def run(self):
        self._send_hello()
        last_hb = time.ticks_ms()
        self._reboot_hard = False
        try:
            while self.running:
                self.link.pump(idle_ms=20, drain_ms=40)
                now = time.ticks_ms()
                if self.cycle_on and time.ticks_diff(now, self.cycle_next) >= 0:
                    self._cycle_step(now)
                if (time.ticks_diff(now, last_hb) > HEARTBEAT_MS
                        and time.ticks_diff(now, self.last_frame_ms) > BUSY_QUIET_MS):
                    self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                    last_hb = now
        except KeyboardInterrupt:
            self.link.send({"type": "bye"})  # do_repl/do_reboot already sent their own
        finally:
            self.m.clear()
            if self._reboot_hard:
                import machine
                machine.reset()
