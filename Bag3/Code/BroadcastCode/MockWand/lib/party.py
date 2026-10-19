"""
party.py -- party games: lobby, roster and the `net` object
===========================================================
SPEC: docs_and_design/2026-10-07-splat-pairing/SPEC.md sections 6-8.

Imported lazily (by solo.prepare(), from main.py) only when a tapped game
declares SPLATS_MIN, after enow.init() (AGENTS.md memory-order rule).

Non-blocking parts, driven by tests and by the blocking wrapper:

    Link(enow, own_mac)        unicast with SEND_TRIES and per-sender "q"
                               dedupe; keeps non-pw_ messages for the game
    Lobby(link, slug, smin, smax, local)
        .step(press=False, stop=False)
                               -> None while the lobby runs,
                                  ("start", Net) or ("cancel", reason)
    Net                        SPEC section 7 members; .poll(), .close(),
                               .run(fn, *args) (try/finally close)

Blocking wrapper for main.py:

    lobby(enow, leds, buz, nfc, slug, smin, smax) -> Net, or None if cancelled

A Net's game must read ESP-NOW through net.wrap(enow) (main.py passes that
as play()'s enow): pw_ messages go to the net, everything else ("stop",
"start_game", game messages) reaches the game unchanged.

UNVERIFIED on hardware: FIND_WAIT_MS, LOBBY_PERIOD_MS, HB_PERIOD_MS,
WAND_LOST_MS and SEND_TRIES under BLE load; the lobby display.
"""

import time

import pairing

FIND_WAIT_MS = 500
LOBBY_PERIOD_MS = 1000
HB_PERIOD_MS = 1000
WAND_LOST_MS = 3000
SEND_TRIES = 3
JOIN_WAIT_MS = 500           # pw_joined wait before pw_join is resent
LOOP_MS = 10                 # blocking lobby loop period
NFC_EVERY = 10               # lobby loop iterations between stop-card reads
BUTTON_PIN = 0

OPS = ("color", "sound", "note", "play", "off")

_counter = 0


def _game_id(own_mac):
    global _counter
    _counter = (_counter + 1) & 0xFF
    return "%s%02X" % (own_mac[-5:].replace(":", ""), _counter)


def _expired(t, ms):
    return time.ticks_diff(time.ticks_ms(), t) >= ms


class Link:
    """ESP-NOW access shared by the lobby and the net of one game."""

    def __init__(self, enow, own_mac):
        self.enow = enow
        self.mac = own_mac
        self.q = 0
        self.seen = {}           # sender MAC -> last q accepted
        self.other = []          # non-pw_ messages, for the game
        self.peers = []

    def add_peer(self, mac):
        if mac not in self.peers:
            self.peers.append(mac)
            self.enow.add_peer(mac)

    def drop_peers(self):
        for mac in self.peers:
            self.enow.remove_peer(mac)
        self.peers = []

    def broadcast(self, data):
        return self.enow.broadcast(data)

    def send(self, mac, data):
        """Unicast with a fresh q, up to SEND_TRIES attempts. True if ACKed."""
        self.q += 1
        data["q"] = self.q
        for _ in range(SEND_TRIES):
            if self.enow.send_to(mac, data):
                return True
        print(f"  party: {data.get('type')} to {mac} not ACKed after {SEND_TRIES} tries")
        return False

    def recv(self):
        """One pw_ message as (data, mac), or None. Other messages are
        kept for the game; a repeated q from a sender is dropped."""
        while True:
            mt, data, mac = self.enow.poll(0)
            if mt is None:
                return None
            if not (mt == "raw" and isinstance(data, dict)
                    and str(data.get("type", "")).startswith("pw_")):
                self.other.append((mt, data, mac))
                continue
            q = data.get("q")
            if q is not None and mac is not None:
                last = self.seen.get(mac)
                if last is not None and q <= last:
                    continue
                self.seen[mac] = q
            return data, mac


class _GameEnow:
    """play()'s enow for a party game: pw_ messages are handled by the net."""

    def __init__(self, net, enow):
        self._net = net
        self._enow = enow

    def poll(self, timeout_ms=0):
        net = self._net
        if not net.link.other:
            net._pump()
        if net.link.other:
            return net.link.other.pop(0)
        return None, None, None

    def __getattr__(self, attr):
        return getattr(self._enow, attr)


# ─── Lobby ──────────────────────────────────

