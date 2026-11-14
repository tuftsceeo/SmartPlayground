"""Tests for sync_game_tags (run with pytest)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_game_tags as sgt


def sets(game, control=("start", "stop"), hidden=("finddevice",)):
    return {"GAME_TAGS": set(game), "CONTROL_TAGS": set(control), "HIDDEN_TAGS": set(hidden)}


def test_identical_has_no_differences():
    assert sgt.compare_py(sets({"a"}), sets({"a"}), set(), set()) == ([], [])


def test_allowed_extra_and_missing_are_separated():
    src = sets({"a", "splatecho"})
    copy = sets({"a"}, control=("start", "stop", "unpair"))
    errors, allowed = sgt.compare_py(src, copy, {"unpair"}, {"splatecho"})
    assert errors == []
    assert sorted(allowed) == ["CONTROL_TAGS: extra 'unpair'", "GAME_TAGS: missing 'splatecho'"]


def test_unallowed_difference_is_error():
    errors, _ = sgt.compare_py(sets({"a", "b"}), sets({"a", "c"}), set(), set())
    assert errors == ["GAME_TAGS: extra 'c'", "GAME_TAGS: missing 'b'"]


def test_live_files_parse():
    assert "splatecho" in sgt.read_tag_sets(sgt.SOURCE)["GAME_TAGS"]
    assert "stop" in sgt.read_wand_reserved(sgt.GAME_NAME_JS)
    assert isinstance(sgt.run(out=lambda s: None), int)
