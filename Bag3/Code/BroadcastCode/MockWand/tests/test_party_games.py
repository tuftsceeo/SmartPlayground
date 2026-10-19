"""
CPython runs of the party games (partytest.py, splattag.py, relaycolor.py)
over the simulated bus in test_party.py: 2-3 wands lobby, start, then each
game's Game.step() runs on every wand every SIM_STEP_MS of fake time.
Includes a leader drop (followers see leader_lost) and a leader ending the
game (followers see end).

Run: python3 Bag3/Code/BroadcastCode/MockWand/tests/test_party_games.py
     (or pytest on this file)
"""
import fakes
from fakes import now, FakeLeds, FakeBuz

fakes.install_game_stubs()

from test_party import Sim, SIM_STEP_MS

import partytest
import splattag
import relaycolor


class Player:
    def __init__(self, wand, mod):
        self.wand = wand
        self.net = wand.net
        self.leds = FakeLeds()
        self.buz = FakeBuz()
        self.game = mod.Game(self.net, self.leds, self.buz)
        self.done = False
        self.pressed = False

    def step(self):
        if self.done:
            return
        uses_press = self.game.step.__code__.co_argcount == 2
        p, self.pressed = self.pressed, False
        ok = self.game.step(p) if uses_press else self.game.step()
        if not ok:
            self.done = True
            self.net.close()


def start(mod, splats, smin):
    """Lobby with len(splats) wands, start on A's button, one Player each."""
    sim = Sim(splats=splats + (0,) * (3 - len(splats)))
    sim.wands = sim.wands[:len(splats)]
    first, rest = sim.wands[0], sim.wands[1:]
    first.tap(smin, slug=mod.__name__)
    sim.run(600)
    for w in rest:
        w.tap(smin, slug=mod.__name__)
    sim.run(600)
    sim.run(50, press=(first,))
    assert all(w.net is not None for w in sim.wands)
    return sim, [Player(w, mod) for w in sim.wands]


def run(sim, players, ms, down=()):
    """Step every player for ms of fake time; wands in down are off the bus."""
    for w in down:
        sim.bus.down.add(w.mac)
    end = now[0] + ms
    while now[0] < end:
        for p in players:
            if p.wand.mac not in sim.bus.down:
                p.step()
        now[0] += SIM_STEP_MS


def leds_rgb(link):
    return [a for op, a in link.writes if op == "leds"]


# ─── partytest ───────────────────────────────

def test_partytest_presses_light_pool_in_presser_color():
    sim, (a, b, c) = start(partytest, (1, 1, 1), 1)
    run(sim, (a, b, c), 200)
    a.pressed = True
    run(sim, (a, b, c), 200)
    b.pressed = True
    run(sim, (a, b, c), 200)
    c.pressed = True
    run(sim, (a, b, c), 200)
    ident = [w[1] for w in a.net.wands]
    assert a.wand.link(0).writes[-1][0] == "leds"
    assert leds_rgb(a.wand.link(0)) and leds_rgb(b.wand.link(0)) and leds_rgb(c.wand.link(0))
    from splat_api import COLOR_RGB as rgb
    assert leds_rgb(a.wand.link(0))[-1] == rgb[ident[0]]
    assert leds_rgb(b.wand.link(0))[-1] == rgb[ident[1]]
    assert leds_rgb(c.wand.link(0))[-1] == rgb[ident[2]]
    # a Splat press on C's Splat counts as C's press: lights pool 0 (A's) in C's color
    c.wand.link(0).press()
    run(sim, (a, b, c), 200)
    assert leds_rgb(a.wand.link(0))[-1] == rgb[ident[2]]


def test_partytest_leader_drop():
    sim, (a, b, c) = start(partytest, (1, 1, 0), 1)
    run(sim, (a, b, c), 1000)
    run(sim, (a, b, c), 4000, down=(a.wand,))
    assert b.done and c.done
    assert not a.done


