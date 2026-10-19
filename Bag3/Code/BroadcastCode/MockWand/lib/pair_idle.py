"""
pair_idle.py -- Splat pairing in the wand's idle loop
=====================================================
SPEC: docs_and_design/2026-10-07-splat-pairing/SPEC.md sections 3 and 5.

Imported lazily by main.py after boot. main.py calls:

    PairIdle(enow, leds, buz, machine)
    .card(cmd)               -> True if cmd was a Splat card or "unpair" (consumed)
    .espnow(data, mac_str)   -> handles pw_who / pw_release_all from a "raw" message
    .tick()                  -> every idle-loop iteration: Splat links, connect
                                deadline, idle glow, serial commands
    .paint()                 -> after the idle display is drawn: identity corner pixel
    .after_game()            -> after a game returns: idle glow again

Serial command (one JSON line on stdin, idle loop only):
    {"cmd":"scan_splats"} -> {"type":"splats","macs":[{"mac":..,"rssi":..},..]}
                             or {"type":"error","code":...,"cmd":"scan_splats",...}

UNVERIFIED on hardware: CLAIM_WAIT_MS, GLOW_SCALE, stdin polling alongside
the NFC loop, the corner pixel index.
"""

import sys
import time

import pairing

CLAIM_WAIT_MS = 300
GLOW_SCALE = 0.15            # idle glow brightness relative to COLOR_RGB
CORNER_PIXEL = 0             # wand matrix pixel showing the identity color
STDIN_EVERY = 5              # tick()s between stdin polls

_ERR_SHAPE = (0, 4, 6, 8, 12, 16, 18, 20, 24)   # leds.SHAPE_X