class Lobby:
    def __init__(self, link, slug, smin, smax=None, local=None):
        self.link = link
        self.slug = slug
        self.smin = smin
        self.smax = smax
        self.local = local
        self.mine = local.count if local is not None else 0
        self.state = "find"
        self.id = None
        self.leader = None       # leader MAC (follower)
        self.roster = []         # [(mac, splat_count)], leader first (leader)
        self._t = time.ticks_ms()
        self._tries = 0
        self.link.broadcast({"type": "pw_find", "g": slug})

    def total(self):
        return sum(c for _, c in self.roster)

    def _lobby_msg(self):
        return {"type": "pw_lobby", "g": self.slug, "id": self.id,
                "n": self.total(), "min": self.smin, "max": self.smax}

    def _lead(self):
        self.state = "lead"
        self.id = _game_id(self.link.mac)
        self.roster = [(self.link.mac, self.mine)]
        self.link.broadcast(self._lobby_msg())
        self._t = time.ticks_ms()
        print(f"  party: leading {self.slug} as {self.id}")

    def _join(self, mac, gid):
        self.state = "join"
        self.leader = mac
        self.id = gid
        self.roster = []
        self.link.add_peer(mac)
        self._tries = 1
        self._t = time.ticks_ms()
        self.link.send(mac, {"type": "pw_join", "id": gid, "splats": self.mine})

    def _refind(self):
        self.link.drop_peers()
        self.state = "find"
        self.id = None
        self.leader = None
        self._t = time.ticks_ms()
        self.link.broadcast({"type": "pw_find", "g": self.slug})

    def _first(self, mac):
        n = 0
        for m, c in self.roster:
            if m == mac:
                return n
            n += c
        return None

    def step(self, press=False, stop=False):
        if stop:
            return self._stop()
        while True:
            got = self.link.recv()
            if got is None:
                break
            r = self._handle(got[0], got[1])
            if r is not None:
                return r
        return self._tick(press)

    def _stop(self):
        if self.state == "lead":
            for mac, _ in self.roster[1:]:
                self.link.send(mac, {"type": "pw_end", "id": self.id})
        elif self.state in ("join", "member"):
            self.link.send(self.leader, {"type": "pw_leave", "id": self.id})
        self.link.drop_peers()
        return ("cancel", "stop")

    def _handle(self, d, mac):
        t = d.get("type")
        st = self.state
        if st == "find":
            if t == "pw_lobby" and d.get("g") == self.slug:
                self._join(mac, d.get("id"))
            return None
        if st == "lead":
            if t == "pw_find" and d.get("g") == self.slug:
                self.link.add_peer(mac)
                self.link.send(mac, self._lobby_msg())
            elif t == "pw_lobby" and d.get("g") == self.slug and d.get("id") != self.id:
                if mac < self.link.mac:
                    print(f"  party: {mac} also leads {self.slug}; merging into it")
                    for m, _ in self.roster[1:]:
                        self.link.send(m, {"type": "pw_end", "id": self.id, "r": "merge"})
                    self.link.drop_peers()
                    self._join(mac, d.get("id"))
            elif t == "pw_join" and d.get("id") == self.id:
                if self._first(mac) is None:
                    self.link.add_peer(mac)
                    self.roster.append((mac, int(d.get("splats") or 0)))
                self.link.send(mac, {"type": "pw_joined", "id": self.id,
                                     "first": self._first(mac), "wands": len(self.roster)})
            elif t == "pw_leave" and d.get("id") == self.id:
                self.roster = [w for w in self.roster if w[0] != mac]
            return None
        # join / member
        if mac != self.leader or d.get("id") != self.id:
            return None
        if t == "pw_lobby":
            self._t = time.ticks_ms()
        elif t == "pw_joined" and st == "join":
            self.state = "member"
            self._t = time.ticks_ms()
            print(f"  party: joined {self.id} (first Splat {d.get('first')})")
        elif t == "pw_start":
            wands = [(w[0], int(w[1])) for w in d.get("wands", [])]
            pool = [(p[0], p[1]) for p in d.get("pool", [])]
            return ("start", Net(self.link, self.id, False, wands, pool, self.local))
        elif t == "pw_end":
            if d.get("r") == "merge":
                self._refind()
                return None
            self.link.drop_peers()
            return ("cancel", "end")
        return None

    def _tick(self, press):
        st = self.state
        if st == "find":
            if _expired(self._t, FIND_WAIT_MS):
                self._lead()
            return None
        if st == "lead":
            n = self.total()
            if (self.smax is not None and n >= self.smax) or (press and n >= self.smin):
                return ("start", self._start())
            if _expired(self._t, LOBBY_PERIOD_MS):
                self._t = time.ticks_ms()
                self.link.broadcast(self._lobby_msg())
            return None
        if st == "join":
            if _expired(self._t, JOIN_WAIT_MS):
                if self._tries >= SEND_TRIES:
                    print(f"  party: no pw_joined from {self.leader}; finding again")
                    self._refind()
                    return None
                self._tries += 1
                self._t = time.ticks_ms()
                self.link.send(self.leader, {"type": "pw_join", "id": self.id,
                                             "splats": self.mine})
            return None
        # member: the lobby broadcast is the leader's heartbeat
        if _expired(self._t, WAND_LOST_MS):
            print(f"  party: lobby {self.id} silent for {WAND_LOST_MS} ms")
            self.link.drop_peers()
            return ("cancel", "leader_lost")
        return None

    def _start(self):
        pool = []
        for w, (_, c) in enumerate(self.roster):
            for s in range(c):
                pool.append((w, s))
        wands = list(self.roster)
        msg_wands = [[m, c] for m, c in wands]
        msg_pool = [[w, s] for w, s in pool]
        for mac, _ in wands[1:]:
            self.link.send(mac, {"type": "pw_start", "id": self.id,
                                 "wands": msg_wands, "pool": msg_pool})
        print(f"  party: {self.id} started, {len(wands)} wand(s), {len(pool)} Splat(s)")
        return Net(self.link, self.id, True, wands, pool, self.local)


