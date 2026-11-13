"""
lobby_game.py -- ad hoc lobby games over ESP-NOW: lobby, roster and the `net` object
===============================================================================
Imported by main.py only when a game declares SPLATS_MIN, after the radio is up.

enter() runs a tap: find a leader's open lobby or become the leader, wait in
the lobby, and return a Net once the game starts (None if the lobby was
cancelled or left). Every wand in the game then calls the same play() with
that Net; net.is_leader selects the role. main.py calls net.close() when
play() returns.

Splat host games (the module sets SPLAT_HOST = True): a wand in the Splat host
role (lib/splat_host.py) always leads and holds the Splats; game wands only
join. A game wand never leads a host game: it looks for a host lobby for up to
HOST_FIND_TRIES finds. A host never yields its lobby. In the game,
net.is_host is True on the host and net.players lists the game wands' indexes.

Wire format: JSON dicts whose "type" starts with "pw_", through
espnow_manager (they arrive as "raw"). In-game frames carry "id", the game id.
See docs_and_design/2026-10-07-splat-pairing/SPEC.md section 8.
"""

import json
import time

import pwire
import splatpair
from pwire import SEND_TRIES, Dedupe

FIND_WAIT_MS = 500        # listen for a lobby after broadcasting pw_find
JOIN_WAIT_MS = 1000       # wait for the leader's pw_joined
LOBBY_SPIN_MS = 150      # follower's waiting spinner step
LOBBY_MS = 1000           # leader's pw_lobby broadcast interval
HEARTBEAT_MS = 1000       # pw_hb broadcast interval
WAND_LOST_MS = 3000       # silence before wand_lost / leader_lost
REFIND_MAX = 2            # re-finds after a leader yields its lobby
MSG_MAX_BYTES = 200       # largest JSON body net.send() accepts
MSGS_PER_POLL = 6         # ESP-NOW messages handled per Net.poll()
LOBBY_NFC_EVERY = 8       # lobby loops between stop-card reads
LOBBY_NFC_MS = 40         # NFC detect timeout for those reads
HOST_FIND_TRIES = 20      # finds a game wand makes for a host lobby (~10 s)

_counter = 0              # 1-byte game id counter, per boot
last_end = None           # why the last enter() returned None
pair_card = None          # a Splat or unpair card read in the lobby, for main.py


def _new_game_id(my_mac):
    global _counter
    _counter = (_counter + 1) & 0xFF
    b = [int(p, 16) for p in my_mac.split(":")]
    return (b[-2] << 16) | (b[-1] << 8) | _counter


