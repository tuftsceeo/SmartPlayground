"""
3c_two_links.py -- why does a second Splat connection drop the first?
=====================================================================
Run on the hub: mpremote connect $HUB resume run bench/3c_two_links.py
Needs on the hub: the stage-3 files (bench/README.md). BOTH Splats on,
not connected to a phone or web app. /main.py moved aside.

Hardware so far (docs_and_design/2026-09-29-splat-hub-logs/): one Splat
holds, with or without a 20% duty scan beside it; with two, starting the
second connection loses the first ~0.1 s later, every time. Hypotheses:

  H1 connecting starves the live link: while a connection is being
     initiated the radio listens continuously (MicroPython fixes the
     initiator duty), the live link misses its events and hits its
     supervision timeout. Evidence: a real IRQ disconnect for the live
     handle, shortly after the other link's INITIATE and before its
     connect completes; short supervision timeout in the conn updates;
     short connect bursts with gaps hold both.
  H2 connection limit (controller or build allows one central link).
     Evidence: the loss follows the other link's CONNECT completion, not
     its initiation; bursts that never complete never drop the live link.
  H3 hub software: link state reset without a radio disconnect.
     Evidence: no IRQ disconnect for the handle before the loss, and a
     write on the old handle still succeeds after it.

Splat side (user, 2026-09-29): after the hub reports a link lost, the
Splat often stays in its connected state (no lights) for minutes, then a
connected sleep (rare blue breathing), and does not advertise until it
gives up or is power-cycled. Both ends share one supervision timeout, so
a real radio timeout should free the Splat too; a Splat that stays
connected points to H3 (the link is alive and only the hub's state was
reset) or to Splat firmware not enforcing the timeout. The write probe
separates the two on the hub side.

IRQ 29/30 (_IRQ_GET_SECRET / _IRQ_SET_SECRET): the stack reading/writing
its key store. In 07_bench_3c_1438e68.txt they appear once per variant at
hub start-up, before any connect completes -- most likely the stack's own
local identity key, not the Splat requesting pairing. Nothing here stores
them (the handler returns None). Bag2's Splat code never pairs, and one
unpaired Splat held on this hub (stage 3), so pairing is not assumed to be
required; if a verdict stays unclear, a gap_pair() test is the next step.

Per variant it logs, with times: every INITIATE (gap_connect call), every
BLE IRQ (connect, disconnect, conn-parameter update, notify counts per
handle), every link state reset with the last IRQ seen, and, on each loss,
a write probe on the old handle. It ends each variant with a SUMMARY and a
per-loss table, and the run with VERDICT lines.
"""

import gc
import os
import sys
import time
import ubluetooth

ubluetooth.BLE().active(True)

import splat_link
from splat_hub import SplatHub
from splat_api import SplatGroup

RUN_S = 12
# (label, interval_us (min, max) or None, DIRECT_CONNECT_MS, DIRECT_RETRY_GAP_MS)
VARIANTS = (
    ("default", None, 10000, 0),
    ("long-interval", (100000, 200000), 10000, 0),
    ("short-bursts", None, 400, 600),
)

_T0 = time.ticks_ms()


def _t():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def _addr(a):
    return ':'.join(['%02X' % b for b in a])


print("3c: firmware %s | %s" % (os.uname().release, os.uname().machine))
print("3c: gc_free %d" % gc.mem_free())


