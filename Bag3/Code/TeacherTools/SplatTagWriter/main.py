"""
SplatTagWriter main.py -- standalone Splat sticker labeller (Bag3 wand hardware)
==============================================================================
Replaces the wand's /main.py while labelling; needs the wand's /lib
(pn532.py, nfc_reader.py, hubtype.py, leds.py, buzzer.py).

One paced cycle, forever:
  1. BLE listen for LISTEN_MS (30 ms of every 100 ms), then PAUSE.
     Never connects to or pairs with a Splat; only reads advertisements.
     A Splat already written can be picked and written again.
  2. If exactly one Splat is close (>= MIN_RSSI and MARGIN_DB clear of the
     next): blue star, one beep. No Splat heard: amber star. Splats heard
     but none close enough or too many close: LEDs off.
  3. NFC read every NFC_GAP_MS for up to TAP_WAIT_MS. Hold the sticker on.
  4. Tag present on two reads in a row -> read text, pause, write
     "splat-<MAC>", pause, read back, pause. Green + two beeps = done,
     red + low beep = failed. Then back to 1.
Writes MIFARE Classic 1K (the Splat stickers) and NTAG. Writes only onto a
blank sticker or one holding "sp:..." / "splat-..." text.
"""

import time
import ubluetooth

ble = ubluetooth.BLE()
ble.active(True)

import sys
sys.path.append("/lib")
import gc
import machine
from hubtype import HUB_CONFIG
from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B, CMD_INLISTPASSIVETARGET
from nfc_reader import read_ndef_text, parse_splat_card, COMMON_KEYS
from leds import Leds, SHAPE_X, SHAPE_CHECK, SHAPE_STAR, RED, GREEN, BLUE, AMBER
from buzzer import Buzzer

LISTEN_MS = 1500        # one BLE listen
SCAN_INTERVAL_US = 100000
SCAN_WINDOW_US = 30000  # 30 % duty: no BLE flood
PAUSE_MS = 1000         # between listens
MIN_RSSI = -65
MARGIN_DB = 10
TAP_WAIT_MS = 20000
NFC_GAP_MS = 300        # between NFC reads
STEP_PAUSE_MS = 300     # between read / write / read back
DONE_PAUSE_MS = 2000

leds = Leds()
buz = Buzzer(HUB_CONFIG["buzzer_pin"])
i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                      scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                      freq=HUB_CONFIG["i2c_freq"])
nfc = PN532(i2c, HUB_CONFIG.get("nfc_addr", 0x24))
done = set()            # MACs written this session


def dbg(msg):
    print(f"[{time.ticks_ms() // 100 / 10:.1f}s] {msg}")


def nfc_wake():
    for n in range(3):
        try:
            fw = nfc.begin()
            dbg(f"nfc wake ok fw={fw} try={n + 1}")
            bound_retries()
            return True
        except Exception as e:
            dbg(f"nfc wake error try={n + 1}: {e}")
            time.sleep_ms(50)
    return False


def bound_retries():
    """RFConfiguration item 5: one passive-activation try per InList, so the
    PN532 answers "no tag" at once instead of searching until a tag turns up
    and leaving that late answer for the next command (stale reads)."""
    try:
        nfc._send_command(0x32, b"\x05\xFF\x01\x01")
        dbg("nfc: retries bounded (1 try per poll)")
    except Exception as e:
        dbg(f"nfc: retry bound FAILED {e}")


def flush():
    """Clear the PN532 tag buffer: abort any command still running (an ACK
    frame from the host aborts it) and read off any answer left waiting."""
    try:
        nfc.i2c.writeto(nfc.addr, b"\x00\x00\xFF\x00\xFF\x00")
    except Exception as e:
        dbg(f"flush: abort write error {e}")
    time.sleep_ms(5)
    for n in range(4):
        try:
            st = nfc.i2c.readfrom(nfc.addr, 1)
        except Exception:
            return
        if st[0] != 0x01:
            return
        junk = bytes(nfc.i2c.readfrom(nfc.addr, 32))
        dbg(f"flush: discarded stale frame {n + 1}: {junk}")
        time.sleep_ms(2)


def release():
    """InRelease all targets so the PN532 holds no tag between labels."""
    flush()
    try:
        nfc._send_command(0x52, b"\x00", timeout=200)
        dbg("nfc: released target")
    except Exception as e:
        dbg(f"nfc: release error {e}")
    flush()


