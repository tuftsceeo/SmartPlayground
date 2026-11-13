"""
splat_host.py -- the Splat host role: a wand that holds Splats for a game
=========================================================================
A wand in this role is not a game controller. It pairs with up to
pairing.HOST_MAX_SPLATS Splats, keeps them across reboots, and runs the Splat
side of Splat host games (game modules that set SPLAT_HOST = True): it always
leads the game's lobby, and game wands join it (lib/lobby_game.py).

Imported by main.py only after the radio is up (AGENTS.md: nothing may allocate
before the radio claims its memory).

The role is the text "splat_host" in /role.txt (pairing.ROLE_PATH). It is set
or cleared by:
  - NFC card "splathost" (any wand) or "player" (a host);
  - ESP-NOW unicast {"type": "set_role", "mac": <wand MAC>, "role":
    "splat_host" | "player"} from a teacher controller.
Each change resets the wand. A wand becoming host keeps its current Splats.

Host idle screen: one corner per Splat slot (identity color when paired, dim
blue when empty) and a white center pixel. In a host lobby the screen is the
player count as a numeral, the host not counted.

The host reads Splat cards, "unpair", "player", "stop", game cards and
getcode cards. Its button does nothing at idle; in a lobby it starts the game.
"""

import os
import time

import pairing

HOST_NFC_MS = 100          # NFC detect timeout per host-loop pass
SLOT_PIXELS = (0, 4, 20, 24)
CENTER_PIXEL = 12
ROLES = ("splat_host", "player")


def set_role(role):
    """Write the role and reset. A role the wand already has does nothing."""
    if role not in ROLES:
        print("  [WARN] splat_host: unknown role %r" % (role,))
        return
    if (role == "splat_host") == pairing.is_host():
        print("  splat_host: already %s" % role)
        return
    import machine
    if role == "splat_host":
        with open(pairing.ROLE_PATH, "w") as f:
            f.write("splat_host")
        if pairing.exists():
            # Keep this wand's Splats through the reset (main.py _read_pairing).
            with open("/pair_boot", "w") as f:
                f.write("1")
    else:
        os.remove(pairing.ROLE_PATH)
    print("  splat_host: role is now %s; resetting" % role)
    time.sleep_ms(300)
    machine.reset()


def _draw(leds, ctl, last):
    from leds import OFF, WHITE, BLUE_DIM
    from splatpair import WAND_RGB
    n = ctl.count if ctl is not None else 0
    view = ("idle", n)
    if view == last:
        return last
    for i in range(leds.num):
        leds.np[i] = OFF
    rgb = WAND_RGB[ctl.identity] if ctl is not None else BLUE_DIM
    for k in range(pairing.HOST_MAX_SPLATS):
        if k < len(SLOT_PIXELS):
            leds.np[SLOT_PIXELS[k]] = rgb if k < n else BLUE_DIM
    leds.np[CENTER_PIXEL] = WHITE
    leds.np.write()
    return view


def run(enow, nfc, leds, buz, get_ctl, pair_card, launch, pull, is_game):
    """The host's idle loop; never returns (a role change resets the wand).

    get_ctl() -> the current splatpair.SplatPairing or None
    pair_card(text) -> handle a Splat or unpair card (may reset)
    launch(name) -> run a game through main.py's game path
    pull(slug, host) -> getcode pull and launch
    is_game(name) -> True for a known game slug
    """
    from nfc_reader import read_ndef_text, parse_splat_card, split_prefixed
    print("  Splat host: up to %d Splats; tap 'player' to leave this role"
          % pairing.HOST_MAX_SPLATS)
    shown = None
    last_text = None
    while True:
        ctl = get_ctl()
        if ctl is not None:
            for i, ev in ctl.poll():
                if ev == "press":
                    ctl.on_press(i)
                    shown = None
            ctl.refresh_glow()

        mt, data, sender = enow.poll()
        if mt == "set_role" and isinstance(data, dict):
            set_role(data.get("role"))
        elif mt == "start_game" and isinstance(data, dict):
            name = data.get("name")
            if is_game(name):
                launch(name)
                shown = None
        elif mt == "code_push" and isinstance(data, dict):
            pull(data.get("slug") or "", data.get("host") or "")
            shown = None
        elif mt == "raw" and ctl is not None and isinstance(data, dict):
            ctl.on_msg(data, sender)

        text, _ = read_ndef_text(nfc, timeout=HOST_NFC_MS)
        if text != last_text:
            last_text = text
            if text == "unpair" or (text and parse_splat_card(text)):
                pair_card(text)
                shown = None
            elif text == "player":
                set_role("player")
            elif text and is_game(text):
                launch(text)
                shown = None
                last_text = None
            elif text:
                head, slug, host = split_prefixed(text)
                if head == "getcode":
                    pull(slug, host)
                    shown = None
                    last_text = None
        shown = _draw(leds, ctl, shown)
        time.sleep_ms(1)
