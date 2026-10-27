"""
Tests for Runtime.get_capabilities() (task 4): the button/motion table
lookup, the live nfcTags/battery derivation, and the motion default for a
game with no table entry (every generated game).
"""

from __future__ import annotations

import pytest

# (name, expected nfcTags, expected battery)
_EXPECTED = [
    ("jump", [], False),
    ("shake", [], False),
    ("shake_rainbow", [], False),
    ("sound", [], False),
    ("rainbow", [], True),
    ("jumpin", [], False),
    # Underscored names so one physical note card serves both nfc_sound and
    # melody; nfc_sound maps them to its NOTE_FREQ keys by stripping the "_".
    (
        "nfc_sound",
        ["note_a", "note_b", "note_c", "note_c_high", "note_d", "note_e", "note_f", "note_g"],
        False,
    ),
    ("gestures", ["blue", "green", "play", "red"], False),
    ("simpleicecream", [], False),
    (
        "melody",
        [
            "backspace", "double_length", "erase", "halve_length", "melody",
            "note_a", "note_b", "note_c", "note_c_high",
            "note_d", "note_e", "note_f", "note_g", "rest",
        ],
        False,
    ),
    ("cooking", ["butter", "cheese", "cooking", "egg", "flour", "milk", "sugar", "tomato"], False),
    ("multiicecream", [], False),
    # freeze_dance.py is the one game that calls its tag set GAME_COMMANDS
    # rather than COMMANDS, so this row is also what guards get_capabilities()
    # reading the alias — without it the game's whole role-select step
    # (caller / player) would show no tags.
    ("freeze_dance", ["caller", "freeze", "go", "player", "rejoin"], False),
]


@pytest.mark.parametrize("name,expected_tags,expected_battery", _EXPECTED)
def test_capabilities_nfc_tags_and_battery(runtime, name, expected_tags, expected_battery):
    """nfcTags = game-specific commands (COMMANDS minus exit tags, plus the
    game's own tag if it re-added it for an in-game control like melody's
    "melody"/erase or cooking's "cooking"/clear). battery = whether play()
    actually reads its `batt` parameter — every game declares it, so only
    rainbow, which uses it, is true."""
    rt = runtime
    rt.load_game(name)
    caps = rt.get_capabilities()
    assert sorted(caps["nfcTags"]) == expected_tags
    assert caps["battery"] is expected_battery
    assert caps["buzzer"] is True


def test_capabilities_known_games_have_button(runtime):
    """Every vendored game has a curated table entry naming its button kind
    — not derivable from source, so this guards against a name silently
    falling out of _TEACHER_TABLE."""
    rt = runtime
    for name in [n for n, _, _ in _EXPECTED]:
        rt.load_game(name)
        caps = rt.get_capabilities()
        assert caps["button"] in ("tap", "hold", "none")


def test_capabilities_no_table_entry_without_accel_shows_no_motion(runtime):
    """A game name with no _TEACHER_TABLE entry (every generated game) whose
    code never reads the accelerometer gets no motion controls. Declaring
    accel as a play() parameter does not count as reading it. Loading via
    raw source names the module "custom", which is absent from the table."""
    rt = runtime
    rt.load_game(
        "from game_tags import exit_tags_excluding\n"
        '_EXIT_TAGS = exit_tags_excluding("jumpin")\n'
        'COMMANDS = _EXIT_TAGS | {"go_for_it"}\n'
        "async def play(nfc, leds, buz, accel, i2c, enow):\n"
        "    pass\n"
    )
    caps = rt.get_capabilities()
    assert caps["button"] == "tap"
    assert caps["motion"] == []
    # nfcTags is still live-derived even with no table entry.
    assert caps["nfcTags"] == ["go_for_it"]


def test_capabilities_no_table_entry_with_accel_shows_everything(runtime):
    """A game with no table entry that reads the accelerometer gets every
    pose/gesture."""
    rt = runtime
    rt.load_game(
        "async def play(nfc, leds, buz, accel, i2c, enow):\n"
        "    x, y, z = accel.read()\n"
    )
    caps = rt.get_capabilities()
    assert set(caps["motion"]) == {
        "tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down",
        "jump", "shake", "flip",
    }


def test_capabilities_before_load_shows_everything(runtime):
    """Querying capabilities with no game loaded yet must not raise."""
    caps = runtime.get_capabilities()
    assert caps["motion"]
    assert caps["nfcTags"] == []


@pytest.mark.parametrize("body", [
    "async def play(nfc, leds, buz, acc, i2c, enow):\n    x, y, z = acc.read()\n",
    "async def play(*args):\n    pass\n",
    "import hubtype\nasync def play(nfc, leds, buz, accel, i2c, enow):\n"
    "    p = hubtype.HUB_CONFIG['accel_int1_pin']\n",
    "from lis2dw12 import LIS2DW12\nasync def play(nfc, leds, buz, a, i2c, enow):\n    pass\n",
])
def test_capabilities_accel_reached_other_ways(runtime, body):
    """A renamed fourth parameter, *args, the INT1 pin and the driver import
    all count as reading the accelerometer."""
    runtime.load_game(body)
    assert runtime.get_capabilities()["motion"]
