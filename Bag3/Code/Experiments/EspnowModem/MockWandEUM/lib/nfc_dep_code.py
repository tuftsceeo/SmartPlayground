"""
nfc_dep_code.py -- receive a game file over NFC-DEP (wand side)
================================================================
NFC-DEP counterpart of espnow_code.py: the wand's PN532 becomes a DEP
initiator, pulls one file from a wand held face-to-face as a DEP target
(tools/devtests/xfer_host.py MODE "nfc"), and promotes it with the same
.part / sha256 / compile() / .bak rules. No WiFi, no radio switch, no reset.

BENCH: needs pn532_dep.py and dep_proto.py (tools/devtests/nfc_dep/) on the
wand's flash root. Imported only from main.py's pull path, after ESP-NOW has
its memory -- nothing here may move ahead of the radio.

The wire format is dep_proto.py's (H header, C chunk, D done). The target
serves one configured file; there is no slug in the request, so a slug that
does not match the served name is refused after the header.
"""

import gc
import os
import time
from binascii import hexlify

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

import machine
import game_store
from game_store import is_valid_slug

# Best measured setting (nfc_dep/RESULTS.md): 400 kHz I2C, 424 kbps, 240 B.
# The firmware's own bus runs at HUB_CONFIG["i2c_freq"]; this module drives
# the same pins through its own SoftI2C object and leaves that one alone.
I2C_FREQ = 400_000
BAUD = 0x02                  # pn532_dep.BAUD_424
CHUNK = 240
LINK_WAIT_MS = 5000          # target must answer InJumpForDEP within this
WRITE_BUF = 4096

# PN532 power-on RFConfiguration values (UM0701 7.3.1), restored afterwards
# because lib/pn532.py never sets them and relies on the defaults.
_RF_RETRIES_DEFAULT = bytes([0x05, 0xFF, 0x01, 0xFF])
_RF_TIMINGS_DEFAULT = bytes([0x02, 0x00, 0x0B, 0x0A])

LAST_STATS = None


def _p32(n):
    return bytes([(n >> 24) & 0xFF, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])


def _u32(b, i):
    return (b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3]


def _link(nfc, DepError):
    """Poll InJumpForDEP for LINK_WAIT_MS. Returns True once a target answers."""
    deadline = time.ticks_add(time.ticks_ms(), LINK_WAIT_MS)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        try:
            if nfc.jump_for_dep(BAUD) is not None:
                return True
        except DepError as e:
            if e.status is None:
                nfc.abort()
        time.sleep_ms(1)
    return False


