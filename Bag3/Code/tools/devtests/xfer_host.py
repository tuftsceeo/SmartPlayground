"""
xfer_host.py -- wand-to-wand transfer bench, sender side (wand A).

Run on a stock Mock Wand with `mpremote resume run`, beside a MockWandEUM
wand (wand B) held face-to-face with it. For each slug in SLUGS, RUNS times:
broadcast the REMOTE_GETCODE bench trigger, serve the file, wait for the
transfer to finish, then pause RUN_GAP_MS so wand B launches the game
(speed files return from play() at once) and is back in its idle loop.

  MODE "espnow": serves through EspnowModem/host/code_sender.py over this
                 wand's own radio (no modem). Its result is wand B's
                 code_done, so ok covers sha256 and compile().
  MODE "nfc":    broadcasts {"via":"nfc"}, then waits as an NFC-DEP target
                 and serves with dep_proto's wire format. ok here only means
                 the link finished; wand B's log has the compile result.

Needs on wand A's flash: /games/<slug>.py, code_sender.py (espnow), and
pn532_dep.py + dep_proto.py (nfc). Wand B's serial log is the record; this
side prints one XFER line per run for pacing and cross-checking.
"""

import sys
for _m in ("pn532_dep", "dep_proto", "code_sender"):
    sys.modules.pop(_m, None)

import gc
import os
import time
import hashlib
import machine

from espnow_manager import ESPNowManager

MODE = "espnow"              # "espnow" / "nfc"
SLUGS = ["speed05", "speed20", "speed28", "speed32", "speed36", "speed40"]
RUNS = 5
STARTUP_MS = 2000
RUN_GAP_MS = 4000            # after a result: wand B compiles, launches, idles
RUN_TIMEOUT_MS = 60000
STOP_LEAD_MS = 1500          # broadcast stop this long before each trigger
# nfc: wand B must take the trigger before this side answers as a target.
# At 300 ms wand B's idle card poll sometimes found this wand first and never
# handled the trigger (runs 3-5 of the first bench). Wand B keeps polling for
# a target for nfc_dep_code.LINK_WAIT_MS (5 s), so this can be generous.
TARGET_DELAY_MS = 1500
TARGET_WAIT_MS = 10000
GAMES_DIR = "/games"

# Mock Wand wiring (MockWand/lib/hubtype.py "wand"), best bench setting.
I2C_SDA = 22
I2C_SCL = 23
I2C_FREQ = 400_000
REQ_MAX = 16


def _serve_espnow(mgr, sender, slug):
    """Trigger one ESP-NOW pull and wait for its code_done. Returns (ok, detail)."""
    sender.last_result = None
    mgr.broadcast({"type": "getcode", "slug": slug})
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < RUN_TIMEOUT_MS:
        mt, data, mac = mgr.poll()
        if mt is not None:
            sender.handle(mt, data, mac)
        r = sender.last_result
        if r is not None:
            return r["ok"], "%d B %d ms frames=%d send_fail=%d %s" % (
                r["bytes"], r["ms"], r["frames"], r["send_fail"], r["why"])
        time.sleep_ms(1)
    return False, "host timeout"


def _file_header(path, name):
    """dep_proto header (size | sha256 | name_len | name), hashed from flash."""
    import dep_proto
    h = hashlib.sha256()
    size = 0
    buf = bytearray(1024)
    with open(path, "rb") as f:
        while True:
            n = f.readinto(buf)
            if not n:
                break
            h.update(memoryview(buf)[:n])
            size += n
    nb = name.encode()
    return dep_proto._p32(size) + h.digest() + bytes([len(nb)]) + nb


def _serve_nfc(mgr, nfc, slug):
    """Trigger one NFC-DEP pull and serve it as target. Returns (ok, detail)."""
    import dep_proto
    from pn532_dep import DepError, STATUS_RELEASED
    path = "%s/%s.py" % (GAMES_DIR, slug)
    header = _file_header(path, slug + ".py")
    mgr.broadcast({"type": "getcode", "slug": slug, "via": "nfc"})
    time.sleep_ms(TARGET_DELAY_MS)
    t0 = time.ticks_ms()
    try:
        nfc.init_as_target(timeout_ms=TARGET_WAIT_MS)
    except DepError as e:
        if e.status is None:
            nfc.abort()
        return False, "no link: %s" % e
    chunks = 0
    done = False
    with open(path, "rb") as f:
        while True:
            try:
                req = nfc.get_data(REQ_MAX, timeout_ms=3000)
            except DepError as e:
                if e.status == STATUS_RELEASED:
                    break
                if e.status is None:
                    nfc.abort()
                return False, "link failed after %d chunks: %s" % (chunks, e)
            op = req[0:1]
            if op == b'H':
                resp = header
            elif op == b'C':
                off, n = dep_proto._u32(req, 1), req[5]
                f.seek(off)
                resp = dep_proto._p32(off) + f.read(n)
                chunks += 1
            elif op == b'D':
                resp = b'OK'
                done = True
            else:
                return False, "unknown op %r" % op
            nfc.set_data(resp)
            time.sleep_ms(1)
    return done, "%d chunks, link %d ms" % (chunks, time.ticks_diff(time.ticks_ms(), t0))


def main():
    mgr = ESPNowManager()
    mgr.init()
    sender = nfc = None
    if MODE == "espnow":
        from code_sender import CodeSender
        sender = CodeSender(mgr, games_dir=GAMES_DIR)
    else:
        import pn532_dep
        i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
        nfc = pn532_dep.PN532Dep(i2c)
        nfc.abort()   # main.py was interrupted and may have left a command pending
        print("# PN532 fw", nfc.begin(), "i2c", I2C_FREQ)
    print("XFER start mode=%s slugs=%s runs=%d mem_free=%d"
          % (MODE, SLUGS, RUNS, gc.mem_free()))
    time.sleep_ms(STARTUP_MS)
    for slug in SLUGS:
        for run in range(1, RUNS + 1):
            mgr.broadcast_stop()
            time.sleep_ms(STOP_LEAD_MS)
            print("XFER trigger mode=%s slug=%s run=%d" % (MODE, slug, run))
            if MODE == "espnow":
                ok, detail = _serve_espnow(mgr, sender, slug)
            else:
                ok, detail = _serve_nfc(mgr, nfc, slug)
            print("XFER result mode=%s slug=%s run=%d ok=%s %s" % (MODE, slug, run, ok, detail))
            # Drain wand B's traffic while it launches and returns to idle.
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < RUN_GAP_MS:
                mt, data, mac = mgr.poll()
                if sender is not None and mt is not None:
                    sender.handle(mt, data, mac)
                time.sleep_ms(1)
    print("XFER all done")


main()