# ─── net ────────────────────────────────────

class _Remote:
    """Pool Splat held by another wand (leader side): pw_cmd per call."""

    def __init__(self, net, i):
        self._net = net
        self._i = i

    def _cmd(self, op, v=None):
        return self._net._cmd(self._i, op, v)

    def color(self, name):
        return self._cmd("color", name)

    def sound(self, name):
        return self._cmd("sound", name)

    def note(self, name):
        return self._cmd("note", name)

    def play(self, names):
        return self._cmd("play", list(names))

    def off(self):
        return self._cmd("off")


class Net:
    def __init__(self, link, gid, is_leader, roster, pool, local):
        self.link = link
        self.id = gid
        self.is_leader = is_leader
        self.local = local
        self.wands = [(m, pairing.identity(m)[0], c) for m, c in roster]
        self._macs = [m for m, _ in roster]
        self.me = self._macs.index(link.mac)
        self._pool = pool
        self.splat_count = len(pool)
        self._events = []
        self._closed = False
        self._ended = False
        now = time.ticks_ms()
        self._hb_t = time.ticks_add(now, -HB_PERIOD_MS)
        self._seen = [now] * len(roster)
        self._lost = [False] * len(roster)
        self._left = [False] * len(roster)
        self._bits = [(1 << c) - 1 for _, c in roster]

    # members

    def owner(self, i):
        return self._pool[i][0]

    def _pool_index(self, w, s):
        for i, p in enumerate(self._pool):
            if p[0] == w and p[1] == s:
                return i
        return None

    def splat(self, i):
        if not self.is_leader:
            raise RuntimeError("net.splat() is leader only; use net.local")
        w, s = self._pool[i]
        if w == self.me:
            return self.local.splat(s)
        return _Remote(self, i)

    def send(self, to, data):
        targets = range(len(self._macs)) if to is None else (to,)
        ok = True
        for w in targets:
            if w != self.me:
                ok = self.link.send(self._macs[w], {"type": "pw_msg", "id": self.id,
                                                    "d": data}) and ok
        return ok

    def wrap(self, enow):
        return _GameEnow(self, enow)

    def _cmd(self, i, op, v):
        w, s = self._pool[i]
        return self.link.send(self._macs[w], {"type": "pw_cmd", "id": self.id,
                                              "s": s, "op": op, "v": v})

    # poll

    def poll(self):
        self._pump()
        if self._events:
            return self._events.pop(0)
        return None

    def _pump(self):
        if self._closed:
            return
        if self.local is not None:
            while True:
                ev = self.local.poll()
                if ev is None:
                    break
                self._local_event(ev)
        while True:
            got = self.link.recv()
            if got is None:
                break
            self._handle(got[0], got[1])
        self._tick()

    def _local_event(self, ev):
        kind, s = ev
        if kind in ("press", "release"):
            i = self._pool_index(self.me, s)
            if self.is_leader:
                if i is not None:
                    self._events.append((kind, i))
                return
            self._events.append((kind, s))
            if i is not None and not self._ended:
                self.link.send(self._macs[0], {"type": "pw_evt", "id": self.id,
                                               "s": i, "e": 1 if kind == "press" else 0})
        elif self.is_leader:
            i = self._pool_index(self.me, s)
            if i is not None:
                self._events.append((kind, i))

    def _handle(self, d, mac):
        if d.get("id") != self.id or mac not in self._macs:
            return
        w = self._macs.index(mac)
        t = d.get("type")
        self._seen[w] = time.ticks_ms()
        if self._lost[w] and t != "pw_leave":
            self._lost[w] = False
            if self.is_leader and not self._left[w]:
                self._events.append(("wand_back", w))
        if t == "pw_hb":
            if self.is_leader:
                self._hb_bits(w, int(d.get("l", 0)))
        elif t == "pw_msg":
            self._events.append(("msg", w, d.get("d")))
        elif self.is_leader:
            if t == "pw_evt":
                self._events.append(("press" if d.get("e") else "release", d.get("s")))
            elif t == "pw_leave":
                self._left[w] = True
                self._lost[w] = True
                self._events.append(("wand_lost", w))
        elif w == 0:
            if t == "pw_cmd":
                self._run_cmd(d)
            elif t == "pw_end":
                self._ended = True
                self._events.append(("end",))

    def _hb_bits(self, w, bits):
        old = self._bits[w]
        self._bits[w] = bits
        for s in range(self.wands[w][2]):
            m = 1 << s
            if (old & m) != (bits & m):
                i = self._pool_index(w, s)
                if i is not None:
                    self._events.append(("splat_back" if bits & m else "splat_lost", i))

    def _run_cmd(self, d):
        op = d.get("op")
        s = d.get("s")
        if op not in OPS or self.local is None or not isinstance(s, int) or s >= self.local.count:
            print(f"  party: bad pw_cmd {d}")
            return
        u = self.local.splat(s)
        if op == "off":
            u.off()
        else:
            getattr(u, op)(d.get("v"))

    def _ready_bits(self):
        bits = 0
        if self.local is not None:
            for s in self.local.ready():
                bits |= 1 << s
        return bits

    def _tick(self):
        if _expired(self._hb_t, HB_PERIOD_MS):
            self._hb_t = time.ticks_ms()
            self.link.broadcast({"type": "pw_hb", "id": self.id, "l": self._ready_bits()})
        if self._ended:
            return
        for w in range(len(self._macs)):
            if w == self.me or self._lost[w]:
                continue
            if not self.is_leader and w != 0:
                continue
            if _expired(self._seen[w], WAND_LOST_MS):
                self._lost[w] = True
                self._events.append(("wand_lost", w) if self.is_leader else ("leader_lost",))

    # cleanup

    def close(self):
        """SPEC section 6: pw_end (leader) or pw_leave (follower), local
        Splats off, party peers removed. Safe to call twice."""
        if self._closed:
            return
        self._closed = True
        if self.is_leader:
            for w in range(1, len(self._macs)):
                if not self._left[w]:
                    self.link.send(self._macs[w], {"type": "pw_end", "id": self.id})
        elif not self._ended:
            self.link.send(self._macs[0], {"type": "pw_leave", "id": self.id})
        if self.local is not None:
            self.local.off()
        self.link.drop_peers()

    def run(self, fn, *args):
        """fn(*args) with close() on return, stop or error; errors re-raise."""
        try:
            return fn(*args)
        finally:
            self.close()