class PairIdle:
    def __init__(self, enow, leds, buz, machine):
        self.enow = enow
        self.leds = leds
        self.buz = buz
        self.machine = machine
        self._glow_due = True
        self._flashed = []           # MACs already shown the pair-success flash
        self._n = 0
        self._stdin = None
        self._line = ""
        try:
            import select
            self._stdin = select.poll()
            self._stdin.register(sys.stdin, select.POLLIN)
        except Exception as e:
            print(f"  pair_idle: no stdin polling ({e}); serial commands off")
            self._stdin = None

    # ─── Feedback ─────────────────────────────

    def _error(self, why):
        print(f"  pairing: {why}")
        self.leds.show_shape(_ERR_SHAPE, (130, 0, 0))
        self.buz.beep(300, 200)
        time.sleep_ms(500)
        self.leds.off()

    def _success_flash(self, i):
        ls = pairing.local()
        name, rgb = ls.identity
        ls.splat(i).color(name)
        self.leds.fill(rgb)
        for f in (800, 1000, 1300):
            self.buz.beep(f, 80)
        time.sleep_ms(300)
        self.leds.off()
        self._glow_due = True

    def _glow(self):
        ls = pairing.local()
        if ls is None:
            return
        from splat_api import COLOR_RGB
        name = ls.identity[0]
        r, g, b = COLOR_RGB[name]
        dim = (int(r * GLOW_SCALE), int(g * GLOW_SCALE), int(b * GLOW_SCALE))
        for i in ls.ready():
            u = ls.splat(i)
            u._check(u.link.setLEDsON(dim), "glow")

    # ─── Hooks ───────────────────────────────

    def card(self, cmd):
        if cmd == "unpair":
            self.release_all("unpair card")
            return True
        mac = pairing.parse_splat_card(cmd)
        if mac is None:
            return False
        ls = pairing.local()
        if ls is not None and ls.index_of(mac) is not None:
            ls.release(mac)
            print(f"  pairing: released {mac}")
            self.buz.beep(600, 80)
            self.buz.beep(400, 120)
            return True
        held = ls.count if ls is not None else len(pairing.load())
        if held >= pairing.MAX_SPLATS:
            self._error(f"full ({held}/{pairing.MAX_SPLATS}); {mac} refused")
            return True
        if self._claimed(mac):
            self._error(f"{mac} is held by another wand")
            return True
        if not pairing.add(mac):
            self._error(f"store refused {mac}")
            return True
        print(f"  pairing: added {mac}; resetting to connect")
        self.buz.beep(1000, 80)
        time.sleep_ms(200)
        self.machine.reset()
        return True

    def _claimed(self, mac):
        """Broadcast pw_who and wait CLAIM_WAIT_MS for a pw_held answer.
        Other messages arriving in the window are dropped (logged)."""
        if not self.enow.is_active:
            return False
        self.enow.broadcast({"type": "pw_who", "m": mac})
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < CLAIM_WAIT_MS:
            mt, data, src = self.enow.poll(10)
            if mt is None:
                time.sleep_ms(1)
                continue
            if isinstance(data, dict) and data.get("type") == "pw_held" and data.get("m") == mac:
                return True
            print(f"  pairing: claim wait dropped {mt} from {src}")
            time.sleep_ms(1)
        return False

    def espnow(self, data, mac_str):
        if not isinstance(data, dict):
            return False
        t = data.get("type")
        if t == "pw_who":
            ls = pairing.local()
            m = data.get("m")
            if ls is not None and isinstance(m, str) and ls.index_of(m) is not None and mac_str:
                self.enow.add_peer(mac_str)
                self.enow.send_to(mac_str, {"type": "pw_held", "m": m.upper()})
                self.enow.remove_peer(mac_str)
            return True
        if t == "pw_release_all":
            self.release_all("pw_release_all")
            return True
        return False

    def release_all(self, why):
        ls = pairing.local()
        if ls is not None:
            ls.off()
            ls.release_all()
        else:
            pairing.clear()
        print(f"  pairing: all released ({why})")
        self.buz.beep(600, 80)
        self.buz.beep(400, 120)

    def tick(self):
        ls = pairing.local()
        if ls is not None:
            ev = ls.poll()
            if ev is not None and ev[0] == "splat_back":
                mac = ls.macs[ev[1]]
                if mac in self._flashed:
                    self._glow_due = True
                else:
                    self._flashed.append(mac)
                    self._success_flash(ev[1])
            for mac in ls.overdue():
                ls.release(mac)
                self._error(f"{mac} not ready within {pairing.PAIR_CONNECT_MS} ms; dropped")
            if self._glow_due and ls.ready():
                self._glow_due = False
                self._glow()
        self._n += 1
        if self._stdin is not None and self._n >= STDIN_EVERY:
            self._n = 0
            self._serial()

    def paint(self):
        ls = pairing.local()
        if ls is None or ls.count == 0:
            return
        self.leds.np[CORNER_PIXEL] = ls.identity[1]
        self.leds.np.write()

    def after_game(self):
        self._glow_due = True

    # ─── Serial commands ─────────────────────

    def _serial(self):
        while self._stdin.poll(0):
            ch = sys.stdin.read(1)
            if not ch:
                return
            if ch not in "\r\n":
                if len(self._line) < 200:
                    self._line += ch
                continue
            line, self._line = self._line.strip(), ""
            if line:
                self._command(line)

    def _command(self, line):
        import json
        try:
            req = json.loads(line)
        except ValueError:
            print(json.dumps({"type": "error", "code": "bad_json"}))
            return
        cmd = req.get("cmd") if isinstance(req, dict) else None
        if cmd != "scan_splats":
            print(json.dumps({"type": "error", "code": "unknown_cmd", "cmd": cmd}))
            return
        if pairing.local() is not None:
            # The hub owns the BLE IRQ; a second scanner would take it over.
            print(json.dumps({"type": "error", "code": "busy", "cmd": cmd,
                              "msg": "wand is paired; tap unpair and power-cycle first"}))
            return
        import splat_scan
        try:
            found = splat_scan.scan()
        except Exception as e:
            sys.print_exception(e)
            print(json.dumps({"type": "error", "code": "cmd_failed", "cmd": cmd, "err": str(e)}))
            return
        print(json.dumps({"type": "splats", "macs": found}))