def _poll_once():
    flush()
    try:
        resp = nfc._send_command(CMD_INLISTPASSIVETARGET, b"\x01\x00", timeout=100)
    except Exception as e:
        return None, str(e)
    if len(resp) < 6 or resp[0] == 0:
        return None, "no tag"
    return resp, None


def poll(timeout=80):
    """Dial timing (station.py DETECT_MS, card_writer.detect_tag): short
    bounded tries every 2 ms until `timeout`. Logs the last reason on a miss."""
    t0 = time.ticks_ms()
    tries = 0
    why = None
    resp = None
    while True:
        tries += 1
        resp, why = _poll_once()
        if resp is not None or time.ticks_diff(time.ticks_ms(), t0) >= timeout:
            break
        time.sleep_ms(2)
    ms = time.ticks_diff(time.ticks_ms(), t0)
    if resp is None:
        dbg(f"poll: none ({why}) tries={tries} {ms}ms")
        return None
    n = resp[5]
    uid = bytes(resp[6:6 + n])
    tag = {"uid": uid, "uid_hex": ":".join("%02X" % b for b in uid),
           "sak": resp[4], "atqa": (resp[2] << 8) | resp[3]}
    dbg(f"poll: TAG {tag['uid_hex']} sak=0x{tag['sak']:02X} atqa=0x{tag['atqa']:04X} {ms}ms")
    return tag


# ── BLE listen ─────────────────────────────────────────────────────────

_seen = {}
_scan_done = [False]
_adv_count = [0]


def _irq(event, data):
    if event == 5:              # scan result: keep it cheap
        _adv_count[0] += 1
        addr_type, addr, adv_type, rssi, adv = data
        if b"Splat" not in bytes(adv):
            return
        mac = ":".join(["%02X" % b for b in addr])
        if rssi > _seen.get(mac, -999):
            _seen[mac] = rssi
    elif event == 6:            # scan done
        _scan_done[0] = True


def listen():
    _seen.clear()
    _scan_done[0] = False
    _adv_count[0] = 0
    t_start = time.ticks_ms()
    ble.irq(_irq)
    ble.gap_scan(LISTEN_MS, SCAN_INTERVAL_US, SCAN_WINDOW_US, True)
    t0 = time.ticks_ms()
    while not _scan_done[0] and time.ticks_diff(time.ticks_ms(), t0) < LISTEN_MS + 500:
        time.sleep_ms(50)
    ble.gap_scan(None)
    ble.irq(None)
    ranked = sorted([(r, m) for m, r in _seen.items()], reverse=True)
    dbg(f"listen: {time.ticks_diff(time.ticks_ms(), t_start)}ms adverts={_adv_count[0]} "
        f"scan_done={_scan_done[0]} splats={sorted([(r, m) for m, r in _seen.items()], reverse=True)} "
        f"done={len(done)} free={gc.mem_free()}")
    # One meaning per display: amber star = no Splat heard; off = Splats
    # heard but none to label now. Blue / green / red are set by the caller.
    if not _seen:
        dbg("listen: no Splat heard")
        leds.show_shape(SHAPE_STAR, AMBER)
        return None
    if ranked[0][0] < MIN_RSSI:
        dbg(f"listen: strongest {ranked[0][1]} {ranked[0][0]}dBm is weaker than {MIN_RSSI}; bring it closer")
        leds.off()
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < MARGIN_DB:
        dbg(f"listen: {ranked[0]} and {ranked[1]} within {MARGIN_DB}dB; move others away")
        leds.off()
        return None
    return ranked[0][1]


# ── NFC write ──────────────────────────────────────────────────────────

def ndef_text(text):
    payload = bytes([2]) + b"en" + text.encode("utf-8")
    record = bytes([0xD1, 1, len(payload)]) + b"T" + payload
    return bytes([0x03, len(record)]) + record + bytes([0xFE])


