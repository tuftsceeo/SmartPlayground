import os
D = os.path.dirname(os.path.abspath(__file__))
p = r"D:\Users\Jennifer\Documents\GitHub\SmartPlayground\Bag3\Code\Wand Module\lib\splat_host.py"
s = open(p, newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')
consts, funcs = open(os.path.join(D, "host_new.py")).read().split("#SPLIT#\n")
i = s.index('Host idle screen:')
j = s.index('"""', i)
s = s[:i] + '''Host screen (HostScreen, frame): four 2x2 corner blocks, one per Splat slot
(TL, TR, BL, BR). A paired slot shows its pair, left column A and right
column B; a missing Splat flashes; an empty slot is dim and the next one to
fill breathes; a re-tapped Splat pulses its corner. The center cross is off at
idle, breathes yellow-green in a lobby and beats cyan in a game, and fills
during a hold. The center pixel shows the lobby color (the host's identity).

Button: a short press peeks the count as a numeral for PEEK_MS (Splats at idle,
players in a lobby or game). A hold starts the game in a lobby (START_HOLD_MS;
refused with no players), ends it while playing (END_HOLD_MS), and at idle
forgets every Splat (FORGET_HOLD_MS; a corner goes out each second, releasing
early keeps them).

The host reads Splat cards, "unpair", "player", "stop", game cards and
getcode cards.
''' + s[j:]
k = s.index('HOST_NFC_MS')
s = s[:k] + consts.rstrip('\n') + s[s.index('\n\n\ndef set_role'):]
a = s.index('def _draw(')
b = s.index('def run(')
s = s[:a] + funcs + s[b:]


def rep(x, y):
    global s
    assert x in s, x[:70]
    s = s.replace(x, y)


rep('def run(enow, nfc, leds, buz, get_ctl, pair_card, launch, pull, is_game):',
    'def run(enow, nfc, leds, buz, get_ctl, pair_card, launch, pull, is_game, button_down=None):')
rep('''    is_game(name) -> True for a known game slug
    """''', '''    is_game(name) -> True for a known game slug
    button_down() -> True while the button is pressed
    """''')
rep('''    shown = None
    last_text = None
    while True:''', '''    screen = HostScreen()
    last_text = None
    while True:
        now = time.ticks_ms()''')
s = s.replace('                    shown = None\n', '').replace('                shown = None\n', '').replace('            shown = None\n', '')
rep('''        shown = _draw(leds, ctl, shown)
        time.sleep_ms(1)''', '''        down = button_down() if button_down is not None else False
        act, hold, gone = screen.button(down, "idle", now)
        if act == "forget":
            print("  Splat host: forgetting every Splat")
            if ctl is not None:
                ctl.release_all()
            else:
                pairing.clear()
            buz.confirm()
            screen.reload()
        screen.draw(leds, ctl, "idle", now, hold, gone, ctl.count if ctl is not None else 0)
        time.sleep_ms(1)''')
open(p, 'w', newline='').write(s.replace('\n', nl))
print("ok", s.count("shown"))