def run(label, interval, direct_ms, gap_ms):
    splat_link.CONN_INTERVAL_US = interval
    splat_link.DIRECT_CONNECT_MS = direct_ms
    splat_link.DIRECT_RETRY_GAP_MS = gap_ms
    hub = SplatHub(2)
    links = hub.links
    route = hub._irq
    events = []          # (t, kind, handle, addr)
    updates = []
    notifies = {}
    last_irq = ["none"]
    initiates = []       # (t, unit, mac)
    losses = []          # dicts

    def unit_of_handle(h):
        for i, l in enumerate(links):
            if l._conn_handle == h:
                return i
        return None

    def spy(event, data):
        t = _t()
        if event == 7:
            events.append((t, "connect", data[0], _addr(data[2])))
            print("[%6.2f] IRQ connect      handle=%d %s" % (t, data[0], _addr(data[2])))
        elif event == 8:
            events.append((t, "disconnect", data[0], _addr(data[2])))
            print("[%6.2f] IRQ disconnect   handle=%d %s (unit %s)"
                  % (t, data[0], _addr(data[2]), unit_of_handle(data[0])))
        elif event == 27:
            h, itvl, lat, sup, st = data
            updates.append((t, h, itvl, lat, sup, st))
            print("[%6.2f] IRQ conn update  handle=%d interval=%.1f ms latency=%d "
                  "supervision=%d ms status=%d" % (t, h, itvl * 1.25, lat, sup * 10, st))
        elif event == 18:
            notifies[data[0]] = notifies.get(data[0], 0) + 1
        elif event not in (5, 6, 9, 10, 11, 12, 17):
            print("[%6.2f] IRQ event %d %r" % (t, event, data))
        last_irq[0] = "%d@%.2f" % (event, t)
        route(event, data)

    for i, link in enumerate(links):
        def make_cd(link=link, i=i):
            orig = link.connect_direct

            # MicroPython passes the instance to a function stored on it
            # (CPython does not), so accept and drop a leading link.
            def cd(*a):
                if a and a[0] is link:
                    a = a[1:]
                timeout_ms = a[0] if len(a) > 0 else 10000
                interval_us = a[1] if len(a) > 1 else None
                initiates.append((_t(), i, link.mac_address))
                print("[%6.2f] INITIATE unit %d -> %s timeout=%d ms interval=%s"
                      % (_t(), i, link.mac_address, timeout_ms, interval_us))
                return orig(timeout_ms, interval_us)
            return cd
        link.connect_direct = make_cd()

        def make_reset(link=link, i=i):
            orig = link._reset_connection_state

            def reset(*a):
                if link.connected:
                    print("[%6.2f] RESET unit %d while connected (handle=%s, last IRQ %s)"
                          % (_t(), i, link._conn_handle, last_irq[0]))
                orig()
            return reset
        link._reset_connection_state = make_reset()

    hub._ble.irq(spy)
    splat = SplatGroup(hub)
    print("[%6.2f] === variant %s: interval=%s direct_ms=%d gap_ms=%d"
          % (_t(), label, interval, direct_ms, gap_ms))
    was = [False, False]
    handle = [None, None]
    tx = [None, None]
    both_at = None
    end = time.ticks_add(time.ticks_ms(), RUN_S * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        splat.poll()
        for i, link in enumerate(links):
            if link.ready and not was[i]:
                handle[i] = link._conn_handle
                tx[i] = link._tx_char_handle
                print("[%6.2f] READY unit %d handle=%s" % (_t(), i, handle[i]))
            if was[i] and not link.ready:
                t = _t()
                other = 1 - i
                oi = [x for x in initiates if x[1] == other and x[0] <= t]
                oc = [e for e in events if e[1] == "connect" and e[3] == links[other].mac_address and e[0] <= t]
                own_disc = [e for e in events if e[1] == "disconnect" and e[2] == handle[i] and e[0] <= t + 0.05]
                probe = "n.a."
                if handle[i] is not None and tx[i] is not None:
                    try:
                        link._ble.gattc_write(handle[i], tx[i], b"\x01\x00")
                        probe = "write OK (link alive at controller)"
                    except OSError as e:
                        probe = "write failed errno %s" % (e.args[0] if e.args else e)
                loss = {
                    "t": t, "unit": i,
                    "irq_disconnect": bool(own_disc),
                    "since_other_initiate": (t - oi[-1][0]) if oi else None,
                    "since_other_connect": (t - oc[-1][0]) if oc else None,
                    "probe": probe,
                }
                losses.append(loss)
                print("[%6.2f] LOSS unit %d: irq_disconnect=%s since_other_initiate=%s "
                      "since_other_connect=%s probe=%s"
                      % (t, i, loss["irq_disconnect"], loss["since_other_initiate"],
                         loss["since_other_connect"], probe))
            was[i] = link.ready
        if both_at is None and splat.connected_count == 2:
            both_at = _t()
            print("[%6.2f] BOTH READY" % both_at)
        time.sleep_ms(1)
    held = splat.connected_count
    print("SUMMARY %s: connects=%s drops=%s initiates=%d both_ready_at=%s ready_at_end=%d "
          "conn_updates=%d notifies=%s misrouted=%d"
          % (label, [l.connects for l in links], [l.drops for l in links],
             len(initiates), both_at, held, len(updates), notifies, hub.misrouted))
    for u in updates:
        print("  update t=%.2f handle=%d interval=%.1f ms latency=%d supervision=%d ms status=%d"
              % (u[0], u[1], u[2] * 1.25, u[3], u[4] * 10, u[5]))
    hub.close_all()
    t = time.ticks_add(time.ticks_ms(), 2000)
    while time.ticks_diff(t, time.ticks_ms()) > 0:
        time.sleep_ms(1)
    return {"label": label, "losses": losses, "held": held, "both_at": both_at,
            "updates": updates}


def verdict(r):
    L = r["losses"]
    if not L:
        return "%s: no losses (both held=%s)" % (r["label"], r["held"] == 2)
    n = len(L)
    real = sum(1 for x in L if x["irq_disconnect"])
    alive = sum(1 for x in L if x["probe"].startswith("write OK"))
    near_init = sum(1 for x in L if x["since_other_initiate"] is not None
                    and x["since_other_initiate"] < 1.5
                    and (x["since_other_connect"] is None
                         or x["since_other_connect"] > x["since_other_initiate"]))
    near_conn = sum(1 for x in L if x["since_other_connect"] is not None
                    and x["since_other_connect"] < 0.5)
    sups = sorted(set(u[4] * 10 for u in r["updates"]))
    parts = ["%s: %d losses" % (r["label"], n),
             "%d with IRQ disconnect" % real,
             "%d probe-alive" % alive,
             "%d within 1.5 s of other INITIATE before its connect" % near_init,
             "%d within 0.5 s after other CONNECT" % near_conn,
             "supervision ms seen %s" % (sups or "none")]
    lean = []
    if real < n or alive:
        lean.append("H3 (hub state reset without radio disconnect)")
    if near_init >= n // 2 + 1:
        lean.append("H1 (initiation starves live link)")
    if near_conn >= n // 2 + 1:
        lean.append("H2 (connection limit)")
    parts.append("leans " + (" + ".join(lean) if lean else "unclear"))
    return " | ".join(parts)


results = []
for v in VARIANTS:
    try:
        results.append(run(*v))
    except Exception as e:
        print("VARIANT %s crashed:" % v[0])
        sys.print_exception(e)
for r in results:
    print("VERDICT " + verdict(r))
print("DONE")