def write_ntag(text):
    data = ndef_text(text)
    while len(data) % 4:
        data += b"\x00"
    dbg(f"write ntag: {len(data) // 4} pages {bytes(data)}")
    for i in range(len(data) // 4):
        try:
            nfc.ntag_write_page(4 + i, data[i * 4:i * 4 + 4])
            dbg(f"write ntag: page {4 + i} ok")
        except Exception as e:
            dbg(f"write ntag: page {4 + i} FAILED {e}")
            return False
        time.sleep_ms(30)
    return True


def write_classic(text):
    data = ndef_text(text)
    while len(data) % 16:
        data += b"\x00"
    blocks = [s * 4 + b for s in range(1, 16) for b in range(3)]
    dbg(f"write classic: {len(data) // 16} blocks {bytes(data)}")
    for i in range(len(data) // 16):
        blk = blocks[i]
        first = (blk // 4) * 4
        authed = False
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                tag = poll(300)
                if tag is None:
                    dbg(f"write classic: block {blk} reselect failed")
                    continue
                try:
                    if nfc.mifare_auth_block(tag["uid"], first, key, kt):
                        dbg(f"write classic: sector {first // 4} auth ok key={key.hex()} {'A' if kt == MIFARE_AUTH_A else 'B'}")
                        authed = True
                        break
                    dbg(f"write classic: sector {first // 4} auth no key={key.hex()} {'A' if kt == MIFARE_AUTH_A else 'B'}")
                except Exception as e:
                    dbg(f"write classic: sector {first // 4} auth error key={key.hex()}: {e}")
            if authed:
                break
        if not authed:
            dbg(f"write classic: block {blk} NO AUTH with any key")
            return False
        try:
            nfc.mifare_write_block(blk, data[i * 16:i * 16 + 16])
            dbg(f"write classic: block {blk} ok")
        except Exception as e:
            dbg(f"write classic: block {blk} FAILED {e}")
            return False
        time.sleep_ms(30)
    return True


def ok_to_write(text):
    if not text:
        return True
    t = text.strip()
    return bool(parse_splat_card(t)) or t.lower().startswith("sp:")


def label(mac):
    """Wait for a sticker and write mac to it. True when written."""
    want = "splat-" + mac.replace(":", "")
    dbg(f"label: want {want!r}")
    nfc_wake()
    last = None
    polls = 0
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < TAP_WAIT_MS:
        tag = poll()
        polls += 1
        uid = tag["uid_hex"] if tag else None
        if uid and uid == last:
            break
        if uid:
            buz.beep(2400, 20)          # tick: something seen once
        last = uid
        time.sleep_ms(NFC_GAP_MS)
    else:
        dbg(f"label: no steady sticker after {polls} polls / {TAP_WAIT_MS}ms")
        return False
    classic = tag["sak"] in (0x08, 0x18)
    dbg(f"label: steady tag {uid} {'classic' if classic else 'ntag'} after {polls} polls")
    time.sleep_ms(STEP_PAUSE_MS)
    text, uid2 = read_ndef_text(nfc, timeout=300)
    dbg(f"label: text before {text!r} (read uid {uid2})")
    # read_ndef_text() lowercases what it reads; compare the same way
    # (card_writer._verify_text does too).
    if text and text.strip() == want.lower():
        dbg("label: already holds this tag; writing it again")
    elif not ok_to_write(text):
        dbg("label: holds other text; NOT overwriting")
        return False
    time.sleep_ms(STEP_PAUSE_MS)
    try:
        poll(300)
        ok = write_classic(want) if classic else write_ntag(want)
    except Exception as e:
        dbg(f"label: write error {e}")
        sys.print_exception(e)
        ok = False
    if not ok:
        dbg("label: write FAILED")
        return False
    time.sleep_ms(STEP_PAUSE_MS)
    back, uid3 = read_ndef_text(nfc, timeout=300)
    dbg(f"label: read back {back!r} (read uid {uid3})")
    if not (back and back.strip() == want.lower()):
        dbg("label: read back does NOT match")
        return False
    return True


# ── main loop ──────────────────────────────────────────────────────────

dbg(f"SplatTagWriter start: PN532 {nfc.begin()} hub={HUB_CONFIG.get('name', '?')} free={gc.mem_free()}")
bound_retries()
cycle = 0
while True:
    cycle += 1
    dbg(f"── cycle {cycle} ──")
    mac = listen()
    if mac is None:
        time.sleep_ms(PAUSE_MS)
        continue
    dbg(f"Splat {mac}: hold its sticker on the wand")
    leds.show_shape(SHAPE_STAR, BLUE)
    buz.beep(1200, 80)
    result = label(mac)
    release()
    if result:
        done.add(mac)
        dbg(f"DONE {mac}  ({len(done)} this session: {sorted(done)})")
        leds.show_shape(SHAPE_CHECK, GREEN)
        buz.beep(1800, 80)
        time.sleep_ms(120)
        buz.beep(1800, 80)
    else:
        dbg(f"FAILED {mac}")
        leds.show_shape(SHAPE_X, RED)
        buz.beep(300, 300)
    time.sleep_ms(DONE_PAUSE_MS)
