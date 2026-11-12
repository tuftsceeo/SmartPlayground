p = r"D:\Users\Jennifer\Documents\GitHub\SmartPlayground\Bag3\Code\BroadcastCode\tools\devtests\test_splat_host.py"
s = open(p, newline='', encoding='utf-8').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')


def rep(x, y, n=1):
    global s
    assert s.count(x) == n, (s.count(x), x[:70])
    s = s.replace(x, y)


rep('''import pairing  # noqa: E402
''', '''import pairing  # noqa: E402
import splat_host  # noqa: E402
''')
rep('''shapes = [c for c in h.leds.calls if c[0] == "show_shape"]
check("the host shows the numeral 2, in green once it can start",
      shapes and shapes[-1][1] == tuple(_L.SHAPE_2) and shapes[-1][2] == _L.GREEN, str(shapes[-1:]))
press(sc, h, sc.sim.now + 10)
sc.run(600)''', '''check("the host's lobby screen has no numeral until a short press",
      not [c for c in h.leds.calls if c[0] == "show_shape"])
press(sc, h, sc.sim.now + 10)
sc.run(200)
shapes = [c for c in h.leds.calls if c[0] == "show_shape"]
check("a short press peeks the player count as the numeral 2",
      shapes and shapes[-1][1] == tuple(_L.SHAPE_2), str(shapes[-1:]))
check("...and does not start the game", nh.phase == "lobby")
hold_start(sc, h)''')
rep('''press(sc, h, sc.sim.now + 10)
sc.run(600)
macs''', '''hold_start(sc, h)
macs''')
rep('''press(sc, h, sc.sim.now + 10)
sc.run(800)''', '''hold_start(sc, h)
sc.run(200)''')
rep('''# ── lobby: the host leads''', '''def hold_start(sc, h):
    press(sc, h, sc.sim.now + 10, splat_host.START_HOLD_MS + 100)
    sc.run(splat_host.START_HOLD_MS + 700)


# ── host screen and slots (no radio) ──
R, G, B = (100, 0, 0), (0, 100, 0), (0, 0, 100)
px = splat_host.frame([(R, G), None, None, None], [True, False, False, False], "idle", 0)
check("corner TL shows the pair: left column A, right column B",
      px[0] == px[5] == splat_host._scale(R, splat_host.PAIR_SCALE)
      and px[1] == px[6] == splat_host._scale(G, splat_host.PAIR_SCALE))
check("the corner blocks are (0,1,5,6) (3,4,8,9) (15,16,20,21) (18,19,23,24)",
      splat_host.CORNERS == ((0, 1, 5, 6), (3, 4, 8, 9), (15, 16, 20, 21), (18, 19, 23, 24)))
check("idle: the cross is off", all(px[i] == (0, 0, 0) for i in splat_host.CROSS_FILL + (12,)))
check("only the next empty slot breathes",
      px[3] != splat_host.EMPTY_RGB and px[15] == px[18] == splat_host.EMPTY_RGB, str((px[3], px[15])))
on = splat_host.frame([(R, G)] * 4, [False] * 4, "idle", 0)
off = splat_host.frame([(R, G)] * 4, [False] * 4, "idle", splat_host.MISSING_FLASH_MS)
check("a missing Splat flashes", on[0] != (0, 0, 0) and off[0] == (0, 0, 0))
check("...but shows solid during boot",
      splat_host.frame([(R, G)] * 4, [False] * 4, "idle", splat_host.MISSING_FLASH_MS, boot=True)[0] != (0, 0, 0))
lob = splat_host.frame([None] * 4, [False] * 4, "lobby", 1000, hold=0.5, lobby_rgb=B)
check("lobby: center pixel is the lobby color; a half hold lights half the cross",
      lob[12] == B and [lob[i] for i in splat_host.CROSS_FILL].count(splat_host.HOLD_RGB) == 4)
check("forget hold: corners go out from the last",
      splat_host.frame([(R, G)] * 4, [True] * 4, "idle", 0, gone=1)[18] == (0, 0, 0))

hs = splat_host.HostScreen(born=0)
a, _, _ = hs.button(True, "lobby", 0)
a, _, _ = hs.button(False, "lobby", splat_host.SHORT_PRESS_MS - 50)
check("a short press is a peek", a == "peek" and hs.peeking(splat_host.SHORT_PRESS_MS))
check("the peek ends after PEEK_MS", not hs.peeking(splat_host.SHORT_PRESS_MS + splat_host.PEEK_MS))
hs.button(True, "lobby", 10000)
a, hold, _ = hs.button(True, "lobby", 10000 + splat_host.START_HOLD_MS - 1)
check("a hold just under START_HOLD_MS does not start", a is None and 0 < hold < 1)
a, _, _ = hs.button(True, "lobby", 10000 + splat_host.START_HOLD_MS, can_start=False)
check("a full hold with no players is refused", a == "refuse")
hs.button(False, "lobby", 20000)
hs.button(True, "playing", 30000)
a1, _, _ = hs.button(True, "playing", 30000 + splat_host.START_HOLD_MS)
a2, _, _ = hs.button(True, "playing", 30000 + splat_host.END_HOLD_MS)
check("ending needs the longer hold", a1 is None and a2 == "end"
      and splat_host.END_HOLD_MS > splat_host.START_HOLD_MS)
hs.button(False, "playing", 40000)
hs.button(True, "idle", 50000)
_, _, g2 = hs.button(True, "idle", 52000)
a, _, _ = hs.button(True, "idle", 50000 + splat_host.FORGET_HOLD_MS)
check("idle hold: a corner goes out per second, then forget", g2 == 2 and a == "forget")

used = []
for m in ("AB:42:00:00:00:00", "AB:42:00:00:06:06", "AB:42:00:00:0C:0C"):
    used.append(splatpair.pick_pair(m, used))
check("pairs differ in their halves and never repeat on a host",
      all(a != b for a, b in used) and len(set(used)) == 3, str(used))

_is_host = pairing.is_host
pairing.is_host = lambda: True
pairing.clear()
for m in ("AB:42:00:00:00:01", "AB:42:00:00:00:02", "AB:42:00:00:00:03", "AB:42:00:00:00:04"):
    pairing.add(m, splatpair.pick_pair)
sl = pairing.load_slots()
check("four Splats fill the four slots in order", [e[0][-2:] for e in sl] == ["01", "02", "03", "04"])
try:
    pairing.add("AB:42:00:00:00:05", splatpair.pick_pair)
    check("a fifth Splat is refused", False)
except ValueError:
    check("a fifth Splat is refused", True)
pairing.remove("AB:42:00:00:00:02")
check("a removed Splat leaves its slot missing", pairing.load_slots()[1] == sl[1]
      and "AB:42:00:00:00:02" not in pairing.load())
pairing.add("AB:42:00:00:00:09", splatpair.pick_pair)
s2 = pairing.load_slots()[1]
check("a new Splat fills the missing slot and takes its pair",
      s2[0] == "AB:42:00:00:00:09" and s2[1:] == sl[1][1:], str(s2))
pairing.clear()
pairing.is_host = _is_host


# ── lobby: the host leads''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', nl))
print("ok")
