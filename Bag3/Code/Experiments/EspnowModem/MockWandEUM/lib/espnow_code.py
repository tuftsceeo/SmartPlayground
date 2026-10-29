"""
espnow_code.py -- receive a game file over ESP-NOW (wand side)
===============================================================
No WiFi join, no radio switch, no reset. Runs on the ESPNowManager the wand already has up.

The receiver drives the transfer, so it never asks for more than its ESP-NOW
rxbuf and window buffer can hold:

    wand -> broadcast  {"type":"code_req","id":r,"slug":s,"hub":h[,"host":id]}
                       "host" pins the request to one sender (the getcode
                       card's "@<id>"); other senders do not answer
    host -> wand       {"type":"code_offer","id":r,"name":n,"size":N,
                        "sha":hex,"chunks":K,"chunk":C}
                       size 0 = refusal; why "busy" + retry_ms = ask again
    wand -> host       {"type":"code_get","id":r,"from":b,"n":w}
    host -> wand       b"CX" + id(1) + seq(u16 BE) + data      (w frames)
    wand -> host       {"type":"code_done","id":r,"ok":bool,"why":str}

Icons (receive(..., icon_dir=...), hub "icon_display"): the game's offer also
carries "icons" (names) and "icons_n" (total). Names past the ones that fit
the offer frame are listed with
    wand -> host       {"type":"code_req",...,"list_from":k}
    host -> wand       {"type":"code_icons","id":r,"from":k,"n":N,"icons":[...]}
then each icon is one code_req with "file":<name>, sent to the sender that
served the game, received the same way into <icon_dir>/<name> (size and
sha256 checked, not compiled). A failed icon is logged and skipped; it does
not change the game's result.

A window that is not complete within GET_WAIT_MS is requested again from
its first missing chunk. The file lands as <dest>.part, is checked (size,
sha256, compile()) and only then promoted, keeping <dest>.bak.

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
# Random delay before each code_req, so wands tapped together do not keep
# colliding on the same broadcast slots.
REQ_JITTER_MS = 300
# A "busy" offer means the sender is serving its maximum number of wands.
# Wait its retry_ms plus up to as much again at random, then ask again,
# for at most BUSY_WAIT_MAX_MS in total.
BUSY_RETRY_MS = 2000
BUSY_WAIT_MAX_MS = 120000
GET_WAIT_MS = 400
MAX_STALLS = 12              # consecutive windows with no progress
MAX_ICONS = 64               # same cap as the sender

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


def _jitter(max_ms):
    """Random delay in [0, max_ms] ms."""
    if max_ms <= 0:
        return 0
    return int.from_bytes(os.urandom(2), 'big') % (max_ms + 1)


def _sleep_polling(enow, ms):
    """Sleep ms while draining (and discarding) incoming messages."""
    deadline = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        enow.poll()
        time.sleep_ms(1)


def _compile_check(path, stats, verbose):
    """'' if path parses, else the reason.

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


def _valid_icon_name(name):
    return (isinstance(name, str) and name.endswith(".py") and 3 < len(name) <= 40
            and "/" not in name and ".." not in name)