class Net:
    def __init__(self, enow, my_mac, ctl, slug, splats_min, splats_max,
                 host_game=False, is_host=False, players_min=1):
        self.enow = enow
        self.my_mac = my_mac
        self.ctl = ctl                  # splatpair.SplatPairing or None
        self.slug = slug
        self.splats_min = splats_min
        self.splats_max = splats_max
        self.host_game = host_game      # the game declares SPLAT_HOST
        self.is_host = is_host          # this wand is the Splat host
        self.has_host = is_host         # wand 0 of this game is a Splat host
        self.players_min = players_min
        self.ident = splatpair.identity_name(my_mac)
        self.lobby_p = 0                # follower in a host lobby: players (pw_lobby p)
        self.lobby_c = None             # and the lobby color name (pw_lobby c)
        self.screen = None              # host: splat_host.HostScreen (enter)
        self.button_down = None
        self.leds = None
        self.phase = "new"              # new, lobby, game, ended, closed
        self.is_leader = False
        self.id = None
        self.leader_mac = None
        self.me = 0
        self.wands = []                 # (mac, identity name, splat count), leader first
        self._pool = []                 # (wand index, local index) per pool Splat
        self._members = []              # lobby/game: dicts, leader first
        self._events = []
        self._q = 0
        self._dedupe = Dedupe()
        self._peers = []                # MACs this Net registered as peers
        self._hb_at = 0
        self._lobby_at = 0
        self._lobby_reply_at = -10000
        self._seen_leader = 0
        self._leader_lost = False
        self._last_lobby_n = None
        self._ready_prev = None
        self._yield_to = None
        self._end_reason = None
        self._closing = False

    # ── properties of SPEC section 7 ──

    @property
    def local(self):
        return self.ctl.group if self.ctl is not None else None

    @property
    def splat_count(self):
        return len(self._pool)

    @property
    def local_count(self):
        return self.ctl.count if self.ctl is not None else 0

    @property
    def players(self):
        """Wand indexes of the game's players: every wand except a Splat host."""
        return list(range(1 if self.has_host else 0, len(self.wands)))

    def lobby_players(self):
        """Players in the lobby, the Splat host not counted."""
        return len(self._members) - (1 if self.has_host else 0)

    def splat(self, i):
        """Splat i of the host's Splats, leader only."""
        if not self.is_leader:
            raise RuntimeError("net.splat() is leader-only")
        w, k = self._pool[i]
        if w != self.me:
            raise RuntimeError("net.splat(%d): not held by this wand" % i)
        return self.local.unit(k)

    def send(self, to, data):
        """Game message to wand index `to`, or every other wand if None.
        True if every addressed wand ACKed it."""
        body = json.dumps(data)
        if len(body) > MSG_MAX_BYTES:
            raise ValueError("net.send: %d bytes, limit %d" % (len(body), MSG_MAX_BYTES))
        targets = [i for i in range(len(self.wands)) if i != self.me] if to is None else [to]
        ok = True
        for i in targets:
            self._q += 1
            ok = pwire.send_acked(self.enow, self.wands[i][0],
                                  {"type": "pw_msg", "id": self.id, "q": self._q, "d": data}) and ok
        return ok

    # ── frames out ──

    def _unicast(self, mac, obj):
        return pwire.send_acked(self.enow, mac, obj)

    def _add_peer(self, mac):
        if pwire.ensure_peer(self.enow, mac):
            self._peers.append(mac)

    def _hb_mask(self):
        g = self.local
        mask = 0
        if g is not None:
            for i, u in enumerate(g.units):
                if u.connected:
                    mask |= 1 << i
        return mask

    def _send_hb(self, now):
        self._hb_at = now
        self.enow.broadcast({"type": "pw_hb", "id": self.id, "l": self._hb_mask()})

    def _send_lobby(self, now):
        self._lobby_at = now
        d = {"type": "pw_lobby", "g": self.slug, "id": self.id,
             "n": self.lobby_splats(), "min": self.splats_min, "max": self.splats_max}
        if self.is_host:
            d["h"] = 1
            d["p"] = self.lobby_players()
            d["c"] = self.ident          # the lobby color: the host's identity
        self.enow.broadcast(d)

    # ── find, lead, join ──

    def find(self):
        """Broadcast pw_find and listen FIND_WAIT_MS. Returns (leader MAC,
        game id) from the first matching pw_lobby, else None."""
        self.enow.broadcast({"type": "pw_find", "g": self.slug})
        end = time.ticks_add(time.ticks_ms(), FIND_WAIT_MS)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            mt, data, sender = self.enow.poll()
            if (mt == "raw" and isinstance(data, dict) and data.get("type") == "pw_lobby"
                    and data.get("g") == self.slug and sender != self.my_mac
                    and (data.get("h") or not self.host_game)):
                self.has_host = bool(data.get("h"))
                return sender, data.get("id")
            time.sleep_ms(1)
        return None

    def lead(self):
        """Open a lobby with this wand as leader."""
        now = time.ticks_ms()
        self.is_leader = True
        self.id = _new_game_id(self.my_mac)
        self.leader_mac = self.my_mac
        self.me = 0
        self._members = [self._member(self.my_mac, self.local_count, now)]
        self.phase = "lobby"
        self._send_lobby(now)
        self._send_hb(now)

    def _member(self, mac, count, now):
        return {"mac": mac, "ident": splatpair.identity_name(mac), "count": count,
                "seen": now, "mask": None, "lost": False}

    def join(self, leader_mac, game_id):
        """Join a lobby. True once the leader's pw_joined arrives; False if it
        does not within JOIN_WAIT_MS."""
        self._add_peer(leader_mac)
        self.is_leader = False
        self.id = game_id
        self.leader_mac = leader_mac
        if not self._unicast(leader_mac, {"type": "pw_join", "id": game_id,
                                          "splats": self.local_count}):
            return False
        end = time.ticks_add(time.ticks_ms(), JOIN_WAIT_MS)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            mt, data, sender = self.enow.poll()
            if mt == "raw" and isinstance(data, dict):
                t = data.get("type")
                if sender == leader_mac and data.get("id") == game_id:
                    if t == "pw_joined":
                        now = time.ticks_ms()
                        self.phase = "lobby"
                        self._seen_leader = now
                        self._send_hb(now)
                        return True
                    if t == "pw_end":
                        r = data.get("r")
                        self._end_reason = r if r in ("yield", "full") else "ended"
                        return False
                elif t == "pw_join":
                    self._redirect_joiner(sender, data.get("id"))
            time.sleep_ms(1)
        return False

    def _redirect_joiner(self, sender, game_id):
        """A wand tried to join a lobby this wand no longer leads: tell it to
        look again."""
        self._add_peer(sender)
        self._unicast(sender, {"type": "pw_end", "id": game_id, "r": "yield"})

    # ── lobby ──

    def lobby_splats(self):
        return sum(m["count"] for m in self._members)

    def can_start(self):
        if not (self.is_leader and self.phase == "lobby" and self.lobby_splats() >= self.splats_min):
            return False
        return not self.is_host or self.lobby_players() >= self.players_min

    def lobby_step(self):
        """One lobby iteration. Returns None while waiting, "start" (the game
        began), "cancel", "refind", or ("yield", leader MAC, game id) when
        this leader should join a lower-MAC leader's lobby."""
        now = time.ticks_ms()
        self._service_local()
        for _ in range(MSGS_PER_POLL):
            mt, data, sender = self.enow.poll()
            if mt is None:
                break
            if (mt == "start_game" and self.has_host and isinstance(data, dict)
                    and data.get("name") == self.slug):
                # The teacher's start_game for this game: wands already in a
                # host lobby stay, and the host takes it as its start.
                if self.can_start():
                    self.start()
                    return "start"
                continue
            if mt in ("stop", "start_game"):
                self._end_reason = "external"
                return "cancel"
            if mt == "raw" and isinstance(data, dict):
                self._lobby_msg(data, sender, now)
                if self.phase == "game":
                    break           # the rest are in-game frames: leave them for poll()
        if self.phase == "game":
            if self._end_reason is not None:     # pw_end followed pw_start at once
                self._finish(self._end_reason)
            return "start"
        if self._end_reason is not None:
            return "refind" if self._end_reason == "yield" else "cancel"
        if self._yield_to is not None:
            to, self._yield_to = self._yield_to, None
            return ("yield", to[0], to[1])
        if time.ticks_diff(now, self._hb_at) >= HEARTBEAT_MS:
            self._send_hb(now)
        if self.is_leader:
            if time.ticks_diff(now, self._lobby_at) >= LOBBY_MS:
                self._send_lobby(now)
            self._prune_lobby(now)
            if (not self.is_host and self.splats_max is not None
                    and self.lobby_splats() >= self.splats_max and self.can_start()):
                self.start()
                return "start"
        elif time.ticks_diff(now, self._seen_leader) >= WAND_LOST_MS:
            self._end_reason = "leader_lost"
            return "cancel"
        return None

    def _lobby_msg(self, d, sender, now):
        t = d.get("type")
        if self.is_leader:
            if t == "pw_find":
                if d.get("g") == self.slug and time.ticks_diff(now, self._lobby_reply_at) >= 100:
                    self._lobby_reply_at = now
                    self._send_lobby(now)
            elif t == "pw_lobby":
                # A host never yields; any other leader yields to a host, or
                # else to the lower MAC.
                if (not self.is_host and d.get("g") == self.slug and d.get("id") != self.id
                        and (d.get("h") or sender < self.my_mac)):
                    self.has_host = bool(d.get("h"))
                    self._yield_to = (sender, d.get("id"))
            elif d.get("id") == self.id:
                if t == "pw_join":
                    self._on_join(sender, d.get("splats"), now)
                elif t == "pw_leave":
                    self._drop_member(sender)
                elif t == "pw_hb":
                    self._seen(sender, now)
        elif t == "pw_join":
            self._redirect_joiner(sender, d.get("id"))
        elif d.get("id") == self.id and sender == self.leader_mac:
            self._seen_leader = now
            if t == "pw_start":
                self._on_start(d, now)
            elif t == "pw_end":
                r = d.get("r")
                self._end_reason = r if r in ("yield", "full") else "ended"
            elif t == "pw_joined":
                pass            # a repeated answer to a retried pw_join
            elif t == "pw_lobby" and d.get("c"):
                self.lobby_p = d.get("p") or 0      # a host lobby: players and color
                self.lobby_c = d.get("c")

    def _seen(self, mac, now):
        for m in self._members:
            if m["mac"] == mac:
                m["seen"] = now
                return m
        return None

    def _on_join(self, sender, splats, now):
        if not isinstance(splats, int) or splats < 0:
            print("  [WARN] lobby: bad pw_join from %s: splats=%r" % (sender, splats))
            return
        have = self._seen(sender, now)
        total = self.lobby_splats() - (have["count"] if have else 0)
        if self.splats_max is not None and total + splats > self.splats_max:
            added = pwire.ensure_peer(self.enow, sender)
            self._unicast(sender, {"type": "pw_end", "id": self.id, "r": "full"})
            if added:
                self.enow.remove_peer(sender)
            return
        self._add_peer(sender)
        if have is None:
            self._members.append(self._member(sender, splats, now))
        else:
            have["count"] = splats
        first = 0
        for m in self._members:
            if m["mac"] == sender:
                break
            first += m["count"]
        self._unicast(sender, {"type": "pw_joined", "id": self.id, "first": first,
                               "wands": [[m["mac"], m["ident"], m["count"]] for m in self._members]})

    def _drop_member(self, mac):
        for m in list(self._members[1:]):
            if m["mac"] == mac:
                self._members.remove(m)
                if mac in self._peers:
                    self.enow.remove_peer(mac)
                    self._peers.remove(mac)

    def _prune_lobby(self, now):
        for m in list(self._members[1:]):
            if time.ticks_diff(now, m["seen"]) >= WAND_LOST_MS:
                print("  lobby: %s silent in the lobby; removed" % m["mac"])
                self._drop_member(m["mac"])

    def start(self):
        """Leader: close the lobby and send pw_start to every follower."""
        if not self.can_start():
            raise RuntimeError("lobby: not enough Splats to start (%d of %d)"
                               % (self.lobby_splats(), self.splats_min))
        now = time.ticks_ms()
        wands = [[m["mac"], m["ident"], m["count"]] for m in self._members]
        self._begin_game(wands, now)
        for m in self._members[1:]:
            self._unicast(m["mac"], {"type": "pw_start", "id": self.id, "wands": wands,
                                     "pool": self.splat_count, "h": 1 if self.is_host else 0})

    def _on_start(self, d, now):
        wands = d.get("wands")
        if (not isinstance(wands, list) or not wands
                or [w[0] for w in wands].count(self.my_mac) != 1):
            print("  [ERR] lobby: pw_start without this wand in its roster: %r" % (wands,))
            self._end_reason = "ended"
            return
        self.has_host = bool(d.get("h"))
        self._begin_game(wands, now)

    def _begin_game(self, wands, now):
        self.wands = [(w[0], w[1], w[2]) for w in wands]
        self.me = [w[0] for w in self.wands].index(self.my_mac)
        self._pool = []
        for wi, (_, _, n) in enumerate(self.wands):
            for k in range(n):
                self._pool.append((wi, k))
        self._members = [self._member(w[0], w[2], now) for w in self.wands]
        for w in self.wands:
            if w[0] != self.my_mac:
                self._add_peer(w[0])
        self._ready_prev = (1 << self.local_count) - 1
        self._seen_leader = now
        self._hb_at = now - HEARTBEAT_MS
        self.phase = "game"
        if self.ctl is not None:
            self.ctl.pause_search()

    # ── in-game ──

    def poll(self):
        """Service Splats, ESP-NOW and heartbeats; return one event or None.
        A game calls this every loop iteration."""
        now = time.ticks_ms()
        if self.phase == "game":
            self._service_local()
            self._track_local_ready()
            for _ in range(MSGS_PER_POLL):
                mt, data, sender = self.enow.poll()
                if mt is None:
                    break
                if mt in ("stop", "start_game"):
                    self._finish("external")
                    break
                if mt == "raw" and isinstance(data, dict):
                    self._game_msg(data, sender, now)
                if self._events:
                    break
            if self.phase == "game":
                if time.ticks_diff(now, self._hb_at) >= HEARTBEAT_MS:
                    self._send_hb(now)
                self._check_lost(now)
            if self.is_host and self.screen is not None and self.phase == "game":
                self._host_tick(now)
        if self._events:
            return self._events.pop(0)
        if self.phase in ("ended", "closed"):
            return ("end",)
        return None

    def _host_tick(self, now):
        """Host screen while playing; a long hold ends the game."""
        down = self.button_down() if self.button_down is not None else False
        act, hold, _ = self.screen.button(down, "playing", now)
        if act == "end":
            print("  Splat host: game ended by a hold")
            self._finish("ended")
            return
        self.screen.draw(self.leds, self.ctl, "playing", now, hold,
                         count=len(self.players),
                         lobby_rgb=splatpair.WAND_RGB[self.ident])

    def _finish(self, reason):
        self._end_reason = reason
        self.phase = "ended"
        self._events = [("end",)]

    def _service_local(self):
        if self.ctl is None:
            return
        for i, ev in self.ctl.poll():
            if self.phase != "game":
                continue
            if self.is_leader:
                self._events.append((ev, i))

    def _track_local_ready(self):
        if not self.is_leader or self._ready_prev is None:
            return
        mask = self._hb_mask()
        self._mask_events(self.me, self._ready_prev, mask)
        self._ready_prev = mask

    def _mask_events(self, wi, old, new):
        base = sum(w[2] for w in self.wands[:wi])
        for k in range(self.wands[wi][2]):
            was, is_ = (old >> k) & 1, (new >> k) & 1
            if was and not is_:
                self._events.append(("splat_lost", base + k))
            elif is_ and not was:
                self._events.append(("splat_back", base + k))

    def _game_msg(self, d, sender, now):
        if d.get("id") != self.id:
            return
        t = d.get("type")
        wi = self._wand_index(sender)
        if wi is None:
            return
        self._members[wi]["seen"] = now
        if not self.is_leader and wi == 0:
            self._seen_leader = now
            if self._leader_lost:
                self._leader_lost = False
        if t == "pw_hb":
            if self.is_leader:
                self._on_member_hb(wi, d.get("l"), now)
        elif t == "pw_msg":
            if self._dedupe.fresh(sender, d.get("q")):
                self._events.append(("msg", wi, d.get("d")))
        elif t == "pw_end":
            if not self.is_leader and wi == 0:
                self._finish("ended")
        elif t == "pw_leave":
            if self.is_leader and wi != 0 and not self._members[wi]["lost"]:
                self._members[wi]["lost"] = True
                self._events.append(("wand_lost", wi))

    def _wand_index(self, mac):
        for i, w in enumerate(self.wands):
            if w[0] == mac:
                return i
        return None

    def _on_member_hb(self, wi, mask, now):
        m = self._members[wi]
        if m["lost"]:
            m["lost"] = False
            self._events.append(("wand_back", wi))
        if isinstance(mask, int):
            old = m["mask"]
            if old is None:
                old = (1 << self.wands[wi][2]) - 1
            self._mask_events(wi, old, mask)
            m["mask"] = mask

    def _check_lost(self, now):
        if self.is_leader:
            for wi, m in enumerate(self._members):
                if wi != self.me and not m["lost"] and time.ticks_diff(now, m["seen"]) >= WAND_LOST_MS:
                    m["lost"] = True
                    self._events.append(("wand_lost", wi))
        elif not self._leader_lost and time.ticks_diff(now, self._seen_leader) >= WAND_LOST_MS:
            self._leader_lost = True
            self._events.append(("leader_lost",))

    # ── end ──

    def close(self):
        """Leave the lobby game: the leader tells every follower the game is over, a
        follower tells the leader it left unless the leader ended it or was
        lost; every peer this Net added is removed."""
        if self.phase == "closed":
            return
        self.phase = "closed"
        if self.ctl is not None:
            self.ctl.resume_search()
        if self.id is not None and self.enow.is_active:
            if self.is_leader:
                for m in self._members[1:]:
                    self._unicast(m["mac"], {"type": "pw_end", "id": self.id})
            elif self._end_reason not in _LEADER_ENDED:
                self._unicast(self.leader_mac, {"type": "pw_leave", "id": self.id})
        for mac in self._peers:
            self.enow.remove_peer(mac)
        self._peers = []

    def leave_lobby(self):
        """The wand's own stop card in the lobby: the leader cancels for
        everyone, a follower leaves."""
        self._end_reason = "left"
        self.close()


