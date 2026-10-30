"""Controller for the teacher tool: radio, roster, targets, sends, NFC and the main loop.

Screens call P.act(fn, *args) from LVGL callbacks; the main loop runs the queued call, so
blocking radio and NFC work never stalls touch. Import after radio bring-up and display init.
"""

import gc
import time

import card_writer
import library
import nfc
import roster
import store
import ui_kit as k
from code_link import HOST_ID
from json_link import JsonLink

P = None
VERSION = "0.1.0"
HEARTBEAT_MS = 5000
CARD_POLL_MS = 150


def ago(ts):
    if ts is None:
        return ""
    s = time.ticks_diff(time.ticks_ms(), ts) // 1000
    return "just now" if s < 60 else f"{s // 60} min ago"


class Panel:
    def __init__(self, code):
        global P
        P = self
        self.code = code
        self.lib = library.Library()
        self.store = store.Store()
        self.roster = roster.Roster(self.store.names)
        self.fleet = None
        self.reader = nfc.Reader()
        self.link = JsonLink(self.on_command)
        self.host = None
        self.q = []
        self.dirty = True
        self.target = {"kind": "all", "name": "Everyone", "macs": None}
        self.logs = {}
        self.sent = {}          # slug -> macs the panel pushed it to
        self.playing = {}       # mac -> slug started from the panel
        self.dist = None        # {"slug","macs","state":{mac: wait|send|has|fail},"done"}
        self.last_call = None   # (ticks, answered)
        self.happening = ""
        self.feed = []
        self.picked = []        # screen 2 selection
        self.pick_mode = "chat"  # chat | group
        self.nfc_on = False
        self.job = None
        self.need_lift = False
        self._added = []
        self._next_card = 0
        self._last_hb = time.ticks_ms()
        self._last_refresh = 0
        self.code.resolve()
        self.code.arm()
        self.reader.init()

    # -- loop ----------------------------------------------------------

    def act(self, fn, *args):
        self.q.append((fn, args))

    def step(self):
        self.link.pump(idle_ms=0, drain_ms=10)
        if self.q:
            fn, args = self.q.pop(0)
            try:
                fn(*args)
            except Exception as e:
                print(f"# action failed: {type(e).__name__}: {e}")
                k.toast("Something went wrong")
        self.radio_step()
        self.nfc_step()
        now = time.ticks_ms()
        if self.dirty or time.ticks_diff(now, self._last_refresh) > 10000:
            self.dirty = False
            self._last_refresh = now
            k.refresh()
        k.tick()
        if time.ticks_diff(now, self._last_hb) > HEARTBEAT_MS:
            self._last_hb = now
            self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})

    # -- radio -----------------------------------------------------------

    @property
    def mgr(self):
        return self.code.mgr

    @property
    def radio(self):
        return self.code.mgr.is_active

    def radio_up(self):
        if self.radio:
            return True
        if self.lib.flash_games() and self.code.resolve():
            return self.code.arm()
        try:
            self.mgr.init()
        except Exception as e:
            print(f"# radio up failed: {e}")
        return self.radio

    def radio_down(self):
        if self.fleet is not None:
            self.fleet.cancel("radio_off")
        if self.code.armed:
            self.code.disarm()
        else:
            self.mgr.shutdown()
        self._added = []

    def radio_step(self):
        if not self.radio:
            return
        if self.code.armed:
            for _ in range(4):
                self.code.poll(on_event=self._share_event, on_msg=self.on_msg)
        else:
            for _ in range(4):
                mt, data, mac = self.mgr.poll()
                if mt is None:
                    break
                if isinstance(data, dict):
                    self.on_msg(data, mac)
        if self.fleet is not None:
            self.fleet.step()

    def _share_event(self, event):
        r = self.code.last_result
        if event in ("ok", "fail") and r is not None:
            if r.get("mac"):
                self.roster.touch(r["mac"])
            if self.fleet is not None:
                self.fleet.on_pull(r)
            if self.host is not None:
                self.host.pull(r)
            self.dirty = True

    def on_msg(self, data, mac):
        if data.get("type") == "status_report":
            e = self.roster.touch(mac, data)
            if self.fleet is not None and self.fleet.scanning:
                e["heard"] = True
                self.fleet.on_msg(data, mac)
                self.link.send({"type": "status_report", "mac": mac, "kind": data.get("kind"),
                                "battery": data.get("battery"), "rssi": data.get("rssi")})
            self.dirty = True
        elif mac in self.roster.d:
            self.roster.touch(mac)

    def unicast(self, mac, msg):
        """Send to one MAC and report whether it was acked."""
        if not self.radio:
            return False
        if mac not in self._added:
            self._added.append(mac)
            if len(self._added) > 14:
                self.mgr.remove_peer(self._added.pop(0))
        self.mgr.add_peer(mac)
        return self.mgr.send_to(mac, msg)

    def get_fleet(self):
        if self.fleet is None:
            from fleet import Fleet
            self.fleet = Fleet(self.emit, self.unicast)
        return self.fleet

    def emit(self, d):
        """Fleet events: update the models, then pass them on to the host."""
        ty = d.get("type")
        if ty == "status_done":
            n, ready, low, stn = self.roster.summary()
            self.last_call = (time.ticks_ms(), n)
            self.add_log({"t": "rep", "n": n, "ready": ready, "low": low, "stn": stn})
            self.note_feed(f"Roll call - {n} answered")
        elif ty == "dist_progress" and self.dist:
            if d["ok"] is None:
                self.dist["state"][d["mac"]] = "send"
            elif d["ok"]:
                self.dist["state"][d["mac"]] = "has"
                self.sent.setdefault(self.dist["slug"], set()).add(d["mac"])
            else:
                self.dist["state"][d["mac"]] = "fail"
            self.happening = f"Send code - {d['done']} of {d['total']}"
        elif ty == "dist_done":
            self.happening = f"Send code done - {d['ok']} of {d['total']}"
            if self.dist:
                self.dist["done"] = True
            self.note_feed(self.happening)
        self.link.send(d)
        self.dirty = True

    def note_feed(self, s):
        self.feed.append((time.ticks_ms(), s))
        del self.feed[:-6]

    # -- targets and chat log -------------------------------------------

    def set_target(self, kind, name, macs=None):
        self.target = {"kind": kind, "name": name, "macs": macs}
        self.dirty = True

    def key(self):
        t = self.target
        if t["kind"] == "all":
            return "all"
        if t["kind"] == "group":
            return "g:" + t["name"]
        if t["kind"] == "one":
            return "m:" + t["macs"][0]
        return "set"

    def macs(self):
        m = self.target["macs"]
        return self.roster.macs() if m is None else list(m)

    def count_text(self):
        t = self.target
        n = len(self.macs())
        return f"{n} devices" if t["kind"] != "one" else self.roster.name(t["macs"][0])

    def add_log(self, entry):
        entry["ts"] = time.ticks_ms()
        lst = self.logs.setdefault(self.key(), [])
        lst.append(entry)
        del lst[:-8]
        self.dirty = True

    def log(self):
        return self.logs.get(self.key(), [])

    def chat_rows(self):
        """Sidebar rows (at most 4): Everyone, saved groups, then devices with a nickname or a warning."""
        r = self.roster
        w = len(r.items("wands"))
        s = len(r.items("stations"))
        rows = [{"title": "Everyone", "sub": f"{w} wands - {s} stations", "glyph": "@everyone_20",
                 "kind": "all", "name": "Everyone", "macs": None, "warn": False}]
        for name, macs in self.store.groups.items():
            rows.append({"title": name, "sub": f"{len(macs)} wands", "glyph": name[:1].upper(),
                         "kind": "group", "name": name, "macs": macs, "warn": False})
        for e in r.d.values():
            low = r.low(e)
            miss = self.last_call is not None and not e["heard"]
            if e["mac"] in self.store.names or low or miss:
                sub = "Battery low" if low else ("Not heard" if miss else ("Wand" if r.is_wand(e) else "Station"))
                rows.append({"title": r.name(e["mac"]), "sub": sub, "glyph": roster.tag_of(e["mac"]),
                             "kind": "one", "name": r.name(e["mac"]), "macs": [e["mac"]], "warn": low or miss})
        return rows[:4]

    # -- actions: roll call, find, start, stop ------------------------------

    def need_radio(self):
        if not self.radio_up():
            k.toast("Radio is off")
            return False
        return True

    def roll_call(self):
        if not self.need_radio():
            return
        fl = self.get_fleet()
        if fl.busy:
            k.toast("Busy - try again in a moment")
            return
        self.roster.begin_roll_call()
        fl.scan(self.mgr)
        self.note_feed("Roll call started")
        self.dirty = True

    def find(self, mac):
        if not self.need_radio():
            return
        self.get_fleet().find(self.mgr, mac)
        k.toast(f"Finding {self.roster.name(mac)}")

    def send_targets(self, msg, bmsg):
        """Returns (acked, total); total is None for a broadcast to everyone."""
        if self.target["macs"] is None:
            self.mgr.broadcast(bmsg)
            time.sleep_ms(40)
            self.mgr.broadcast(bmsg)
            return None, None
        macs = self.macs()
        ok = 0
        for mac in macs:
            if self.unicast(mac, msg):
                ok += 1
            else:
                self.add_log({"t": "err", "text": f"{self.roster.name(mac)} didn't answer",
                              "retry": (self.retry_send, mac, msg)})
        return ok, len(macs)

    def retry_send(self, mac, msg):
        if self.unicast(mac, msg):
            self.add_log({"t": "note", "text": f"{self.roster.name(mac)} answered", "b": ""})
        else:
            k.toast(f"{self.roster.name(mac)} still not answering")

    def _sub(self, ok, total):
        if ok is None:
            return f"Sent to everyone - {ago(time.ticks_ms())}"
        return f"on {ok} of {total} - just now"

    def start_game(self, slug):
        if not self.need_radio():
            return
        g = self.lib.get(slug)
        name = g["name"] if g else slug
        ok, total = self.send_targets({"type": "start_game", "name": slug}, {"type": "start_game", "name": slug})
        for mac in self.macs():
            self.playing[mac] = slug
        self.add_log({"t": "note", "text": "New game:", "b": name})
        self.add_log({"t": "mine", "text": f"Start {name}", "color": g["color"] if g else 0xBF75C9,
                      "sub": self._sub(ok, total)})
        self.note_feed(f"Start {name}")

    def stop(self):
        if not self.need_radio():
            return
        ok, total = self.send_targets({"type": "stop"}, ["stop"])
        for mac in self.macs():
            self.playing.pop(mac, None)
        self.add_log({"t": "mine", "text": "Stop", "color": 0xC0392B, "sub": self._sub(ok, total)})
        self.note_feed("Stop")

    def stop_all(self):
        self.set_target("all", "Everyone")
        self.stop()

    # -- code distribution ---------------------------------------------------

    def send_code(self, slug):
        """Start pushing a flash game's code to the current targets and show screen 4."""
        if not self.need_radio():
            return
        g = self.lib.get(slug)
        if g is None or not g["flash"]:
            k.toast("Only games from the computer have code to send")
            return
        macs = self.macs()
        if not macs:
            k.toast("No devices yet - run a roll call")
            return
        fl = self.get_fleet()
        if fl.busy:
            k.toast("Busy - try again in a moment")
            return
        self.code.set_game(slug)
        self.dist = {"slug": slug, "name": g["name"], "macs": macs, "done": False,
                     "state": {m: "wait" for m in macs}}
        fl.distribute(self.mgr, slug, macs)
        self.happening = f"Send code - 0 of {len(macs)}"
        self.add_log({"t": "mine", "text": f"Send code: {g['name']}", "color": 0x6C4CD1,
                      "sub": f"to {len(macs)} devices"})
        k.go("scr_send")

    def pause(self):
        if self.fleet is not None:
            self.fleet.paused = not self.fleet.paused
            self.dirty = True

    def retry_code(self, mac):
        if self.dist and self.fleet is not None:
            self.dist["state"][mac] = "wait"
            self.dist["done"] = False
            self.fleet.retry(mac)
            self.dirty = True

    def leave_send(self):
        if self.fleet is not None:
            self.fleet.cancel("cancelled")
        k.back()

    def start_sent(self):
        """Start the pushed game on the devices that have it."""
        d = self.dist
        if not d:
            return
        macs = [m for m, s in d["state"].items() if s == "has"]
        if not macs:
            k.toast("No wand has it yet")
            return
        keep = self.target
        self.set_target("set", "Have it", macs)
        self.start_game(d["slug"])
        self.target = keep
        k.home()

    # -- groups, names ---------------------------------------------------------

    def save_group(self, name):
        if not name or not self.picked:
            return
        self.store.add_group(name, self.picked)
        self.set_target("group", name, list(self.picked))
        k.toast(f"Saved {name}")
        k.home()

    def rename(self, mac, name):
        self.store.rename(mac, name.strip())
        self.dirty = True

    # -- NFC ---------------------------------------------------------------------

    def nfc_enter(self):
        """Radio off, field on. False (with a message) when no reader is fitted."""
        if not self.reader.ok:
            k.toast(self.reader.error, 4000)
            return False
        if self.nfc_on:
            return True
        self.radio_down()
        try:
            self.reader.antenna_on()
        except Exception as e:
            k.toast(f"NFC error: {e}")
            self.radio_up()
            return False
        self.nfc_on = True
        self.job = None
        self.need_lift = False
        return True

    def nfc_leave(self):
        if not self.nfc_on:
            return
        self.nfc_on = False
        self.job = None
        self.reader.antenna_off()
        self.radio_up()
        self.dirty = True

    def card_job(self, mode, text, label, cb):
        """Wait for a card, then write `text` (or read it). cb(result, uid, text) result:
        written | already | failed | read | empty."""
        self.job = {"mode": mode, "text": text, "label": label, "cb": cb}
        self.need_lift = False

    def card_lift(self):
        self.need_lift = True

    def nfc_step(self):
        if not self.nfc_on or self.job is None:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_card) < 0:
            return
        self._next_card = time.ticks_add(now, CARD_POLL_MS)
        rd = self.reader
        try:
            tag = rd.detect_tag(timeout=100)
        except Exception as e:
            print(f"# nfc detect: {e}")
            return
        if self.need_lift:
            if tag is None:
                self.need_lift = False
            return
        if tag is None:
            return
        job = self.job
        self.job = None
        uid = tag["uid_hex"]
        job["cb"]("busy", uid, None)
        existing = card_writer.existing_text(rd, tag)
        if job["mode"] == "read":
            res = "read" if existing else "empty"
            text = existing
        else:
            text = job["text"]
            if existing == text.strip().lower():
                res = "already"
            elif card_writer.write_text(rd, tag, text):
                res = "written"
                label = job["label"].split("@", 1)[0]
                try:
                    import stats_log
                    stats_log.record_tag(label)
                except Exception:
                    pass
            else:
                res = "failed"
        self.need_lift = True
        job["cb"](res, uid, text)

    # -- host (ChatBroadcast) ------------------------------------------------------

    def on_command(self, cmd):
        if self.host is None:
            import host
            self.host = host.Host(self)
        self.host.dispatch(cmd)


def run():
    """Main loop. Also how ChatBroadcast resumes the panel after installing a game over the REPL."""
    P.lib.scan()
    P.radio_up()
    P.dirty = True
    if P.host is not None:
        P.host.link()
    while True:
        P.step()
        time.sleep_ms(1)