# ─── Blocking lobby for main.py ─────────────

def _show(leds, lob):
    np = leds.np
    if lob.state == "lead":
        n = lob.total()
        for i in range(len(np)):
            np[i] = (0, 0, 0)
        for i in range(min(lob.smin, len(np))):
            np[i] = (0, 120, 0) if i < n else (0, 12, 0)
        np.write()
    else:
        rgb = lob.local.identity[1] if lob.local is not None else (60, 60, 60)
        for i in range(len(np)):
            np[i] = rgb if i in (0, 4, 12, 20, 24) else (0, 0, 0)
        np.write()


def lobby(enow, leds, buz, nfc, slug, smin, smax=None):
    """Run the lobby until the game starts (returns a Net) or is cancelled
    (stop card, pw_end, leader gone: returns None)."""
    from machine import Pin
    from espnow_manager import get_own_mac
    from nfc_reader import read_tag_command
    from game_tags import exit_tags_excluding
    exits = exit_tags_excluding(slug)
    btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    was = btn.value() == 0
    lob = Lobby(Link(enow, get_own_mac()), slug, smin, smax, pairing.local())
    shown = None
    k = 0
    while True:
        down = btn.value() == 0
        press = down and not was
        was = down
        stop = False
        k += 1
        if k % NFC_EVERY == 0:
            text, _ = read_tag_command(nfc, timeout=50)
            stop = text in exits
        r = lob.step(press, stop)
        if r is not None:
            leds.off()
            if r[0] == "start":
                buz.beep(1047, 80)
                return r[1]
            print(f"  party: lobby cancelled ({r[1]})")
            buz.beep(400, 120)
            return None
        key = (lob.state, lob.total())
        if key != shown:
            shown = key
            _show(leds, lob)
            if lob.state == "member":
                buz.beep(784, 60)
        time.sleep_ms(LOOP_MS)
