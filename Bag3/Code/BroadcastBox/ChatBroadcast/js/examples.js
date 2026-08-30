/** Compact starter payloads for the 6-arg play() contract (payload.py). */

const JUMPIN_CODE = `"""
Jump In — shake to light the wand
=================================
Shake the wand to fill the LED matrix with color. Press the button to reset.
Tap a stop tag to exit.
"""

import time
import math
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK

_EXIT_TAGS = exit_tags_excluding("jumpin")
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 50
BUTTON_PIN = 0
SHAKE_THRESHOLD = 1.4
PICK = [RED, GREEN, BLUE, YELLOW, PURPLE, PINK]


class JumpInGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.level = 0
        self.color = RED

    def _check_stop(self):
        msg_type, _, _ = self.enow.poll()
        if msg_type in ("stop", "start_game"):
            return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def _check_button(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self.level = 0
                self.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def run(self):
        while True:
            if self._check_stop():
                return
            if self._check_button():
                pass
            elif self.accel:
                try:
                    x, y, z = self.accel.read()
                    mag = math.sqrt(x * x + y * y + z * z)
                    if mag > SHAKE_THRESHOLD:
                        self.level = min(25, self.level + 1)
                        self.color = PICK[self.level % len(PICK)]
                        self.leds.fill(self.color)
                        self.buz.beep(600, 40)
                except Exception:
                    pass
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(659, 80)
    try:
        JumpInGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

const JUMP_CODE = `"""
Jump Counter — freefall jump detection
======================================
Each jump lights one more LED. Press the button to reset. Tap stop to exit.
"""

import time
import math
import random
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK

_EXIT_TAGS = exit_tags_excluding("jump")
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40
BUTTON_PIN = 0
NUM_LEDS = 25
FREEFALL_THRESHOLD = 0.3
MIN_EVENT_SPACING = 1000
PICK_COLORS = [RED, GREEN, BLUE, YELLOW, PURPLE, PINK]


class JumpGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.level = 0
        self.in_jump = False
        self.last_jump_time = 0
        self.color = random.choice(PICK_COLORS)
        self.leds.off()

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def _check_button_reset(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self.level = 0
                self.in_jump = False
                self.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def _update_jumps(self):
        if self.accel is None:
            return
        try:
            x, y, z = self.accel.read()
            magnitude = math.sqrt(x * x + y * y + z * z)
            now = time.ticks_ms()
            if magnitude < FREEFALL_THRESHOLD:
                if not self.in_jump:
                    if time.ticks_diff(now, self.last_jump_time) > MIN_EVENT_SPACING:
                        self.level += 1
                        self.last_jump_time = now
                        self.in_jump = True
            else:
                self.in_jump = False
        except Exception:
            pass

    def _render_level(self, level):
        self.leds.off()
        n = min(level, NUM_LEDS)
        for i in range(n):
            row = 4 - (i // 5)
            col = i % 5
            self.leds.np[row * 5 + col] = self.color
        self.leds.np.write()

    def run(self):
        while True:
            if self._check_stop():
                return
            if not self._check_button_reset():
                self._update_jumps()
            self._render_level(self.level)
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(659, 80)
    time.sleep_ms(40)
    buz.beep(784, 120)
    try:
        JumpGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

const SHAKE_RAINBOW_CODE = `"""
Shake Rainbow — climb through rainbow colors
============================================
Shake harder to unlock higher colors. Press the button to reset.
"""

import time
import math
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK

_EXIT_TAGS = exit_tags_excluding("shakerainbow")
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40
BUTTON_PIN = 0
SHAKE_COLOR_RANGE = [WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK]
SHAKE_THRESHOLD = 0.15
ACC_MAX = 10.0


class ShakeRainbowGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.current_level = 0
        self.current_color = SHAKE_COLOR_RANGE[0]
        self.leds.off()

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def _accel_mag(self):
        if self.accel is None:
            return 0
        try:
            x, y, z = self.accel.read()
            return math.sqrt(x * x + y * y + z * z) - 1
        except Exception:
            return 0

    def _check_button_reset(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self.current_level = 0
                self.current_color = SHAKE_COLOR_RANGE[0]
                self.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def run(self):
        while True:
            if self._check_stop():
                return
            if not self._check_button_reset():
                acc_raw = self._accel_mag()
                if acc_raw > SHAKE_THRESHOLD:
                    acc = (acc_raw ** 2) * 1.5
                    if acc > ACC_MAX:
                        acc = ACC_MAX
                    if acc < 0:
                        acc = 0
                    n = len(SHAKE_COLOR_RANGE)
                    level = int((acc / ACC_MAX) * (n - 1))
                    if level > self.current_level:
                        self.current_level = level
                        self.current_color = SHAKE_COLOR_RANGE[level]
            self.leds.fill(self.current_color)
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(659, 80)
    try:
        ShakeRainbowGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

const MELODY_CODE = `"""
Melody — tap note tags to build a tune
======================================
Needs 8 note NFC tags. Button plays back. Erase tag clears. Stop exits.
"""

import time
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, WHITE

_EXIT_TAGS = exit_tags_excluding("melody")
NOTE_TAGS = {
    "note_c": (262, RED),
    "note_d": (294, ORANGE),
    "note_e": (330, YELLOW),
    "note_f": (349, GREEN),
    "note_g": (392, BLUE),
    "note_a": (440, PURPLE),
    "note_b": (494, PINK),
    "note_c_high": (523, WHITE),
}
COMMANDS = _EXIT_TAGS | set(NOTE_TAGS.keys()) | {"erase", "backspace"}
NFC_POLL_INTERVAL = 4
LOOP_DELAY_MS = 40
BUTTON_PIN = 0
MAX_NOTES = 25


class MelodyGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.notes = []
        self.leds.off()

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        return False

    def _check_button_play(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                for freq, color in self.notes:
                    self.leds.fill(color)
                    self.buz.beep(freq, 180)
                    time.sleep_ms(40)
                self.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def _poll_nfc(self):
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
        except Exception:
            return False
        if cmd in _EXIT_TAGS:
            return True
        if cmd in ("erase", "backspace"):
            self.notes = []
            self.leds.off()
            self.buz.beep(200, 80)
            return False
        if cmd in NOTE_TAGS:
            freq, color = NOTE_TAGS[cmd]
            if len(self.notes) < MAX_NOTES:
                self.notes.append((freq, color))
            self.leds.fill(color)
            self.buz.beep(freq, 160)
            time.sleep_ms(40)
            self.leds.off()
        return False

    def run(self):
        while True:
            if self._check_stop():
                return
            self._check_button_play()
            if self._poll_nfc():
                return
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(659, 80)
    try:
        MelodyGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

const RAINBOW_CODE = `"""
Rainbow — shake for color
=========================
Shake the wand to cycle through rainbow fills. Button resets to white.
"""

import time
import math
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK

_EXIT_TAGS = exit_tags_excluding("rainbow")
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40
BUTTON_PIN = 0
COLORS = [WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK]
SHAKE_THRESHOLD = 1.5


class RainbowGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.idx = 0
        self.leds.fill(COLORS[0])

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def _check_button(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self.idx = 0
                self.leds.fill(COLORS[0])
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def run(self):
        while True:
            if self._check_stop():
                return
            if self._check_button():
                pass
            elif self.accel:
                try:
                    x, y, z = self.accel.read()
                    mag = math.sqrt(x * x + y * y + z * z)
                    if mag > SHAKE_THRESHOLD:
                        self.idx = (self.idx + 1) % len(COLORS)
                        self.leds.fill(COLORS[self.idx])
                        self.buz.beep(400 + self.idx * 40, 50)
                        time.sleep_ms(200)
                except Exception:
                    pass
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 60)
    try:
        RainbowGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

const FREEZE_CODE = `"""
Freeze Dance — move, then freeze
================================
Shake while the music "plays" (LEDs animate). When LEDs go white, freeze!
"""

import time
import math
import random
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import PURPLE, WHITE, RED, GREEN

_EXIT_TAGS = exit_tags_excluding("freezedance")
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 50
BUTTON_PIN = 0
SHAKE_THRESHOLD = 1.35


class FreezeDanceGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._frame = 0
        self.frozen = False
        self.until = time.ticks_ms() + random.randint(3000, 6000)

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def run(self):
        while True:
            if self._check_stop():
                return
            now = time.ticks_ms()
            if time.ticks_diff(now, self.until) >= 0:
                self.frozen = not self.frozen
                self.until = now + (2000 if self.frozen else random.randint(3000, 7000))
                if self.frozen:
                    self.leds.fill(WHITE)
                    self.buz.beep(200, 120)
                else:
                    self.buz.beep(600, 80)

            if self.frozen:
                if self.accel:
                    try:
                        x, y, z = self.accel.read()
                        mag = math.sqrt(x * x + y * y + z * z)
                        if mag > SHAKE_THRESHOLD:
                            self.leds.fill(RED)
                            self.buz.beep(150, 200)
                    except Exception:
                        pass
            else:
                self.leds.fill(PURPLE if (self._frame // 4) % 2 == 0 else GREEN)

            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    try:
        FreezeDanceGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

const COOKING_CODE = `"""
Cooking — recipe steps with ingredient tags
===========================================
Tap ingredient tags in order. Wrong order gets a buzz. Button restarts.
"""

import time
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, GREEN, YELLOW, ORANGE, BLUE

_EXIT_TAGS = exit_tags_excluding("cooking")
RECIPE = ["flour", "egg", "milk", "butter", "sugar"]
COMMANDS = _EXIT_TAGS | set(RECIPE)
NFC_POLL_INTERVAL = 4
LOOP_DELAY_MS = 40
BUTTON_PIN = 0
COLORS = [YELLOW, ORANGE, BLUE, GREEN, RED]


class CookingGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.step = 0
        self.leds.fill(COLORS[0])

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        return False

    def _check_button(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self.step = 0
                self.leds.fill(COLORS[0])
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def _poll_nfc(self):
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
        except Exception:
            return False
        if cmd in _EXIT_TAGS:
            return True
        if cmd in RECIPE:
            if cmd == RECIPE[self.step]:
                self.buz.beep(700, 80)
                self.step += 1
                if self.step >= len(RECIPE):
                    self.leds.fill(GREEN)
                    self.buz.beep(880, 200)
                    time.sleep_ms(400)
                    self.step = 0
                self.leds.fill(COLORS[self.step % len(COLORS)])
            else:
                self.leds.fill(RED)
                self.buz.beep(180, 200)
                time.sleep_ms(200)
                self.leds.fill(COLORS[self.step % len(COLORS)])
        return False

    def run(self):
        while True:
            if self._check_stop():
                return
            self._check_button()
            if self._poll_nfc():
                return
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    try:
        CookingGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
`;

export const EXAMPLES = [
    {
        id: "melody",
        name: "Melody",
        emoji: "🎵",
        category: "sound",
        description: "Tap each note-tag to play a tune.",
        tagNote: "8 NFC tags",
        tags: ["note_c", "note_d", "note_e", "note_f", "note_g", "note_a", "note_b", "note_c_high"],
        starterPrompt: "Start from the Melody example — one tag per note.",
        startingCode: MELODY_CODE,
    },
    {
        id: "freezedance",
        name: "Freeze Dance",
        emoji: "❄️",
        category: "color",
        description: "Move, then freeze when the music stops.",
        tagNote: null,
        tags: ["freezedance"],
        starterPrompt: "Start from Freeze Dance — move and freeze game.",
        startingCode: FREEZE_CODE,
    },
    {
        id: "rainbow",
        name: "Rainbow",
        emoji: "🌈",
        category: "color",
        description: "Shake for color.",
        tagNote: null,
        tags: ["rainbow"],
        starterPrompt: "Start from Rainbow — shake for color.",
        startingCode: RAINBOW_CODE,
    },
    {
        id: "shakerainbow",
        name: "Shake Rainbow",
        emoji: "🌈",
        category: "color",
        description: "Shake harder to climb through rainbow colors.",
        tagNote: null,
        tags: ["shakerainbow"],
        starterPrompt: "Start from Shake Rainbow — sticky high-score shake colors.",
        startingCode: SHAKE_RAINBOW_CODE,
    },
    {
        id: "jump",
        name: "Jump",
        emoji: "⬆️",
        category: "color",
        description: "Jump (freefall) to light more LEDs on the matrix.",
        tagNote: null,
        tags: ["jump"],
        starterPrompt: "Start from Jump — freefall jump counter on the LEDs.",
        startingCode: JUMP_CODE,
    },
    {
        id: "cooking",
        name: "Cooking",
        emoji: "🍳",
        category: "multi",
        description: "Recipe steps with ingredient tags.",
        tagNote: "Multi-tag",
        tags: ["flour", "egg", "milk", "butter", "sugar"],
        starterPrompt: "Start from Cooking — recipe steps game.",
        startingCode: COOKING_CODE,
    },
    {
        id: "jumpin",
        name: "Jump In",
        emoji: "🦘",
        category: "color",
        description: "Simple jump game — great first project.",
        tagNote: null,
        tags: ["jumpin"],
        starterPrompt: "Make a simple jump game where shaking makes the wand light up.",
        startingCode: JUMPIN_CODE,
    },
];

export const CATEGORIES = [
    { id: "all", label: "All" },
    { id: "sound", label: "🎵 Sound" },
    { id: "color", label: "🎨 Color" },
    { id: "multi", label: "🏷️ Multi-tag" },
];

export function findExample(id) {
    return EXAMPLES.find((e) => e.id === id);
}