_LEADER_ENDED = ("ended", "yield", "full", "leader_lost", "external")


# ── lobby display ──

def _draw_lobby(leds, net, last):
    from leds import OFF, GREEN, BLUE_DIM
    rgb = splatpair.WAND_RGB[net.ident]
    if net.is_leader:
        joined, need = net.lobby_splats(), net.splats_min
        view = (joined, need)
        if view == last:
            return last
        n = leds.num
        for i in range(n):
            leds.np[i] = OFF
        for i in range(min(max(joined, need), n)):
            if joined >= need:
                leds.np[i] = GREEN
            else:
                leds.np[i] = rgb if i < joined else BLUE_DIM
        leds.np.write()
        return view
    if net.lobby_c is not None:
        # Host lobby: a dot per player, lobby color in the center.
        view = ("dots", net.lobby_p, net.lobby_c)
        if view == last:
            return last
        for i in range(leds.num):
            leds.np[i] = OFF
        dots = [i for i in range(leds.num) if i != 12][:net.lobby_p]
        for i in dots:
            leds.np[i] = GREEN
        if leds.num > 12:
            leds.np[12] = splatpair.WAND_RGB.get(net.lobby_c, BLUE_DIM)
        leds.np.write()
        return view
    # A follower waits with a blue spinner: a still icon in a red identity read as an error.
    step = time.ticks_ms() // LOBBY_SPIN_MS
    if last == ("wait", step):
        return last
    leds.animate_spin(step, BLUE_DIM, frames_per_step=1)
    return ("wait", step)