def receive(sda, scl, slug=None, on_progress=None, verbose=True):
    """Fetch a game over NFC-DEP and promote it into /games.

    Returns True on success, 'nohost' if no target answered, 'norequest' if
    the target serves a different game, or False on a failed transfer (old
    game left in place). Timing goes to LAST_STATS, with espnow_code's keys.
    """
    global LAST_STATS
    import pn532_dep
    import dep_proto
    from pn532_dep import PN532Dep, DepError
    from espnow_code import _compile_check

    stats = {"t_start": time.ticks_ms()}
    LAST_STATS = stats
    i2c = machine.SoftI2C(sda=machine.Pin(sda), scl=machine.Pin(scl), freq=I2C_FREQ)
    nfc = PN532Dep(i2c)
    linked = False
    tmp_path = None
    why = ""
    ok = False
    size = 0
    name = ""
    n_chunks = 0
    try:
        nfc.abort()
        nfc.begin()
        nfc.configure_initiator()
        linked = _link(nfc, DepError)
        stats["t_offer"] = time.ticks_ms()
        if not linked:
            if verbose:
                print("[NFX] no DEP target answered in %d ms" % LINK_WAIT_MS)
            return 'nohost'
        size, want_sha, name = dep_proto.parse_header(
            nfc.exchange(b'H', dep_proto.HEADER_MAX))
        if not name.endswith(".py") or not is_valid_slug(name[:-3]):
            print("[NFX] refusing offered name %r" % name)
            return False
        if slug and name[:-3] != slug:
            if verbose:
                print("[NFX] target serves %r, not %r" % (name, slug))
            return 'norequest'
        game_store.ensure_dir()
        dest = game_store.GAMES_DIR + '/' + name
        tmp_path = dest + '.part'
        if verbose:
            print("[NFX] receiving %s: %d bytes, %d-byte chunks" % (dest, size, CHUNK))
        gc.collect()
        wbuf = bytearray(WRITE_BUF)
        wlen = 0
        h = hashlib.sha256()
        off = 0
        stats["t_body"] = time.ticks_ms()
        try:
            with open(tmp_path, 'wb') as f:
                while off < size:
                    n = min(CHUNK, size - off)
                    resp = nfc.exchange(b'C' + _p32(off) + bytes([n]), 4 + n)
                    if len(resp) != 4 + n or _u32(resp, 0) != off:
                        why = "chunk reply mismatch at %d" % off
                        break
                    piece = memoryview(resp)[4:]
                    h.update(piece)
                    if wlen + n > WRITE_BUF:
                        f.write(memoryview(wbuf)[:wlen])
                        wlen = 0
                    wbuf[wlen:wlen + n] = piece
                    wlen += n
                    off += n
                    n_chunks += 1
                    if on_progress is not None:
                        on_progress(off, size)
                if wlen:
                    f.write(memoryview(wbuf)[:wlen])
            if not why and nfc.exchange(b'D', 2) != b'OK':
                why = "bad done reply"
        except DepError as e:
            why = "link lost at %d/%d: %s" % (off, size, e)
            if e.status is None:
                nfc.abort()
        stats["t_body_end"] = time.ticks_ms()
        got_sha = h.digest()
        wbuf = None
        h = None
        try:
            nfc.release()
        except DepError as e:
            print("[NFX] release: %s" % e)
        linked = False
        if not why:
            if os.stat(tmp_path)[6] != size:
                why = "size mismatch"
            elif got_sha != want_sha:
                why = "sha256 mismatch"
            else:
                why = _compile_check(tmp_path, stats, verbose)
        if why:
            if verbose:
                print("[NFX] FAILED: %s: %s" % (dest, why))
            os.remove(tmp_path)
        else:
            try:
                os.rename(dest, dest + '.bak')
            except OSError:
                pass    # no previous copy of this game
            os.rename(tmp_path, dest)
            ok = True
    except DepError as e:
        print("[NFX] PN532 error: %s" % e)
        return False
    finally:
        if linked:
            try:
                nfc.release()
            except DepError:
                pass
        try:
            nfc.command(pn532_dep.CMD_RFCONFIGURATION, _RF_RETRIES_DEFAULT)
            nfc.command(pn532_dep.CMD_RFCONFIGURATION, _RF_TIMINGS_DEFAULT)
        except DepError as e:
            print("[NFX] RF config restore failed: %s" % e)

    stats["t_done"] = time.ticks_ms()
    t0 = stats["t_start"]
    stats.update({
        "ok": ok, "why": why, "name": name[:-3], "bytes": size,
        "chunks": n_chunks,
        "offer_ms": time.ticks_diff(stats["t_offer"], t0),
        "body_ms": time.ticks_diff(stats["t_body_end"], stats["t_body"]),
        "verify_ms": time.ticks_diff(stats["t_done"], stats["t_body_end"]),
        "total_ms": time.ticks_diff(stats["t_done"], t0),
    })
    if verbose:
        print("[NFX] %s %s: %d B total %d ms (link %d, body %d, verify %d) "
              "%.1f KB/s body, chunks=%d"
              % ("OK" if ok else "FAIL", name, size, stats["total_ms"],
                 stats["offer_ms"], stats["body_ms"], stats["verify_ms"],
                 size / 1024 / max(stats["body_ms"], 1) * 1000, n_chunks))
    return True if ok else False
