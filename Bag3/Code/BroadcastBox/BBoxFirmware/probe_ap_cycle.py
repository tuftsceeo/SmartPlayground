"""
probe_ap_cycle.py — Phase A T1 bench probe: does AP down/up survive repeat
cycles in one boot? Modeled on probe_stick.py's `_result("key", value, ok)`
RESULT-line convention. Standalone; not part of BOX_FILES / manifest.js --
this is a bench tool, not firmware.

See design/phase-a-box-power-modes.plan.md, task T1, for the full rationale.
Short version: a box-side pass here is NECESSARY but NOT SUFFICIENT. The
failure this exists to catch -- "AP visible at good rssi but join times
out" (MockWand/code_puller.py:165-174, the docstring on _reset_sta) -- looks
identical to success from the box side: ap.active() reads True and a socket
binds fine either way. Only a station completing the join distinguishes
them, so this is a two-board test.

Deploy and run from the REPL (ask which board is on which port first --
ports change between sessions, see the plan's Hardware etiquette section):

  mpremote connect <BOX_PORT> fs cp probe_ap_cycle.py :/flash/probe_ap_cycle.py

Step A (box) -- runs N=10 AP down/up cycles, then leaves the AP up on the
final cycle instead of tearing it down, as a hand-off to step B:

  mpremote connect <BOX_PORT> exec "import probe_ap_cycle; probe_ap_cycle.run()"

Step B (wand), with the box's AP still up from step A. This is a cold radio
(no main.py ESP-NOW this boot) -- do not pass enow=, do not modify any
MockWand file to run this:

  mpremote connect <WAND_PORT> exec "import code_puller; print('T1_JOIN', code_puller.pull(verbose=True))"

The void-trial rule from REBOOT_PULL_PLAN.md applies: if the wand's scan
never sees SP-FILEPUSH, that trial says nothing about the handshake --
re-run rather than counting it.

Also, while the box is already on USB this session: confirm G11/G12 are
really the side keys. T6's whole input model rests on that assumption and
nothing has verified it yet.

  mpremote connect <BOX_PORT> exec "import probe_ap_cycle; probe_ap_cycle.check_side_keys()"
"""

import time
import socket

from code_server import _start_ap, SSID, PWD, PORT, AP_SETTLE_MS

N_CYCLES = 10

# Raw pin numbers under test -- intentionally not imported from buttons.py.
# The point of this check is to verify the assumption buttons.py already
# bakes in (G11/G12, active-low, PULL_UP), not to exercise buttons.py itself.
B1_PIN = 11
B2_PIN = 12

RESULTS = []

# Held module-level so the hand-off listening socket from the final cycle
# is not garbage-collected out from under step B between run() returning
# and the wand's connect() -- MicroPython sockets have no other reference
# once _one_cycle() returns.
_HANDOFF_SRV = None


def _result(key, value, ok=True):
    line = "RESULT %s=%s ok=%s" % (key, value, "1" if ok else "0")
    print(line)
    RESULTS.append((key, value, ok))


def _paint(lines, color=0xFFFFFF, bg=0x111111):
    """Best-effort LCD paint. The Box is normally observed only by its
    screen, so results have to land there too, not just on serial -- but a
    paint failure must never take a real AP-cycle result down with it."""
    try:
        import M5
        M5.begin()
        M5.Lcd.setRotation(1)
        font = getattr(M5.Lcd.FONTS, "DejaVu18", None)
        if font:
            M5.Lcd.setFont(font)
        M5.Lcd.fillScreen(bg)
        M5.Lcd.setTextColor(color, bg)
        y = 8
        for line in lines:
            M5.Lcd.setCursor(8, y)
            M5.Lcd.print(line)
            y += 22
    except Exception as e:
        print("# probe_ap_cycle paint failed: %s" % str(e))


def _one_cycle(i, leave_up=False):
    """One _start_ap() -> bind/listen -> close -> teardown cycle.

    Returns (activated, bound, went_down, elapsed_ms). went_down is only
    meaningful (and only checked) when leave_up is False -- the whole point
    of the final cycle's leave_up=True is to violate that check on purpose.
    A per-cycle exception is caught here rather than escaping run(), so one
    bad cycle reports its own failure instead of losing the other 9.

    On the hand-off cycle (leave_up=True) the listening socket is kept open
    too, not just the AP -- closing it would let the wand join the AP fine
    and then have its TCP connect() reset, which looks like a probe failure
    but is really just this file forgetting to leave a socket for it.
    """
    global _HANDOFF_SRV
    t0 = time.ticks_ms()
    activated = False
    bound = False
    went_down = False
    ap = None
    srv = None
    try:
        ap = _start_ap(SSID, PWD)
        activated = bool(ap.active())
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', PORT))
        srv.listen(1)
        bound = True
    except Exception as e:
        print("# cycle %d setup err: %s" % (i, str(e)))
    finally:
        if srv is not None and not leave_up:
            try:
                srv.close()
            except OSError:
                pass
    if leave_up:
        _HANDOFF_SRV = srv  # keep it referenced past this function's return
        elapsed = time.ticks_diff(time.ticks_ms(), t0)
        return activated, bound, went_down, elapsed
    if ap is not None:
        try:
            ap.active(False)
        except OSError:
            pass
        time.sleep_ms(AP_SETTLE_MS)
        try:
            went_down = not ap.active()
        except OSError:
            went_down = False
    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    return activated, bound, went_down, elapsed


