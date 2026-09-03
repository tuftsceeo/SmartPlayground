"""
Tests for Runtime.get_capabilities() (task 4): the button/motion table
lookup, the live nfcTags/battery derivation, and the "no entry -> show
everything" fallback a freshly generated jumpin.py depends on.
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
    ("nfc_sound", ["notea", "noteb", "notec", "noted", "notee", "notef", "noteg"], False),
    ("gestures", ["blue", "green", "play", "red"], False),
    ("simpleicecream", [], False),
    (
        "melody",
        [
            "backspace", "erase", "melody",
            "note_a", "note_b", "note_c", "note_c_high",
            "note_d", "note_e", "note_f", "note_g",
        ],
        False,
    ),
    ("cooking", ["butter", "cheese", "cooking", "egg", "flour", "milk", "sugar", "tomato"], False),
    ("multiicecream", [], False),
]


@pytest.mark.parametrize("name,expected_tags,expected_battery", _EXPECTED)
def test_capabilities_nfc_tags_and_battery(runtime, name, expected_tags, expected_battery):
    """nfcTags = game-specific commands (COMMANDS minus exit tags, plus the
    game's own tag if it re-added it for an in-game control like melody's
    "melody"/erase or cooking's "cooking"/clear). battery = whether play()
    takes a `batt` kwarg — true only for rainbow."""
    rt = runtime
    rt.load_game(name)
    caps = rt.get_capabilities()
    assert sorted(caps["nfcTags"]) == expected_tags
    assert caps["battery"] is expected_battery
    assert caps["buzzer"] is True


def test_capabilities_known_games_have_button_and_hint(runtime):
    """Every vendored game has a curated table entry (button kind + a
    one-line hint) — these aren't derivable from source, so this just
    guards against a name silently falling out of _TEACHER_TABLE."""
    rt = runtime
    for name in [n for n, _, _ in _EXPECTED]:
        rt.load_game(name)
        caps = rt.get_capabilities()
        assert caps["button"] in ("tap", "hold", "none")
        assert caps["hint"], "%s has no how-to-play hint" % name


def test_capabilities_no_table_entry_shows_everything(runtime):
    """The important path: a game name with no _TEACHER_TABLE entry (e.g. a
    freshly generated jumpin.py before anyone hand-writes its copy) must
    degrade to every pose/gesture rather than an empty panel. Loading via
    raw source (as the sim's dev "custom source" path does) names the
    module "custom", which is guaranteed absent from the table."""
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
    assert set(caps["motion"]) == {
        "tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down",
        "jump", "shake", "flip",
    }
    # nfcTags is still live-derived even with no table entry.
    assert caps["nfcTags"] == ["go_for_it"]


def test_capabilities_before_load_shows_everything(runtime):
    """Querying capabilities with no game loaded yet must not raise."""
    caps = runtime.get_capabilities()
    assert caps["motion"]
    assert caps["nfcTags"] == []
