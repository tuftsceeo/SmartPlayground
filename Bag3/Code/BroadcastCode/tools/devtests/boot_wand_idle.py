"""Pair and unpair in main.py's idle loop (A5), booted under the stubs.

The real main.py idle loop runs with a scripted NFC reader. Other wands on the
same fake ESP-NOW bus answer (or don't answer) pw_who. Asserts: machine.reset()
is called only after a successful add; a full wand refuses without a claim
check; a held card and the unpair card release without a reset; pw_who is
answered for held MACs only; pw_release_all releases in idle and in a game;
identity glow, corner pixel and success flash after a connect.

Run: python3 tools/devtests/boot_wand_idle.py
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wandboot  # noqa: E402
import wandsim  # noqa: E402
from wandboot import A, B, boot, machine, pairing_file  # noqa: E402

check = wandsim.Checker()

C = "AB:42:00:00:6D:27"
CARD_A = "splat-ab4200007eb6"
CARD_B = "splat-ab4200002060"
CARD_C = "splat-ab4200006d27"
HOLDER_MAC = "AA:00:00:00:00:21"
OTHER_MAC = "AA:00:00:00:00:31"
NONE = [None]


def start_holder(b, held=(A,), cadence_ms=120, mac=HOLDER_MAC):
    """Another wand holding `held`, servicing ESP-NOW like the idle loop."""
    w = wandsim.Wand(b.sim, b.bus, mac)
    for h in held:
        w.splat(h)
    b.holder = w

    def run():
        import splatpair
        w.ctl = splatpair.SplatPairing(list(held), w.enow, w.leds, w.buz, my_mac=mac)
        while True:
            w.ctl.poll()
            mt, data, sender = w.enow.poll()
            if mt == "raw" and isinstance(data, dict):
                w.ctl.on_msg(data, sender)
            time.sleep_ms(cadence_ms)

    b.sim.spawn("holder", run, w)
    return w


def other_wand(b, mac=OTHER_MAC):
    w = wandsim.Wand(b.sim, b.bus, mac)
    b.other = w
    return w


def types(b, typ):
    return b.bus.sent(typ=typ)


# ── Tap a Splat card nobody holds: claim check, add, reset ──
b = boot(cards=NONE * 2 + [CARD_A] + NONE * 3)
check("unpaired tap, no answer: machine.reset() called", b.reset)
check("...the MAC is in /pairing.json", pairing_file() == [A], str(pairing_file()))
who = types(b, "pw_who")
check("...one pw_who for that MAC was broadcast",
      len(who) == 1 and who[0][3]["m"] == A and who[0][2] == "*", str(who))
check("...an unpaired boot never imported ubluetooth", "ubluetooth" not in sys.modules)

# ── Another wand holds it: refuse, no reset ──
b = boot(cards=NONE * 2 + [CARD_A] + NONE * 8, setup=lambda b: start_holder(b))
check("held elsewhere: no reset", not b.reset)
check("...nothing written", pairing_file() is None, str(pairing_file()))
check("...the holder answered pw_held by unicast, ACKed",
      [x[4] for x in types(b, "pw_held")] == ["acked"], str(types(b, "pw_held")))
check("...error feedback", "play:reject" in b.wand.buz.names())
check("...the answered claim left no peer behind", b.holder.enow.get_peer_macs() == [])

# ── The claimer waits CLAIM_WAIT_MS, so a slow holder is not heard ──
b = boot(cards=NONE * 2 + [CARD_A] + NONE * 3, setup=lambda b: start_holder(b, cadence_ms=900))
check("holder slower than CLAIM_WAIT_MS: not heard, the wand pairs", b.reset)

# ── Full wand refuses, with no claim check ──
b = boot(macs=[A, B], in_range=[A, B], cards=NONE * 40 + [CARD_C] + NONE * 5)
check("a wand holding 2 refuses a third", not b.reset and pairing_file() == [A, B], str(pairing_file()))
check("...without broadcasting pw_who", types(b, "pw_who") == [])
check("...with error feedback", b.wand.buz.names().count("play:reject") >= 1)

# ── Tap a held card: unpair that Splat, no reset ──
b = boot(macs=[A, B], in_range=[A, B], cards=NONE * 40 + [CARD_A] + NONE * 8)
ctl = b.m._pair_ctl
check("held card: no reset", not b.reset)
check("...removed from the file, the other stays", pairing_file() == [B], str(pairing_file()))
check("...the group's unit 0 is now the other Splat",
      ctl.macs == [B] and ctl.group.count == 1 and ctl.hub.links[0].mac_address == B)
check("...that Splat's link is disconnected", b.wand.periph(A).conn is None)
check("...its glow was cleared first", "allLEDsOff" in [n for n, d in b.wand.periph(A).cmds()])
check("...the other Splat is still connected", b.wand.periph(B).conn is not None)

b = boot(macs=[A], in_range=[A], cards=NONE * 40 + [CARD_A] + NONE * 8)
check("tapping the only held card leaves no pairing",
      not b.reset and pairing_file() is None and b.m._pair_ctl.group is None
      and b.m._pair_ctl.count == 0)
check("...BLE stays active (no deactivate)", "BLE.deactivate" not in b.order)

# ── unpair card ──
b = boot(macs=[A, B], in_range=[A, B], cards=NONE * 40 + ["unpair"] + NONE * 8)
check("unpair card: no reset, file deleted, every link disconnected",
      not b.reset and pairing_file() is None and b.m._pair_ctl.count == 0
      and b.wand.periph(A).conn is None and b.wand.periph(B).conn is None)
b = boot(cards=NONE * 2 + ["unpair"] + NONE * 3)
check("unpair card on an unpaired wand is harmless", not b.reset and pairing_file() is None)

# ── pw_release_all in the idle loop ──
def release_later(b):
    w = other_wand(b)
    b.sim.at(6000, lambda: w.enow.broadcast({"type": "pw_release_all"}))


b = boot(macs=[A, B], in_range=[A, B], cards=NONE * 80, setup=release_later)
check("pw_release_all in idle: released, file deleted, no reset",
      not b.reset and pairing_file() is None and b.m._pair_ctl.count == 0
      and b.wand.periph(A).conn is None)

# ── pw_who responder ──
def ask_later(b):
    w = other_wand(b)
    b.sim.at(6000, lambda: w.enow.broadcast({"type": "pw_who", "m": A}))
    b.sim.at(7000, lambda: w.enow.broadcast({"type": "pw_who", "m": C}))


b = boot(macs=[A, B], in_range=[A, B], cards=NONE * 80, setup=ask_later)
held = types(b, "pw_held")
check("pw_who for a held MAC is answered, only that one",
      len(held) == 1 and held[0][3]["m"] == A and held[0][2] == OTHER_MAC, str(held))
check("...the asker is not left as a peer", b.wand.enow.get_peer_macs() == [])

b = boot(cards=NONE * 30, setup=ask_later)
check("an unpaired wand never answers pw_who", types(b, "pw_held") == [])

# ── Identity glow, corner pixel, success flash ──
def snap_corner(b):
    b.corner = []
    real = b.m.show_idle
    b.m.show_idle = lambda soc, frame: (real(soc, frame), b.corner.append(b.m.leds.np[4]))[1]


b = boot(macs=[A], in_range=[A], cards=NONE * 60, setup=snap_corner)
sp = sys.modules["splatpair"]
ident = sp.identity_name(wandboot.MY_MAC)
check("identity is the last MAC byte modulo the palette",
      ident == sp.PALETTE[0x07 % len(sp.PALETTE)] == "turngreen", ident)
check("the controller's identity comes from the wand's own MAC", b.m._pair_ctl.identity == ident
      and b.m._pair_ctl.my_mac == wandboot.MY_MAC, b.m._pair_ctl.my_mac)
cols = b.wand.periph(A).colors()
check("first connect: the Splat flashes the identity color, then glows dim",
      cols[0] == (0, 255, 0) and cols[-1] == (0, 38, 0), str(cols))
check("...the wand plays the rising success tone", "play:success" in b.wand.buz.names())
mult = b.m.brightness.MULTIPLIER
want = tuple(int(c * mult) for c in sp.WAND_RGB[ident])
check("the wand shows the identity color in its corner pixel while idle",
      sp.CORNER_PIXEL == 4 and b.corner and b.corner[-1] == want, "%s vs %s" % (b.corner[-1:], want))
check("the paired idle loop detects with the short NFC timeout",
      set(wandboot.FakeReader.timeouts) == {sp.PAIRED_DETECT_MS}, str(set(wandboot.FakeReader.timeouts)))
b2 = boot(cards=NONE * 3)
check("the unpaired idle loop keeps the 250 ms detect timeout",
      set(wandboot.FakeReader.timeouts) == {250})

# ── Reconnect refreshes the glow without a second flash ──
def drop_later(b):
    b.sim.at(8000, lambda: b.wand.ble.drop(A))


b = boot(macs=[A], in_range=[A], cards=NONE * 120, setup=drop_later)
cols = b.wand.periph(A).colors()
check("a dropped Splat reconnects and the glow returns",
      b.m._pair_ctl.hub.links[0].connects == 2 and cols[-1] == (0, 38, 0)
      and cols.count((0, 255, 0)) == 1, "connects=%d cols=%s" % (b.m._pair_ctl.hub.links[0].connects, cols))
check("...and the file still holds the Splat", pairing_file() == [A])

# ── In a game: pw_who answered, pw_release_all ends the game ──
b = boot(macs=[A], in_range=[A], cards=NONE * 40)
m = b.m


class FakeEnow:
    def __init__(self, script):
        self.script = list(script)
        self.is_active = True

    def poll(self, timeout_ms=0):
        return self.script.pop(0) if self.script else (None, None, None)


w = m._StartGameCapture(FakeEnow([
    ("raw", {"type": "pw_who", "m": "AB:42:00:00:00:00"}, OTHER_MAC),
    ("raw", {"type": "pw_cmd", "id": 1}, OTHER_MAC),
    ("raw", {"type": "pw_release_all"}, OTHER_MAC),
]))
check("in a game, a pw_who is consumed", w.poll() == (None, None, None))
check("...other pw_ messages pass through to the game", w.poll()[0] == "raw")
r = w.poll()
check("...pw_release_all ends the game as a stop", r[0] == "stop")
check("...and released the Splats", m._pair_ctl.count == 0 and pairing_file() is None)

# ── _launch_game restores an idle Splat after any game ──
b = boot(macs=[A], in_range=[A], cards=NONE * 40)
m = b.m
p = b.wand.periph(A)
n0 = len(p.writes)
m._run_games = lambda *a: None
m._launch_game("x", None, None, None, None, None, None, None)
names = [n for _, n, _ in p.writes[n0:]]
check("after any game: Splats are cleared and the idle glow restored",
      "allTasksOff" in names and "allLEDsOff" in names and names[-1] == "setLEDs", str(names))

shutil.rmtree(wandboot.TMP, ignore_errors=True)
check.finish("wand idle pairing OK")