def run_lobby(net, nfc, button_down, leds, buz):
    """Block in the lobby. Returns "start", "cancel" or "refind", or the
    ("yield", ...) tuple from Net.lobby_step()."""
    global pair_card
    from nfc_reader import read_ndef_text, parse_splat_card
    shown = None
    was_down = button_down()
    n = 0
    while True:
        res = net.lobby_step()
        if res is not None:
            return res
        n += 1
        if n % LOBBY_NFC_EVERY == 0:
            text, _ = read_ndef_text(nfc, timeout=LOBBY_NFC_MS)
            if text == "stop":
                net.leave_lobby()
                return "cancel"
            # Pairing needs the idle loop (and a reset for a new Splat): leave
            # the lobby and hand the card to main.py.
            if text == "unpair" or (text and parse_splat_card(text)):
                pair_card = text
                net.leave_lobby()
                return "cancel"
        down = button_down()
        if net.is_host:
            # Host: a short press peeks the player count; a hold starts.
            now = time.ticks_ms()
            act, hold, _ = net.screen.button(down, "lobby", now, net.can_start())
            if act == "start":
                net.start()
                return "start"
            if act == "refuse":
                print("  Splat host: no players yet; not starting")
                buz.reject()
            net.screen.draw(leds, net.ctl, "lobby", now, hold, count=net.lobby_players(),
                            lobby_rgb=splatpair.WAND_RGB[net.ident])
            time.sleep_ms(1)
            continue
        if down and not was_down and net.can_start():
            net.start()
            return "start"
        was_down = down
        shown = _draw_lobby(leds, net, shown)
        time.sleep_ms(1)