def _request(enow, req, stats, verbose, to=None):
    """Send req until a code_offer for it arrives, backing off on "busy".

    to: unicast to that sender (already a peer) instead of broadcasting.
    Returns (offer, sender_mac), or (None, 'nohost') / (None, 'busy').
    """
    rid = req["id"]
    offer = None
    sender = None
    tries = 0
    busy_waits = 0
    busy_deadline = time.ticks_add(time.ticks_ms(), BUSY_WAIT_MAX_MS)
    while tries < REQ_TRIES:
        _sleep_polling(enow, _jitter(REQ_JITTER_MS))
        tries += 1
        if to is None:
            sent = enow.broadcast(req)
        else:
            sent = enow.send_to(to, req)
        if not sent:
            print("[ENX] code_req send failed (attempt %d)" % tries)
        deadline = time.ticks_add(time.ticks_ms(), OFFER_WAIT_MS)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            mt, data, mac = enow.poll()
            if (mt == "raw" and isinstance(data, dict)
                    and data.get("type") == "code_offer"
                    and data.get("id") == rid):
                offer, sender = data, mac
                break
            time.sleep_ms(1)
        if offer is None:
            continue
        if offer.get("size", 0) or offer.get("why") != "busy":
            break
        # Sender is at capacity: back off and ask again.
        busy_waits += 1
        stats["busy_waits"] = busy_waits
        if time.ticks_diff(busy_deadline, time.ticks_ms()) <= 0:
            if verbose:
                print("[ENX] sender still busy after %d s, giving up"
                      % (BUSY_WAIT_MAX_MS // 1000))
            return None, 'busy'
        retry = offer.get("retry_ms", BUSY_RETRY_MS)
        wait = retry + _jitter(retry)
        if verbose:
            print("[ENX] sender busy, retrying in %d ms (wait %d)"
                  % (wait, busy_waits))
        _sleep_polling(enow, wait)
        offer = None
        tries = 0
    stats["busy_waits"] = busy_waits
    if offer is None:
        return None, 'nohost'
    return offer, sender


def _fetch(enow, sender, rid, offer, dest, stats, on_progress, verbose,
           compile_check):
    """Pull the offered file into dest.part, check it and promote it to
    dest. compile_check: also compile() it and keep the old copy as
    dest.bak (game files; icons are size and sha256 only). Sends code_done. Returns '' or the reason it
    failed (the old dest is left in place)."""
    size = offer["size"]
    chunks = offer["chunks"]
    chunk = offer["chunk"]
    want_sha = offer["sha"]
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
        elif compile_check:
            why = _compile_check(tmp_path, stats, verbose)
    if why:
        if verbose:
            print("[ENX] FAILED: %s: %s" % (dest, why))
        os.remove(tmp_path)
    else:
        if compile_check:
            try:
                os.rename(dest, dest + '.bak')
            except OSError:
                pass    # no previous copy of this game
        os.rename(tmp_path, dest)
    stats["t_done"] = time.ticks_ms()
    enow.send_to(sender, {"type": "code_done", "id": rid, "ok": not why,
                          "why": why})
    stats.update({"gets": n_gets, "frames": n_frames, "dup": n_dup,
                  "min_gc_free": min_free})
    return why


def _offer_ok(offer):
    chunk = offer.get("chunk", 0)
    return (chunk > 0 and chunk + FRAME_HDR <= 250
            and offer.get("chunks") == (offer["size"] + chunk - 1) // chunk)


def _icon_names(enow, sender, offer, slug, hubtype, verbose):
    """Every icon name for the game: the offer's, then list_from pages."""
    names = list(offer.get("icons") or [])
    total = offer.get("icons_n", len(names))
    if not isinstance(total, int):
        return names
    total = min(total, MAX_ICONS)
    while len(names) < total:
        rid = _rid()
        enow.send_to(sender, {"type": "code_req", "id": rid, "slug": slug,
                              "hub": hubtype, "list_from": len(names)})
        page = None
        deadline = time.ticks_add(time.ticks_ms(), OFFER_WAIT_MS)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            mt, data, mac = enow.poll()
            if (mt == "raw" and mac == sender and isinstance(data, dict)
                    and data.get("type") == "code_icons"
                    and data.get("id") == rid):
                page = data
                break
            time.sleep_ms(1)
        if page is None or page.get("from") != len(names) or not page.get("icons"):
            if verbose:
                print("[ENX] icon list stopped at %d/%d" % (len(names), total))
            break
        names.extend(page["icons"])
    return names[:total]


def _receive_icons(enow, sender, offer, slug, hubtype, icon_dir, verbose):
    """Pull every icon the game's offer lists into icon_dir. Returns the
    number promoted; a failed icon is skipped."""
    try:
        os.mkdir(icon_dir)
    except OSError:
        pass
    names = _icon_names(enow, sender, offer, slug, hubtype, verbose)
    if verbose and names:
        print("[ENX] icon leg: %d file(s)" % len(names))
    promoted = 0
    for name in names:
        if not _valid_icon_name(name):
            print("[ENX] icon: refusing name %r" % (name,))
            continue
        st = {}
        rid = _rid()
        ioffer, isender = _request(enow, {"type": "code_req", "id": rid,
                                          "slug": slug, "hub": hubtype,
                                          "file": name}, st, False, to=sender)
        if ioffer is None or not ioffer.get("size", 0):
            print("[ENX] icon %s: not served (%s)"
                  % (name, isender if ioffer is None else ioffer.get("why")))
            continue
        if ioffer.get("name") != name or not _offer_ok(ioffer):
            print("[ENX] icon %s: bad offer %r" % (name, ioffer))
            continue
        why = _fetch(enow, sender, rid, ioffer, icon_dir + '/' + name, st,
                     None, False, False)
        if why:
            print("[ENX] icon FAILED: %s: %s" % (name, why))
        else:
            promoted += 1
    if verbose and names:
        print("[ENX] %d/%d icon(s) promoted" % (promoted, len(names)))
    return promoted


def receive(enow, slug=None, hubtype=None, on_progress=None, verbose=True,
            host_id=None, icon_dir=None):
    """Fetch a game over ESP-NOW and promote it into /games.

    host_id (the getcode card's "@<id>" suffix) restricts the request to
    the sender with that id; None or "" takes the first sender to answer.
    icon_dir: after the game file, fetch the icons its offer lists into
    this directory (icon count in LAST_STATS["icons"]).

    Returns True on success, 'nohost' if no sender answered, 'norequest' if
    the sender has no such game, 'busy' if the sender stayed at capacity for
    BUSY_WAIT_MAX_MS, or False on a failed transfer (old game left in
    place). Icon failures do not change the result. Timing and counters go
    to LAST_STATS.
    """
    global LAST_STATS
    stats = {"t_start": time.ticks_ms()}
    LAST_STATS = stats
    rid = _rid()
    req = {"type": "code_req", "id": rid, "slug": slug or "",
           "hub": hubtype or ""}
    if host_id:
        req["host"] = host_id

    offer, sender = _request(enow, req, stats, verbose)
    stats["t_offer"] = time.ticks_ms()
    if offer is None:
        if verbose and sender == 'nohost':
            print("[ENX] no sender answered code_req for %r (host %r)"
                  % (slug or "<active>", host_id or "<any>"))
        return sender

    size = offer.get("size", 0)
    if not size:
        if verbose:
            print("[ENX] sender has no game %r" % (slug or "<active>"))
        return 'norequest'
    name = offer.get("name", "")
    if not name.endswith(".py") or not is_valid_slug(name[:-3]):
        print("[ENX] refusing offered name %r" % name)
        return False
    if not _offer_ok(offer):
        print("[ENX] inconsistent offer %r" % offer)
        return False
    chunks = offer["chunks"]

    enow.add_peer(sender)
    game_store.ensure_dir()
    dest = game_store.GAMES_DIR + '/' + name
    why = _fetch(enow, sender, rid, offer, dest, stats, on_progress, verbose,
                 True)
    ok = not why
    if ok and icon_dir:
        stats["icons"] = _receive_icons(enow, sender, offer, name[:-3],
                                        hubtype or "", icon_dir, verbose)

    t0 = stats["t_start"]
    stats.update({
        "ok": ok, "why": why, "name": name[:-3], "bytes": size,
        "chunks": chunks,
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
                 stats["gets"], stats["frames"], stats["dup"],
                 stats["min_gc_free"]))
    return ok
