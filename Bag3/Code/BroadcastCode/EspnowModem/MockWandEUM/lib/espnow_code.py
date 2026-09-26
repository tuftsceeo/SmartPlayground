"""
espnow_code.py -- receive a game file over ESP-NOW (wand side)
===============================================================
ESP-NOW counterpart of code_puller.py: no WiFi join, no radio switch, no
reset. Runs on the ESPNowManager the wand already has up.

The receiver drives the transfer, so it never asks for more than its ESP-NOW
rxbuf and window buffer can hold:

    wand -> broadcast  {"type":"code_req","id":r,"slug":s,"hub":h}
    host -> wand       {"type":"code_offer","id":r,"name":n,"size":N,
                        "sha":hex,"chunks":K,"chunk":C}   (size 0 = refusal)
    wand -> host       {"type":"code_get","id":r,"from":b,"n":w}
    host -> wand       b"CX" + id(1) + seq(u16 BE) + data      (w frames)
    wand -> host       {"type":"code_done","id":r,"ok":bool,"why":str}

A window that is not complete within GET_WAIT_MS is requested again from
its first missing chunk. The file lands as <dest>.part, is checked (size,
sha256, compile()) and only then promoted, keeping <dest>.bak -- the same
rules as code_puller.pull().

PEER: EspnowModem/host/code_sender.py holds a hand-kept copy of the message
names and frame layout. Change both in the same commit.
"""

import gc
import os
import time
from binascii import hexlify

try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

import game_store
from game_store import is_valid_slug

FRAME_TAG = b"CX"
FRAME_HDR = 5                # tag(2) id(1) seq(2)
WINDOW = 8                   # chunks per code_get; must fit the ESP-NOW rxbuf
WRITE_BUF = 4096             # batch flash writes; one write stalls the radio
REQ_TRIES = 3
OFFER_WAIT_MS = 800
GET_WAIT_MS = 400
MAX_STALLS = 12              # consecutive windows with no progress

# Timing and counters of the most recent receive(), for the caller to log.
# (MicroPython functions do not take attributes, hence a module global.)
LAST_STATS = None


def _rid():
    return os.urandom(1)[0]


PSRAM_REGION_MIN = 1024 * 1024   # IDF regions this large are PSRAM


def _idf_largest():
    """Largest free internal IDF heap block, or None if not available."""
    try:
        import esp32
    except ImportError:
        return None
    big = 0
    for total, free, largest, low in esp32.idf_heap_info(esp32.HEAP_DATA):
        if total < PSRAM_REGION_MIN and largest > big:
            big = largest
    return big


def _compile_check(path, stats, verbose):
    """'' if path parses, else the reason (same check as code_puller).

    Runs after every transfer buffer has been released, with a collect
    first, and records the heap it had to work with (pre_compile_* in
    stats) so the margin is visible per run. A MemoryError is reported
    separately from a syntax error: the source is fine but this heap cannot
    hold the compile, and the game could not be imported in this state
    either.
    """
    size = os.stat(path)[6]
    gc.collect()
    gc.collect()
    stats["pre_compile_gc_free"] = gc.mem_free()
    stats["pre_compile_idf_largest"] = _idf_largest()
    if verbose:
        print("[ENX] pre-compile: %d B source, gc free %d, idf largest %s"
              % (size, stats["pre_compile_gc_free"],
                 stats["pre_compile_idf_largest"]))
    src = None
    try:
        with open(path, 'r') as f:
            src = f.read()
        compile(src, path, 'exec')
        return ""
    except MemoryError as e:
        src = None
        gc.collect()
        why = ("too large to compile here (%d B source, %d B gc free): %s"
               % (size, gc.mem_free(), e))
    except Exception as e:
        why = "does not compile: %s" % e
    finally:
        src = None
    if verbose:
        print("[ENX] rejected: %s %s" % (path, why))
    return why


def _progress(cb, got, total):
    if cb is None:
        return
    try:
        cb(got, total)
    except Exception as e:
        print("[ENX] on_progress err: %s" % e)


