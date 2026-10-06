"""
Virtual NFC tag demo: XIAO ESP32-C6 + NFC Tag 2 Click (NT3H2111) + OLED.

The tag is a programmable mailbox. Every few seconds the C6 deals a creature
card and writes it into the tag over I2C, reads it back, and shows it on the
OLED. When a phone or reader taps the tag the demo notices the RF field and
the NDEF-read flag, counts it as a delivery, and reprograms the tag with the
next card. BOOT button (GPIO9) deals the next card immediately.
"""

import time
import random
from machine import Pin, SoftI2C

import ssd1306
from nt3h import NT3H
import ndef

I2C_SDA = 22
I2C_SCL = 23
BUTTON_PIN = 9
CARD_SECS = 8
SENT_HOLD_MS = 2500

CARDS = [
    ("fox",   [" /\\_/\\  ", "( o.o ) ", " > ^ <  "]),
    ("owl",   [" {o,o}  ", " /)_)   ", '  " "   ']),
    ("frog",  ["  @..@  ", " (----) ", "( >__< )"]),
    ("snail", ["   @/    ", " __/ \\_  ", "(______) "]),
    ("bat",   ["/\\ ^_^ /\\", " \\|   |/ ", "  v   v  "]),
    ("fish",  [" ><(((o>", "  ~~~~  ", " ~~  ~~ "]),
]

i2c = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, 0x3C)
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
tag = NT3H(i2c)


def shuffle(items):
    for i in range(len(items) - 1, 0, -1):
        j = random.getrandbits(8) % (i + 1)
        items[i], items[j] = items[j], items[i]


def centered(text, y):
    oled.text(text, max(0, (128 - len(text) * 8) // 2), y)


def draw(card, status, secs_left, taps, sent, field, tick):
    oled.fill(0)
    centered("VIRTUAL TAG", 0)
    oled.hline(0, 9, 128, 1)
    if card:
        for n, line in enumerate(card[1]):
            centered(line, 14 + n * 9)
        centered(card[0].upper(), 42)
    centered(status, 52)
    oled.text(f"tap{taps}", 0, 56)
    oled.text(f"out{sent}", 88, 56)
    # countdown bar
    w = int(128 * secs_left / CARD_SECS)
    oled.fill_rect(0, 62, w, 2, 1)
    # radio waves when a reader field is present
    if field:
        r = 4 + (tick % 4) * 4
        oled.ellipse(120, 24, r, r, 1)
        oled.ellipse(8, 24, r, r, 1)
    oled.show()


def program(card):
    """Write the card into the tag and verify by reading it back over I2C."""
    ok = tag.write_ndef(ndef.build_ndef_text(card[0]))
    back = ndef.decode_ndef_text(tag.read_tlv_area(1))
    return ok and back == card[0]


def main():
    if not tag.present():
        oled.fill(0)
        centered("NT3H missing", 24)
        oled.show()
        return
    print("cc", tag.read_cc().hex(), "uid", tag.read_uid().hex())

    deck = list(range(len(CARDS)))
    shuffle(deck)
    pos = 0
    card = None
    status = ""
    taps = 0
    sent = 0
    field_prev = False
    read_seen = False
    next_at = 0
    hold_until = 0
    last_poll = 0
    tick = 0
    btn_prev = 1

    while True:
        now = time.ticks_ms()
        btn = button.value()
        skip = btn == 0 and btn_prev == 1
        btn_prev = btn

        if card is None or skip or time.ticks_diff(now, next_at) >= 0:
            if time.ticks_diff(now, hold_until) >= 0 or skip:
                card = CARDS[deck[pos % len(deck)]]
                pos += 1
                if pos % len(deck) == 0:
                    shuffle(deck)
                status = "writing..."
                draw(card, status, CARD_SECS, taps, sent, False, tick)
                try:
                    ok = program(card)
                except OSError:
                    ok = False
                status = "ready: tap me" if ok else "write failed"
                print("card", card[0], "ok" if ok else "FAIL")
                read_seen = False
                next_at = time.ticks_add(time.ticks_ms(), CARD_SECS * 1000)

        if time.ticks_diff(now, last_poll) >= 100:
            last_poll = now
            tick += 1
            try:
                ns = tag.ns_reg()
            except OSError:
                ns = 0
            field = bool(ns & NT3H.NS_RF_FIELD_PRESENT)
            read = bool(ns & NT3H.NS_NDEF_DATA_READ)
            if field and not field_prev:
                taps += 1
                status = "reader nearby!"
                print("field on, ns", hex(ns))
            if read and not read_seen:
                read_seen = True
                sent += 1
                status = f"sent {card[0]}!"
                print("delivered", card[0], "ns", hex(ns))
                hold_until = time.ticks_add(now, SENT_HOLD_MS)
                next_at = hold_until
            field_prev = field
            left = max(0, time.ticks_diff(next_at, now)) / 1000
            draw(card, status, min(left, CARD_SECS), taps, sent, field, tick)

        time.sleep_ms(1)


main()
