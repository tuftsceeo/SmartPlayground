"""Controller for the teacher tool: radio, roster, targets, sends, NFC and the main loop.

Screens call P.act(fn, *args) from LVGL callbacks; the main loop runs the queued call, so
blocking radio and NFC work never stalls touch. Import after radio bring-up and display init.
"""

import gc
import time

import beep
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
PROTO = 1           # link protocol; ChatBroadcast's identify carries its own (host.identify)
HEARTBEAT_MS = 5000
CARD_POLL_MS = 150


def ago(ts):
    if ts is None:
        return ""
    s = time.ticks_diff(time.ticks_ms(), ts) // 1000
    return "just now" if s < 60 else f"{s // 60} min ago"


def short_ago(ts):
    """Roll-call age under a group's name: "now", "1m", "12m"."""
    s = time.ticks_diff(time.ticks_ms(), ts) // 1000
    return "now" if s < 60 else f"{s // 60}m"


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
        self.wake = None        # ticks at which to refresh once (screens holding a result)
        self.target = {"kind": "all", "name": "Everyone", "macs": None}
        self.logs = {}
        self.sent = {}          # slug -> macs the panel pushed it to
        self.playing = {}       # mac -> slug started from the panel
        self.dist = None        # {"slug","macs","state":{mac: wait|send|has|fail},"done"}
        self.last_call = None   # (ticks, answered)
        self.calls = {}         # chat key -> (ticks, wands, stations) from its last roll call
        self._call = None       # (chat key, macs or None) of the roll call listening now
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
        self._nfc_errs = 0
        self.code.resolve()
        self.radio_up()
        self.reader.init()
        beep.init()

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
        if self.host is not None:
            self.host.check()
        now = time.ticks_ms()
        if self.wake is not None and time.ticks_diff(now, self.wake) >= 0:
            self.wake = None
            self.dirty = True
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
        """Radio on; it serves code whenever it is on. Only nfc_enter turns it off."""
        self.code.radio_on()
        return self.radio

    def radio_down(self):
        if self.fleet is not None:
            self.fleet.cancel("radio_off")
        self.code.radio_off()
        self._added = []

    def radio_step(self):
        if not self.radio:
            return
        for _ in range(4):
            self.code.poll(on_event=self._share_event, on_msg=self.on_msg)
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
                self._scan_push(mac, e)
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

    def _scan_push(self, mac, e):
        """Send code to Everyone: each wand that answers the scan is pushed the code (unicast)."""
        d = self.dist
        if (d is None or not d.get("scan") or d.get("stopped") or mac in d["state"]
                or not self.roster.is_wand(e)):
            return
        d["state"][mac] = "wait"
        d["macs"].append(mac)
        d["done"] = False
        self.fleet.retry(mac)

    def get_fleet(self):
        if self.fleet is None:
            from fleet import Fleet
            self.fleet = Fleet(self.emit, self.unicast)
        return self.fleet

    def emit(self, d):
        """Fleet events: update the models, then pass them on to the host."""
        ty = d.get("type")
        if ty == "status_done":
            n = self.roster.summary()[0]
            now = time.ticks_ms()
            self.last_call = (now, n)
            if self._call is not None:
                key, macs = self._call
                self._call = None
                es = [e for e in self.roster.items() if e["heard"] and (macs is None or e["mac"] in macs)]
                nw = sum(1 for e in es if self.roster.is_wand(e))
                self.calls[key] = (now, nw, len(es) - nw)
            self.note_feed(f"Roll call - {n} answered")
            if self.dist:
                self.dist["scan"] = False
        elif ty == "dist_progress" and self.dist:
            if d["ok"] is None:
                self.dist["state"][d["mac"]] = "recv"
            elif d["ok"]:
                self.dist["state"][d["mac"]] = "has"
                self.sent.setdefault(self.dist["slug"], set()).add(d["mac"])
            else:
                self.dist["state"][d["mac"]] = "fail"
                self.dist.setdefault("why", {})[d["mac"]] = d.get("why")
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

    def answered(self):
        """Subtitle for the current chat after a roll call: its own count, or one device's age."""
        r = self.roster
        m = self.target["macs"]
        if self.target["kind"] == "one":
            return f"Heard {r.age(r.d[m[0]])}" if m[0] in r.d else ""
        es = r.items() if m is None else [r.d[x] for x in m if x in r.d]
        n = sum(1 for e in es if e["heard"])
        return f"{n} answered{k.DOT}{ago(self.last_call[0])}"

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
        """Left-column rows (at most 5): Everyone, saved groups, then devices you have chatted
        with, named, or with a low battery. A low battery shows as an amber avatar, not text."""
        r = self.roster
        rows = [{"title": "Everyone", "glyph": "@everyone_20",
                 "kind": "all", "name": "Everyone", "macs": None, "warn": False}]
        for name, macs in self.store.groups.items():
            rows.append({"title": name, "glyph": name[:1].upper(),
                         "kind": "group", "name": name, "macs": macs, "warn": False})
        for e in r.ranked():
            low = r.low(e)
            if e["mac"] in self.store.names or low or ("m:" + e["mac"]) in self.logs:
                wand = r.is_wand(e)
                rows.append({"title": r.name(e["mac"]),
                             "glyph": "@wand_20" if wand else "@station_face_20",
                             "kind": "one", "name": r.name(e["mac"]), "macs": [e["mac"]], "warn": low})
        return rows[:5]

    # -- actions: roll call, find, start, stop ------------------------------

    def need_radio(self):
        if not self.radio_up():
            k.toast("Radio is off")
            return False
        return True

    def roll_call(self, macs=None):
        """Ask every device to answer; the counts are kept for the open chat (macs: its devices)."""
        if not self.need_radio():
            return
        fl = self.get_fleet()
        if fl.busy:
            k.toast("Busy - try again in a moment")
            return
        self.roster.begin_roll_call()
        self._call = (self.key(), macs)
        fl.scan(self.mgr)
        self.add_log({"t": "mine", "text": "Roll call", "color": 0x22C3A6, "icon": "roll"})
        self.note_feed("Roll call started")
        self.dirty = True

    def find(self, mac):
        if not self.need_radio():
            return
        self.get_fleet().find(self.mgr, mac)
        if self.target["kind"] == "one" and self.target["macs"][0] == mac:
            self.add_log({"t": "mine", "text": "Find it", "color": 0x22C3A6, "icon": "find"})
            self.add_log({"t": "reply", "text": "Blinking and buzzing"})
            e = self.roster.d.get(mac)
            if e is not None and e["battery"] is not None:
                low = self.roster.low(e)
                self.add_log({"t": "reply", "text": f"Battery {e['battery']}%" + (f"{k.DOT}charge soon" if low else ""),
                              "warn": low})

    def open_group(self):
        """Opening a group (1B): a roll call for its devices, then Find on each one."""
        if self.target["kind"] != "group" or not self.need_radio():
            return
        macs = list(self.target["macs"] or [])
        fl = self.get_fleet()
        if not fl.scanning:
            self.roll_call(macs)
        for mac in macs:
            fl.find(self.mgr, mac)

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
        return ok, len(macs)

    def mine_sub(self, e):
        """Second line of a sent bubble, aged at each refresh."""
        if e.get("sub"):
            return e["sub"]
        if e.get("icon") in ("roll", "find"):
            a = ago(e["ts"])
            return a[:1].upper() + a[1:]
        if e.get("total") is None:
            return f"Sent to everyone{k.DOT}{ago(e['ts'])}"
        return f"{e.get('verb', 'Sent to')} {e['ok']} of {e['total']}{k.DOT}{ago(e['ts'])}"

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
                      "ok": ok, "total": total, "verb": "Playing on"})
        self.note_feed(f"Start {name}")

    def stop(self):
        if not self.need_radio():
            return
        ok, total = self.send_targets({"type": "stop"}, ["stop"])
        for mac in self.macs():
            self.playing.pop(mac, None)
        self.add_log({"t": "mine", "text": "Stop", "color": 0xC0392B, "ok": ok, "total": total, "verb": "Stopped on"})
        self.note_feed("Stop")

    def stop_all(self):
        self.set_target("all", "Everyone")
        self.stop()

    # -- code distribution ---------------------------------------------------

    def send_code(self, slug):
        """Send a flash game's code and show screen 4, pushed one wand after another (unicast).
        Everyone: no standing roll call is needed - a scan runs now and each wand that answers is
        queued, so the list is whoever is on and in range at this moment."""
        if not self.need_radio():
            return
        g = self.lib.get(slug)
        if g is None or not g["flash"]:
            return      # 3b lists only games from the computer
        fl = self.get_fleet()
        if fl.distributing:
            k.toast("Busy - try again in a moment")
            return
        if self.target["macs"] is None:
            self.code.set_game(slug)
            self.dist = {"mode": "push", "scan": True, "all": True, "slug": slug, "name": g["name"], "macs": [],
                         "done": False, "state": {}, "ts": time.ticks_ms()}
            fl.distribute(self.mgr, slug, [])
            if fl.scanning:
                # a roll call already running: queue the wands it has heard, the rest as they answer
                for e in self.roster.items():
                    if e["heard"]:
                        self._scan_push(e["mac"], e)
            else:
                self.roster.begin_roll_call()
                self._call = (self.key(), None)
                fl.scan(self.mgr)
            self.add_log({"t": "mine", "text": f"Send code: {g['name']}", "color": 0x6C4CD1})
            k.go("scr_send")
            return
        macs = self.macs()
        if not macs:
            k.toast("No devices yet - run a roll call")
            return
        self.code.set_game(slug)
        self.dist = {"mode": "push", "slug": slug, "name": g["name"], "macs": macs, "done": False,
                     "state": {m: "wait" for m in macs}, "ts": time.ticks_ms()}
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

    def retry_failed(self):
        if self.dist:
            for mac, s in list(self.dist["state"].items()):
                if s == "fail":
                    self.retry_code(mac)

    def send_rest(self):
        """After Stop: send again to the devices that don't have the code yet."""
        d = self.dist
        if not d or not self.need_radio():
            return
        rest = [m for m, s in d["state"].items() if s != "has"]
        fl = self.get_fleet()
        if not rest or fl.busy:
            return
        for m in rest:
            d["state"][m] = "wait"
        d["stopped"] = False
        d["done"] = False
        self.code.set_game(d["slug"])
        fl.distribute(self.mgr, d["slug"], rest)
        self.dirty = True

    def leave_send(self):
        d = self.dist
        if d is not None:
            d["stopped"] = True     # wands still answering the scan are not queued
        if self.fleet is not None:
            self.fleet.cancel("cancelled")
        k.back()

    def start_sent(self):
        """Start the sent game: a broadcast after a send to Everyone, else on the devices that
        have it."""
        d = self.dist
        if not d:
            return
        macs = [m for m, s in d["state"].items() if s == "has"]
        if not macs:
            return
        if d.get("all"):
            d["stopped"] = True
            self.set_target("all", "Everyone")
            self.start_game(d["slug"])
            k.home()
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
        k.home()
        k.go("scr_group")
        self.open_group()

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
        written | already | failed | read | empty. A card still on the reader from the last
        job is lifted first (need_lift), so the next tag is never written by accident."""
        self.job = {"mode": mode, "text": text, "label": label, "cb": cb}

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
            self._nfc_errs = 0
        except Exception as e:
            print(f"# nfc detect: {e}")
            self._nfc_errs += 1
            if self._nfc_errs >= 15:
                # as the Dial does: after a run of errors, start the reader again
                self._nfc_errs = 0
                if rd.init():
                    rd.antenna_on()
            return
        if self.need_lift:
            if tag is None:
                self.need_lift = False
                self.dirty = True
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
        if res in ("written", "already", "read"):
            beep.ok()
        elif res in ("failed", "empty"):
            beep.fail()
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
