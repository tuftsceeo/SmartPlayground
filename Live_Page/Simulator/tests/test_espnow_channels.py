"""
Tests that ESP-NOW traffic and real failures travel on separate channels.

espnow_manager reports every send through sim_state; before these channels
were split, that shared the one callback the host treated as a crash, so a
freeze_dance caller's every broadcast surfaced as an error in the UI.

Imports are inside the tests: the `runtime` fixture is what puts py/ and its
shims on sys.path.
"""

from __future__ import annotations


def _capture(sim_state):
    """(logs, errors, sends), wired to the three callbacks."""
    logs, errors, sends = [], [], []
    sim_state.set_log_callback(logs.append)
    sim_state.set_error_callback(errors.append)
    sim_state.set_enow_sent_callback(lambda k, d, m: sends.append((k, d, m)))
    return logs, errors, sends


def test_espnow_send_is_not_an_error(runtime):
    """A broadcast is routine traffic: it reports as a send and leaves a log
    line, but never reaches the error channel."""
    import sim_state
    from espnow_manager import ESPNowManager

    logs, errors, sends = _capture(sim_state)
    ESPNowManager().send_raw("ff:ff:ff:ff:ff:ff", b"FD_GO")

    assert sends == [("raw", "FD_GO", "ff:ff:ff:ff:ff:ff")]
    assert errors == []
    assert logs, "a send should still leave a trace in the log"


def test_error_channel_is_separate(runtime):
    """emit_error reaches only the error callback."""
    import sim_state

    logs, errors, sends = _capture(sim_state)
    sim_state.emit_error("ValueError: boom")

    assert errors == ["ValueError: boom"]
    assert logs == []
    assert sends == []


def test_enow_round_trip_carries_bytes(runtime):
    """A queued raw message keeps its bytes payload — what freeze_dance.py
    compares against its MSG_* constants, and why the panel sends a Python
    bytes literal rather than a str."""
    import sim_state

    _capture(sim_state)
    sim_state.enow_queue.clear()
    sim_state.enqueue_enow("raw", b"FD_FREEZE")

    msg_type, data, _mac = sim_state.dequeue_enow()
    assert msg_type == "raw"
    assert data == b"FD_FREEZE"
