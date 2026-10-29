"""ChatBroadcast host commands over json_link (the Dial's table plus card.write, games.rescan, unlink).

Before the teacher taps Link on screen 7 only read-only commands are answered; after
Just charge only identify is.
"""

import gc
import time

import panel
import ui_kit as k
from code_link import HOST_ID

READ_ONLY = ("identify", "info", "mode", "games.list", "stats.get", "arm", "disarm")


class Host:
    def __init__(self, P):
        self.P = P
        self.linked = False
        self.ignored = False
        self.prompted = False
        self.card = None        # {"text","label","state","msg"} for screen 9
        self.h = {
            "identify": self.identify, "info": self.info, "mode": self.mode,
            "arm": self.ok, "disarm": self.ok,
            "games.list": self.games_list, "games.select": self.games_select,
            "games.delete": self.games_delete, "games.clear": self.games_clear,
            "games.rescan": self.games_rescan,
            "stats.get": self.stats_get, "stats.reset": self.stats_reset,
            "fleet.scan": self.fleet_scan, "fleet.find": self.fleet_find,
            "fleet.distribute": self.fleet_distribute, "fleet.cancel": self.fleet_cancel,
            "card.write": self.card_write, "unlink": self.unlink,
        }

    def send(self, d):
        self.P.link.send(d)

    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        fn = self.h.get(name)
        if fn is None:
            self.send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        if self.ignored and name != "identify":
            return
        if not self.linked:
            if not self.prompted:
                self.prompted = True
                k.go("scr_link_prompt")
            if name not in READ_ONLY:
                self.send({"type": "error", "id": rid, "code": "not_linked",
                           "msg": "tap Link on the panel"})
                return
        fn(cmd, rid)

    # -- screen 7 choices --------------------------------------------------

    def link(self):
        self.linked = True
        self.P.dirty = True
        k.go("scr_linked", push=False)

    def just_charge(self):
        self.ignored = True
        k.home()

    def unlink(self, cmd, rid):
        self.ok(cmd, rid)
        self.linked = False
        self.prompted = False
        if self.card is not None:
            self.card_done("write_failed", None)
        k.home()

    # -- identity and state --------------------------------------------------

    def identify(self, cmd, rid):
        self.send({"type": "identity", "id": rid, "device": "crowpanel", "version": panel.VERSION,
                   "w": k.W, "h": k.H, "nfc": self.P.reader.ok, "host_id": HOST_ID})

    def ok(self, cmd, rid, **extra):
        d = {"type": "ok", "id": rid, "cmd": cmd.get("cmd")}
        d.update(extra)
        self.send(d)

    def info(self, cmd, rid):
        P = self.P
        self.send({"type": "info", "id": rid, "version": panel.VERSION, "mem": gc.mem_free(),
                   "armed": P.radio, "linked": self.linked,
                   "payload_ready": bool(P.lib.flash_games()), "up": time.ticks_ms()})

    def mode(self, cmd, rid):
        self.send({"type": "mode", "id": rid, "mode": "WRITE" if self.P.lib.flash_games() else "IDLE",
                   "armed": self.P.radio})

    # -- games and stats ------------------------------------------------------

    def _pulls(self):
        try:
            import stats_log
            return stats_log.aggregate().get("pulls") or {}
        except Exception:
            return {}

    def games_list(self, cmd, rid):
        pulls = self._pulls()
        lst = [{"slug": g["slug"], "name": g["name"], "bytes": g["bytes"], "pulls": pulls.get(g["slug"], 0),
                "tags": g["tags"]} for g in self.P.lib.flash_games()]
        self.send({"type": "games", "id": rid, "list": lst, "active": self.P.code.active_slug})

    def _known(self, rid, slug):
        if not slug or not any(g["slug"] == slug for g in self.P.lib.flash_games()):
            self.send({"type": "error", "id": rid, "code": "unknown_slug"})
            return False
        return True

    def games_select(self, cmd, rid):
        slug = cmd.get("slug")
        if self._known(rid, slug):
            try:
                with open("/flash/active.txt", "w") as f:
                    f.write(slug)
            except OSError:
                pass
            self.P.code.set_game(slug)
            self.ok(cmd, rid, active=slug)

    def games_delete(self, cmd, rid):
        slug = cmd.get("slug")
        if self._known(rid, slug):
            self.P.lib.delete(slug)
            self.P.dirty = True
            self.ok(cmd, rid, slug=slug)

    def games_clear(self, cmd, rid):
        self.P.lib.clear()
        self.P.dirty = True
        self.ok(cmd, rid)

    def games_rescan(self, cmd, rid):
        self.P.lib.scan()
        self.P.radio_up()
        self.P.dirty = True
        self.ok(cmd, rid, n=len(self.P.lib.flash_games()))

    def stats_get(self, cmd, rid):
        try:
            import stats_log
            agg = stats_log.aggregate()
        except Exception:
            agg = {}
        self.send({"type": "stats", "id": rid, "pulls": agg.get("pulls") or {},
                   "writes": agg.get("writes") or {}, "since": agg.get("since") or 0})

    def stats_reset(self, cmd, rid):
        import stats_log
        stats_log.reset()
        self.ok(cmd, rid)

    # -- fleet ---------------------------------------------------------------

    def _fleet(self, rid):
        P = self.P
        if P.nfc_on or not P.radio_up():
            self.send({"type": "error", "id": rid, "code": "not_serving", "msg": "radio is off"})
            return None
        return P.get_fleet()

    def fleet_scan(self, cmd, rid):
        fl = self._fleet(rid)
        if fl is None:
            return
        if fl.busy:
            self.send({"type": "error", "id": rid, "code": "busy"})
            return
        self.P.roster.begin_roll_call()
        fl.scan(self.P.mgr)
        self.P.note_feed("Computer: roll call")
        self.ok(cmd, rid)

    def fleet_find(self, cmd, rid):
        mac = cmd.get("mac")
        if not mac:
            self.send({"type": "error", "id": rid, "code": "no_mac"})
            return
        fl = self._fleet(rid)
        if fl is not None:
            fl.find(self.P.mgr, mac)
            self.ok(cmd, rid, mac=mac)

    def fleet_distribute(self, cmd, rid):
        P = self.P
        slug = cmd.get("slug")
        macs = cmd.get("macs")
        if not self._known(rid, slug):
            return
        if not isinstance(macs, list) or not macs:
            self.send({"type": "error", "id": rid, "code": "no_macs"})
            return
        fl = self._fleet(rid)
        if fl is None:
            return
        if fl.busy:
            self.send({"type": "error", "id": rid, "code": "busy"})
            return
        g = P.lib.get(slug)
        P.code.set_game(slug)
        P.dist = {"slug": slug, "name": g["name"], "macs": list(macs), "done": False,
                  "state": {m: "wait" for m in macs}}
        fl.distribute(P.mgr, slug, macs)
        P.happening = f"Send code - 0 of {len(macs)}"
        P.note_feed(f"Computer: send {g['name']}")
        self.ok(cmd, rid, slug=slug, total=len(macs))

    def fleet_cancel(self, cmd, rid):
        if self.P.fleet is not None:
            self.P.fleet.cancel("cancelled")
        self.ok(cmd, rid)

    def pull(self, r):
        path = r.get("path") or ""
        self.send({"type": "pull", "id": None,
                   "slug": r.get("slug") or (path.rsplit("/", 1)[-1][:-3] if path else None),
                   "role": r.get("hub") or "wand", "wand": r.get("mac"), "ok": r.get("ok"),
                   "ms": r.get("ms"), "why": r.get("why") or None})

    # -- card.write (screen 9) ---------------------------------------------------

    def card_write(self, cmd, rid):
        text = (cmd.get("text") or "").strip()
        label = cmd.get("label") or text
        if (text == "getcode" or text.startswith("getcode:")) and "@" not in text:
            text = f"{text}@{HOST_ID}"
        if not text or len(text.encode()) > 54:
            self.send({"type": "error", "id": rid, "code": "bad_text"})
            return
        if self.card is not None:
            self.send({"type": "error", "id": rid, "code": "busy"})
            return
        self.ok(cmd, rid)
        self.card = {"text": text, "label": label, "state": "waiting", "msg": "Tap a card here"}
        k.go("scr_linked_card")

    def card_result(self, res, uid, text):
        c = self.card
        if c is None:
            return
        if res == "busy":
            c["state"] = "writing"
            c["msg"] = "Keep holding..."
        elif res in ("written", "already"):
            self.send({"type": "card_written", "label": c["label"], "uid": uid, "text": c["text"]})
            self.P.note_feed(f"Card written: {c['label']}")
            self.card_done(None, uid)
            return
        else:
            c["state"] = "error"
            c["msg"] = "Write failed - lift and tap again"
            self.P.card_job("write", c["text"], c["label"], self.card_result)
        self.P.dirty = True

    def card_done(self, event, uid):
        """Finish screen 9: report a failure if event is set, then back to 8."""
        c = self.card
        self.card = None
        if event and c is not None:
            self.send({"type": event, "uid": uid, "text": c["text"], "label": c["label"]})
        self.P.nfc_leave()
        if k.cur == "scr_linked_card":
            k.go("scr_linked", push=False)
