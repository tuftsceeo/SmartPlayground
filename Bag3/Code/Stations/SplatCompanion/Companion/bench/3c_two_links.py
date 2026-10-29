"""
3c_two_links.py -- diagnostic for two Splat connections on one hub
===================================================================
Run on the hub: mpremote connect $HUB resume run bench/3c_two_links.py
Needs on the hub: the stage-3 files (bench/README.md). BOTH Splats on and
searching. /main.py moved aside.

For each entry in VARIANTS (connection interval, direct-connect timeout,
retry gap) it builds SplatHub(2), runs RUN_S and logs, with times: each
INITIATE (gap_connect call), BLE IRQ connect/disconnect/conn-parameter
update and any other unhandled event, a link state reset while connected
with the last IRQ seen, and each link loss with a write probe on its old
handle. It ends each variant with a SUMMARY and the run with VERDICT
lines.

VERDICT labels a variant's losses by the evidence pattern it matches:
  H1  loss within 1.5 s of the other link's INITIATE, before its connect
  H2  loss within 0.5 s after the other link's connect completes
  H3  loss with no IRQ disconnect for that handle, or the old handle
      still accepts a write
Times are measured from when the loss is detected, which can follow the
disconnect by a few ms; read the IRQ lines for exact order.
IRQ 29/30 (_IRQ_GET_SECRET / _IRQ_SET_SECRET) are the stack's key-store
reads and writes; nothing here stores keys.
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

# A copy of a lib/ module in / shadows /lib/ (MicroPython searches / first)
# and has caused a stale driver to run: report every module's file and
# size, and stop on a shadow.
import ble_splat
_shadow = []
for _name, _mod in (("ble_splat", ble_splat), ("splat_link", splat_link),
                    ("splat_hub", sys.modules["splat_hub"]),
                    ("splat_api", sys.modules["splat_api"])):
    _f = _mod.__file__
    print("3c: %s from %s (%d bytes)" % (_name, _f, os.stat(_f)[6]))
for _lib in os.listdir("/lib"):
    try:
        os.stat("/" + _lib)
        _shadow.append(_lib)
    except OSError:
        pass
if _shadow:
    print("FAIL: root copies shadow /lib/: %s -- remove them and rerun" % _shadow)
    raise SystemExit


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