def test_partytest_end():
    sim, (a, b) = start(partytest, (1, 1), 1)
    run(sim, (a, b), 500)
    a.done = True
    a.net.close()
    run(sim, (a, b), 100)
    assert b.done
    assert ("ledsOff", None) in [(op, None) for op, _ in b.wand.link(0).writes]


# ─── splattag ────────────────────────────────

def _hit_lit(players):
    a = players[0]
    i = a.game.lit
    if i is None:
        return False
    w, s = a.net._pool[i]
    players[w].wand.link(s).press()
    return True


def test_splattag_scores_and_wins():
    sim, ps = start(splattag, (1, 1, 1), 2)
    a = ps[0]
    for _ in range(splattag.WIN_SCORE * 3):
        run(sim, ps, splattag.GAP_MS + 100)
        _hit_lit(ps)
        run(sim, ps, 100)
        if a.done:
            break
    assert a.done and a.game.winner is not None
    assert max(a.game.scores) == splattag.WIN_SCORE
    run(sim, ps, 100)
    assert all(p.done for p in ps)
    for p in ps[1:]:
        assert p.game.scores == a.game.scores


def test_splattag_round_timeout_moves_target():
    sim, ps = start(splattag, (1, 1), 2)
    run(sim, ps, splattag.GAP_MS + 100)
    assert ps[0].game.lit is not None
    t0 = ps[0].game.lit_t
    run(sim, ps, splattag.ROUND_MS + splattag.GAP_MS + 200)
    assert ps[0].game.lit_t != t0
    assert ps[0].game.scores == [0, 0]


def test_splattag_wand_lost_skips_its_splats_and_leader_drop():
    sim, (a, b, c) = start(splattag, (1, 1, 1), 2)
    run(sim, (a, b, c), 500)
    run(sim, (a, b), 4000, down=(c.wand,))
    assert 2 in a.game.lost
    sim.bus.down.clear()
    run(sim, (a, b, c), 500)
    run(sim, (a, b, c), 4000, down=(a.wand,))
    assert b.done and c.done


# ─── relaycolor ──────────────────────────────

def test_relaycolor_baton_passes_and_shows_on_local_splats():
    sim, ps = start(relaycolor, (1, 1, 1), 1)
    a, b, c = ps
    run(sim, ps, 300)
    assert [p.game.holder for p in ps] == [0, 0, 0]
    a.pressed = True
    run(sim, ps, 300)
    assert [p.game.holder for p in ps] == [1, 1, 1]
    from pairing import IDENTITY
    from splat_api import COLOR_RGB
    assert leds_rgb(b.wand.link(0))[-1] == COLOR_RGB[IDENTITY[1][0]]
    b.wand.link(0).press()           # holder's own Splat passes too
    run(sim, ps, 300)
    assert [p.game.holder for p in ps] == [2, 2, 2] and c.game.k == 2
    c.pressed = True
    run(sim, ps, 300)
    assert [p.game.holder for p in ps] == [0, 0, 0] and a.game.k == 3
    b.pressed = True                 # not the holder: nothing
    run(sim, ps, 300)
    assert a.game.holder == 0


def test_relaycolor_holder_lost_leader_takes_baton():
    sim, ps = start(relaycolor, (1, 1, 1), 1)
    a, b, c = ps
    run(sim, ps, 300)
    a.pressed = True
    run(sim, ps, 300)                # B holds
    run(sim, (a, c), 4000, down=(b.wand,))
    assert a.game.holder == 0 and c.game.holder == 0 and 1 in c.game.lost
    a.pressed = True
    run(sim, (a, c), 300)
    assert a.game.holder == 2, "pass skips the lost wand"


def test_relaycolor_leader_drop():
    sim, ps = start(relaycolor, (1, 0), 1)
    run(sim, ps, 500)
    run(sim, ps, 4000, down=(ps[0].wand,))
    assert ps[1].done


if __name__ == "__main__":
    import sys
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name)
    print(f"{n} passed")
    sys.exit(0)