def receive(enow, slug=None, hubtype=None, on_progress=None, verbose=True):
    """Fetch a game over ESP-NOW and promote it into /games.

    Returns True on success, 'nohost' if no sender answered, 'norequest' if
    the sender has no such game, or False on a failed transfer (old game
    left in place). Timing and counters go to LAST_STATS.
    """
    global LAST_STATS
    stats = {"t_start": time.ticks_ms()}
    LAST_STATS = stats
    rid = _rid()
    req = {"type": "code_req", "id": rid, "slug": slug or "",
           "hub": hubtype or ""}

    offer = None
    sender = None
    for attempt in range(REQ_TRIES):
        if not enow.broadcast(req):
            print("[ENX] code_req broadcast failed (attempt %d)" % (attempt + 1))
        deadline = time.ticks_add(time.ticks_ms(), OFFER_WAIT_MS)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            mt, data, mac = enow.poll()
            if (mt == "raw" and isinstance(data, dict)
                    and data.get("type") == "code_offer"
                    and data.get("id") == rid):
                offer, sender = data, mac
                break
            time.sleep_ms(1)
        if offer is not None:
            break
    stats["t_offer"] = time.ticks_ms()
    if offer is None:
        if verbose:
            print("[ENX] no sender answered code_req for %r" % (slug or "<active>"))
        return 'nohost'

    size = offer.get("size", 0)
    if not size:
        if verbose:
            print("[ENX] sender has no game %r" % (slug or "<active>"))
        return 'norequest'
    name = offer.get("name", "")
    chunks = offer["chunks"]
    chunk = offer["chunk"]
    want_sha = offer["sha"]
    if not name.endswith(".py") or not is_valid_slug(name[:-3]):
        print("[ENX] refusing offered name %r" % name)
        return False
    if chunks != (size + chunk - 1) // chunk or chunk + FRAME_HDR > 250:
        print("[ENX] inconsistent offer %r" % offer)
        return False

    enow.add_peer(sender)
    game_store.ensure_dir()
    dest = game_store.GAMES_DIR + '/' + name
    tmp_path = dest + '.part'
    if verbose:
        print("[ENX] receiving %s from %s: %d bytes, %d chunks"
              % (dest, sender, size, chunks))

    gc.collect()
    slots = bytearray(WINDOW * chunk)
    slot_len = [0] * WINDOW
    wbuf = bytearray(WRITE_BUF)
    wlen = 0
    h = hashlib.sha256()
    base = 0
    stalls = 0
    n_gets = 0
    n_frames = 0
    n_dup = 0
    min_free = gc.mem_free()
    ok = False
    why = ""
    _progress(on_progress, 0, size)
    stats["t_body"] = time.ticks_ms()

    with open(tmp_path, 'wb') as f:
        while base < chunks:
            n = min(WINDOW, chunks - base)
            for i in range(n):
                slot_len[i] = 0
            enow.send_to(sender, {"type": "code_get", "id": rid,
                                  "from": base, "n": n})
            n_gets += 1
            start_base = base
            deadline = time.ticks_add(time.ticks_ms(), GET_WAIT_MS)
            win_base = base
            have = 0
            while have < n and time.ticks_diff(deadline, time.ticks_ms()) > 0:
                mt, data, mac = enow.poll()
                if (mt != "raw" or mac != sender
                        or not isinstance(data, (bytes, bytearray))
                        or data[:2] != FRAME_TAG or data[2] != rid):
                    time.sleep_ms(1)
                    continue
                n_frames += 1
                seq = (data[3] << 8) | data[4]
                i = seq - win_base
                if i < 0 or i >= n or slot_len[i]:
                    n_dup += 1
                    continue
                dlen = len(data) - FRAME_HDR
                o = i * chunk
                slots[o:o + dlen] = data[FRAME_HDR:]
                slot_len[i] = dlen
                have += 1
            # Commit the contiguous prefix of this window.
            k = 0
            while k < n and slot_len[k]:
                dlen = slot_len[k]
                piece = memoryview(slots)[k * chunk:k * chunk + dlen]
                h.update(piece)
                if wlen + dlen > WRITE_BUF:
                    f.write(memoryview(wbuf)[:wlen])
                    wlen = 0
                wbuf[wlen:wlen + dlen] = piece
                wlen += dlen
                k += 1
            base = win_base + k
            free = gc.mem_free()
            if free < min_free:
                min_free = free
            if base == start_base:
                stalls += 1
                if stalls >= MAX_STALLS:
                    why = "stalled at chunk %d/%d" % (base, chunks)
                    break
            else:
                stalls = 0
                _progress(on_progress, min(base * chunk, size), size)
        if wlen:
            f.write(memoryview(wbuf)[:wlen])
    stats["t_body_end"] = time.ticks_ms()
    got_sha = hexlify(h.digest()).decode()
    # Release every transfer buffer before the compile check; it needs one
    # large contiguous block and the wand has no PSRAM.
    slots = None
    wbuf = None
    slot_len = None
    h = None

    if not why:
        if os.stat(tmp_path)[6] != size:
            why = "size mismatch"
        elif got_sha != want_sha:
            why = "sha256 mismatch"
        else:
            why = _compile_check(tmp_path, stats, verbose)
    if why:
        if verbose:
            print("[ENX] FAILED: %s: %s" % (dest, why))
        os.remove(tmp_path)
    else:
        try:
            os.rename(dest, dest + '.bak')
        except OSError:
            pass    # no previous copy of this game
        os.rename(tmp_path, dest)
        ok = True
    stats["t_done"] = time.ticks_ms()
    enow.send_to(sender, {"type": "code_done", "id": rid, "ok": ok,
                          "why": why})

    t0 = stats["t_start"]
    stats.update({
        "ok": ok, "why": why, "name": name[:-3], "bytes": size,
        "chunks": chunks,
        "gets": n_gets, "frames": n_frames, "dup": n_dup,
        "min_gc_free": min_free,
        "offer_ms": time.ticks_diff(stats["t_offer"], t0),
        "body_ms": time.ticks_diff(stats["t_body_end"], stats["t_body"]),
        "verify_ms": time.ticks_diff(stats["t_done"], stats["t_body_end"]),
        "total_ms": time.ticks_diff(stats["t_done"], t0),
    })
    if verbose:
        print("[ENX] %s %s: %d B total %d ms (offer %d, body %d, verify %d) "
              "%.1f KB/s body, gets=%d frames=%d dup=%d min_gc_free=%d"
              % ("OK" if ok else "FAIL", name, size, stats["total_ms"],
                 stats["offer_ms"], stats["body_ms"], stats["verify_ms"],
                 size / 1024 / max(stats["body_ms"], 1) * 1000,
                 n_gets, n_frames, n_dup, min_free))
    return True if ok else False