def run(n=N_CYCLES, leave_up_on_last=True):
    """Run n AP down/up cycles. On the last one, leave the AP up (default)
    as the hand-off to step B rather than tearing it down -- pass
    leave_up_on_last=False for a fully self-contained run that leaves
    nothing up on exit (useful for a dry run with no wand on hand).
    """
    print("# probe_ap_cycle start (n=%d)" % n)
    n_ok = 0
    for i in range(1, n + 1):
        last = (i == n)
        leave_up = last and leave_up_on_last
        activated, bound, went_down, elapsed = _one_cycle(i, leave_up=leave_up)
        ok = activated and bound and (leave_up or went_down)
        if ok:
            n_ok += 1
        note = "left_up(hand-off)" if leave_up else "torn_down"
        _result(
            "cycle_%d" % i,
            "activated=%d bound=%d down=%d ms=%d %s"
            % (activated, bound, went_down, elapsed, note),
            ok,
        )
    all_ok = n_ok == n
    _result("ap_cycle", "%d/%d" % (n_ok, n), all_ok)
    _paint(
        [
            "AP cycle: %d/%d" % (n_ok, n),
            "AP: %s" % ("UP (step B)" if leave_up_on_last else "down"),
            "see serial for detail",
        ],
        color=(0x3FE0C2 if all_ok else 0xFF7A4A),
    )
    if leave_up_on_last:
        print("# AP left UP for wand join (step B) -- SSID=%s port=%d" % (SSID, PORT))
    else:
        print("# probe_ap_cycle done -- AP torn down, nothing left up")
    return n_ok, n


def _wait_for_press(pin, wait_s):
    t0 = time.ticks_ms()
    was_down = pin.value() == 0
    while time.ticks_diff(time.ticks_ms(), t0) < wait_s * 1000:
        down = pin.value() == 0
        if down and not was_down:
            return True
        was_down = down
        time.sleep_ms(20)
    return False


def check_side_keys(wait_s=10):
    """Confirm G11/G12 read 0 pressed / 1 released, and report which
    physical key maps to which pin. Prompts for one key at a time so a
    result of "not seen" on only one of the two still tells you something.

    The prompt is painted on the LCD, not just printed to serial: over
    mpremote exec the only thing a person standing at the bench can watch
    in real time is the screen -- serial output only surfaces after the
    call returns, by which point any timing window has already closed.
    """
    import machine

    b1 = machine.Pin(B1_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    b2 = machine.Pin(B2_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

    _paint(["Press the key you", "think is Key1 (B1)", "now! (%ds)" % wait_s],
           color=0xFFA000)
    print("# press the key you believe is Key1/B1 (G11=pin %d) -- watch the LCD"
          % B1_PIN)
    seen_b1 = _wait_for_press(b1, wait_s)
    _result("g11_pin%d_pressed" % B1_PIN, seen_b1, seen_b1)
    _paint(["Key1 (B1): %s" % ("seen" if seen_b1 else "NOT seen")],
           color=(0x3FE0C2 if seen_b1 else 0xFF7A4A))
    time.sleep_ms(1200)

    _paint(["Press the key you", "think is Key2 (B2)", "now! (%ds)" % wait_s],
           color=0xFFA000)
    print("# press the key you believe is Key2/B2 (G12=pin %d) -- watch the LCD"
          % B2_PIN)
    seen_b2 = _wait_for_press(b2, wait_s)
    _result("g12_pin%d_pressed" % B2_PIN, seen_b2, seen_b2)

    both_ok = seen_b1 and seen_b2
    _paint(
        [
            "G11(pin%d): %s" % (B1_PIN, "seen" if seen_b1 else "NOT seen"),
            "G12(pin%d): %s" % (B2_PIN, "seen" if seen_b2 else "NOT seen"),
        ],
        color=(0x3FE0C2 if both_ok else 0xFF7A4A),
    )
    print("# report which physical key you pressed for each pin above")
    return seen_b1, seen_b2