def _wait_for_host(net, nfc, leds):
    """A game wand in a host game: find a host lobby, spinning, up to
    HOST_FIND_TRIES times. Returns (MAC, id), or None (no host, or stop card)."""
    from nfc_reader import read_ndef_text
    from leds import BLUE_DIM
    for k in range(HOST_FIND_TRIES):
        leds.animate_spin(k, BLUE_DIM, frames_per_step=1)
        found = net.find()
        if found is not None:
            return found
        text, _ = read_ndef_text(nfc, timeout=LOBBY_NFC_MS)
        if text == "stop":
            net._end_reason = "left"
            return None
    print("  lobby: no Splat host lobby for %r" % net.slug)
    net._end_reason = "no_host"
    return None


def enter(enow, slug, splats_min, splats_max, ctl, my_mac, nfc, leds, buz, button_down,
          host_game=False, is_host=False, players_min=1):
    """A tap on a lobby game's card. Returns a Net in its game phase, or None
    when the lobby was cancelled, left or lost; last_end then says why:
    "left" (this wand's stop card), "external" (ESP-NOW stop or start_game),
    "ended" (the leader cancelled), "leader_lost", "full" (the lobby could not
    take this wand's Splats) or "no_answer" (every join attempt went
    unanswered). In a host game: "no_host" (no host lobby found). A join that fails, or a leader that yields its lobby, makes
    the wand look again, up to REFIND_MAX more times."""
    global last_end, pair_card
    pair_card = None
    last_end = None
    net = Net(enow, my_mac, ctl, slug, splats_min, splats_max, host_game, is_host, players_min)
    net.leds = leds
    net.button_down = button_down
    if is_host:
        import splat_host
        net.screen = splat_host.HostScreen(born=time.ticks_add(time.ticks_ms(), -60000))
    for attempt in range(1 + REFIND_MAX):
        net._end_reason = None
        net.phase = "new"
        if is_host:
            found = None
        elif host_game:
            found = _wait_for_host(net, nfc, leds)
            if found is None:
                last_end = net._end_reason
                net.close()
                return None
        else:
            found = net.find()
        if found is None:
            net.lead()
        elif not net.join(found[0], found[1]):
            if net._end_reason == "full":
                last_end = "full"
                net.close()
                return None
            print("  [WARN] lobby: no answer from the leader of %r" % slug)
            last_end = "no_answer"
            continue
        res = run_lobby(net, nfc, button_down, leds, buz)
        while isinstance(res, tuple):          # a lower-MAC leader exists: join it
            _, mac, gid = res
            for m in net._members[1:]:
                net._unicast(m["mac"], {"type": "pw_end", "id": net.id, "r": "yield"})
            net._members = []
            if not net.join(mac, gid):
                break
            res = run_lobby(net, nfc, button_down, leds, buz)
        if isinstance(res, tuple):
            last_end = "no_answer"
            continue
        if res == "start":
            last_end = None
            return net
        if res == "refind":
            continue
        last_end = net._end_reason or "ended"
        break
    if last_end is None:
        last_end = net._end_reason or "ended"
    net.close()
    return None
