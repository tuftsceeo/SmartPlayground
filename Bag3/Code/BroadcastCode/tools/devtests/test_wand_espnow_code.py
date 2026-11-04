"""CPython test: stock MockWand/lib/espnow_code.py against the code senders.

Loads the stock wand's copy of the receiver in place of MockWandEUM's and
runs the EspnowModem/tests/test_code_xfer.py suite against
EspnowModem/host/code_sender.py, then a host-pinned pull against the Dial's
code_link (the getcode card's "@<id>").

Run: python3 tools/devtests/test_wand_espnow_code.py
"""

import importlib.util
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BC = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(BC, "..", "Experiments", "EspnowModem", "tests"))

import test_code_xfer as T  # noqa: E402  (stubs, Air, FakeMgr, tests)

spec = importlib.util.spec_from_file_location(
    "espnow_code", os.path.join(BC, "..", "Wand Module", "lib", "espnow_code.py"))
wand_code = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wand_code)
assert "MockWand/lib" in wand_code.__file__.replace(os.sep, "/")
assert "MockWandEUM" not in wand_code.__file__
sys.modules["espnow_code"] = wand_code
T.espnow_code = wand_code


def _fast(mod):
    mod.GET_WAIT_MS = 60
    mod.OFFER_WAIT_MS = 150
    mod.REQ_JITTER_MS = 30


def run_xfer_suite():
    _fast(wand_code)
    T.code_sender.BUSY_RETRY_MS = 100
    ctx = T.setup()
    tests = [T.test_clean_big_file, T.test_lossy_link,
             T.test_old_game_kept_as_bak, T.test_refusals, T.test_no_host,
             T.test_broken_file_rejected_old_kept, T.test_corruption_detected,
             T.test_active_slug, T.test_many_wands_concurrent_with_busy,
             T.test_peer_table_never_fills, T.test_busy_gives_up_after_budget,
             T.test_display_pull_with_icons, T.test_offer_icons_list_fits_frame,
             T.test_icon_failure_keeps_game, T.test_icon_file_refusals]
    for fn in tests:
        fn(ctx)
        print("ok   xfer:", fn.__name__)
    ctx[4].stop = True
    shutil.rmtree(ctx[0])
    return len(tests)


def run_dial_pinned():
    import test_dial_code_link as D
    D.espnow_code = wand_code
    ctx = D.setup()
    tests = [D.test_arm_refused_without_game, D.test_resolve_reads_active,
             D.test_serve_transfer_events_and_stats,
             D.test_refusal_is_not_a_pull, D.test_idle_session_reports_fail,
             D.test_pinned_request_for_other_host_ignored]
    for fn in tests:
        fn(ctx)
        print("ok   dial:", fn.__name__)
    shutil.rmtree(ctx[0])
    return len(tests)


if __name__ == "__main__":
    n = run_xfer_suite()
    n += run_dial_pinned()
    print("%d passed (receiver: MockWand/lib/espnow_code.py)" % n)
