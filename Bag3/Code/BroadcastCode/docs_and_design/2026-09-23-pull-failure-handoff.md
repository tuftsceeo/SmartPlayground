# Intermittent wand code pull — investigation handoff, 2026-09-23

Branch `Chat_to_Tap_Doggle`, code state `7efa4ff`. Written to hand the
investigation to a new agent with local hardware access.

**How this was built.** The evidence section is taken from test reports and
direct observations. The code section is built only from the live source
at `7efa4ff`. Comments, READMEs, design notes and earlier conclusions in
this session were treated as stale and not relied on. Where an earlier
conclusion is wrong, section 6 says so.

**Evidence weights:** `[T]` test with captured logs (highest), `[O]` direct
human observation, `[C]` code reading (lowest). `[X]` marks a claim about
ESP-IDF or MicroPython behaviour that nobody has verified on these boards.

---

## 1. The problem

A MockWand taps a `getcode:<slug>@<host>` card. It reboots into pull mode,
joins that Dial's SoftAP, and pulls one game file over TCP. **Sometimes the
pull fails.** Once a wand–Dial pairing fails, it tends to keep failing; once
it works, it tends to keep working [O]. The user first saw this on
2026-09-22/23, while testing several Broadcast hosts in one room.

Nothing is verified fixed. Real defects were found and fixed along the way
(antenna selection, per-chunk allocation, exception handling), and the
failure persists after every one of them.

## 2. Four failure types, addressed separately

These are the four types observed during the 9/22 tests. F1–F3 are
symptoms: each is the point in the pull where it failed. F4 is a
*condition*: the attempt started while the Dial was still holding the
wand's previous attempt. F1 or F2 can happen inside it. Classify every
failed attempt as one of F1–F3, and separately record whether it was in F4.

| | **F1 — stalls on block x of y** | **F2 — never connects** | **F3 — TCP client issue** | **F4 — timeout mismatch / retry overlap** |
|---|---|---|---|---|
| Where it fails | Mid-body, after the header | WiFi association, before any TCP | Joined, but socket connect, request or header fails before the first body byte | Retry begins while the Dial still holds the prior attempt for this wand's MAC |
| Wand log | header, then `[Errno 116] ETIMEDOUT` ~10–11 s later; `pull failed mid-transfer` | `STAT_CONNECTING`, then `STAT_IDLE` on attempt 2; `pairing failed -- giving up` | `joined ...` present, **no** `receiving ...`; then **the same** `pairing failed -- giving up` line as F2 | `# pull mode: attempt 2/2`, or any attempt shortly after an unclean exit |
| Dial log | client in `body`, `sent` frozen at a multiple of 512, deadline counting down, no exception, reaped at the 30 s deadline, no RST | no accept | `pull ? fail` in `stats.log`: accepted, then finished before its request resolved (slug unset) | `clients=1` and/or `stations=1` from the prior attempt when the new one begins |
| Code path | `_recv_body` (`code_puller.py:223-259`) vs `_step_body` (`code_server.py:826-864`) | `_connect_wifi` (`code_puller.py:533-618`) vs the AP driver | `pull()` maps any `OSError` before the body to `'nojoin'` (`code_puller.py:801-808`); Dial `_S_REQ` 5 s deadline (`code_server.py:60, 618`) | Wand `recv` timeout 10 s + reset + boot + scan vs Dial reply deadline 30 s after last progress (`code_server.py:59`); station age-out ~85 s observed |
| Observed instances | Instance 1 & 2, Update 2, Update 3 (×5 offsets: 3072, 3072, 4096, 4096, 7680), Update 4 cycle 1, T5-A | Instance 1 attempt 2, Update 2 retry, Update 4 cycle 2, T2 (most of 10), T5-A/B | **No wand-side capture this session.** Dial 1 `stats.log`: 138 `pull ? fail` in a 140–165 ms burst, source unknown | **By code, every attempt 2** (below). Plus T2's first attempts that followed a failed cycle by less than the age-out |

**F3 is currently invisible on the wand.** The wand prints the same final
line for F2 and F3. Tell them apart by whether `joined <ssid>` and
`[XFER] connected to` appear before it. T2's "10/10 pairing failed" and
T5's "pairing failed" have to be re-read with that in mind; the summary
line alone cannot say which type occurred.

**Every second attempt is in F4, by construction:**

- A second boot only happens after an F1 (D6).
- The wand abandons 10 s after the last byte, then resets, boots and
  scans. Its retry join starts about 13–20 s after the stall began.
- The Dial holds the stalled client until 30 s after its last progress
  (D11), and the station entry for ~85 s (E20).

So attempt 2 always overlaps the stale TCP client, and it has overlapped a
stale station entry in every instance measured. This matches the user's 9/22
observations: second attempts always failed, and the Dial still showed
"receiving" when the retry began (E7).

**Outcomes observed inside F4 are mixed.** Most were F2 (Instance 1,
Update 2). Update 3 records one where the retry **joined and then stalled
again** at a different offset (F1 inside F4). So a same-MAC re-association
during the holdover *can* succeed. Whatever F4 does, it doesn't always
block the join.

**Two questions, kept apart:**

1. What causes the *first* failure of a pairing? This is always F1 or F2,
   outside F4.
2. Does F4 cause the *repeat* failures? Test A and test H settle it.

## 3. Hypothesis status

### 3.1 Disproven

"Disproven" means a test shows the hypothesis is neither necessary nor
sufficient. "As a mechanism" means it cannot produce the observed
signature.

| ID | Hypothesis | Disproven by |
|---|---|---|
| H2 | Wrong antenna selected | Fixed and verified (`antenna: external`, −22 dBm). F1 and F2 continue [T, Update 4] |
| H3 | Antenna not re-asserted on retry | Fixed and verified (re-printed per attempt). F2 continues at −33/−34 dBm [T, Update 4] |
| H4 | Receiver overload at close range | Failures at −33 to −61 dBm as well as −22 [T, Updates 1, 4] |
| H12 | `MemoryError` escaping `_advance()` | Catch-all live and printing nothing during a 28 s stall [T, Update 2] |
| H13 | Per-chunk allocation churn | Buffer reuse live; stalls continue [T] |
| H16 | Transfer rate tied to the UI loop | During a stall the Dial loop runs on time (2 s dumps, deadline counting down). It isn't moving *slowly*; it has stopped [T, Update 2] |
| H17a | The held TCP client uses up the slot the retry needs | The cap of 4 is never reached, and F2 fails before TCP exists [T + C]. **This refutes only the slot-exhaustion form.** The timeout mismatch itself (F4) is real, certain from code, and still open (H17b in 3.3) |
| H21 | `_find_ap()` picks the wrong AP | Every failing log shows the wanted SSID matched [T] |
| H23 | Real NFC tap vs scripted `pull_flag` path | The scripted path failed 10/10 in T2 [T, Update 6] |
| H26a | Pools fill to `MAX_CLIENTS` | `stations=1` and `clients≤1` throughout failures; the cap is never reached [T, Update 6]. The lingering-station half survives as N1 |
| — | "Fails only after a wand power cycle" | T2 fails with no power cycle [T] |
| — | "Fails only after pulling from a *different* Dial" | T2 fails pulling from the same Dial repeatedly [T] |
| H1/H22 | A second co-located AP is **required** | T5 Phase A: F1 and F2 with only Dial 1 armed. **n=2, and nobody confirmed from the wand's scan log that Dial 2's SSID was absent.** Treat as disproven only once that is checked |

### 3.2 Weakened

| ID | Hypothesis | Why weakened |
|---|---|---|
| H6′ | Wand RTC-held radio calibration is the sticky state | T2: the wand hard-reset every cycle and stayed failing. T4: a reset of the Dial alone recovered it. **Low weight** — mpremote activity during the session interrupted devices (section 7) |
| H11/H15 | Dial Python-heap pressure | `gc_free` was 40–55 K during failures; no allocation error anywhere |
| H-heap | Dial IDF heap fragmented over a long uptime (Update 6) | Only evidence: `idf_largest` 7680 while failing vs 20480 after a reset. The two readings are not shown to be at the same point, and nothing links contiguous IDF heap to association. The Dial-reset recovery fits N1 just as well. Test B separates them |

### 3.3 Open

| ID | Hypothesis | Covers | State |
|---|---|---|---|
| **H17b** | **F4 causes the repeat failure: the Dial's holdover of the prior attempt (stale TCP client and/or TCP state) breaks the retry** | F4 → F1 or F2 | Holds for every attempt 2 by code. Whether it *causes* the retry's failure is untested. Test H separates the TCP half from the station half |
| **N1** | **The station half of F4: the SoftAP keeps a stale entry for the wand's MAC after an unclean exit, and re-association from the same MAC fails while it stands** | F2 inside F4; the sticky state | **Leading explanation for F2 inside F4 and for the sticky state** (4.3). **Not absolute:** Update 3's retry re-associated during the holdover and then stalled. Explains nothing about the first failure |
| **H5** | **Wand–AP link dies mid-body (association lost, or RF path stops carrying data)** | F1 | **Leading explanation for F1.** Wand association state during a stall has never been captured |
| F3-src | Source and frequency of F3 | F3 | Unknown. The wand mislabels it as F2, and the Dial's `pull ? fail` burst has no attributed source. Test I |
| H7 | Ambient 2.4 GHz congestion (24 APs, `tufts_eecs` on channel 1) | F1 | Untested |
| H8/H9/H10 | Brownout during TX; peripherals left energized across reset; external antenna current | F1 | Untested. No battery data during a pull |
| H14 | Dial LVGL/flash work starving the WiFi driver | F1 | Python loop proven alive; driver-level starvation not tested |
| H18 | Spurious hold-to-EXIT drops the AP mid-transfer | F1 | One unexplained `# serve aborted by EXIT` on Dial 2 during a free-run window. Not correlated with any stall |
| H19/H20 | Longer SSID; BSSID pinning | F2 | Untested. BSSID pinning **predates** `95898a1` (section 5.3), so it is not new |
| H24 | The problem predates the multi-device work | both | Unresolved. `stats.log` cannot settle it (section 6) |
| H25 | Per-unit variance | both | **Every test used one MockWand.** Dial 1 fails ~9% of named pulls in `stats.log` vs Dial 2 ~48%; the log mixes sessions, firmware and bench runs |
| N4 | Wand prints and dumps the heap map right before `sta.active(True)` (D2) | F2 | Untested. Violates the tree's own memory-order rule in live code |

## 4. Evidence ledger

### 4.1 Test and observation evidence, in date order

| # | Evidence | Type | Weight / caveat |
|---|---|---|---|
| E1 | Failures first noticed during multi-host work, two Dials armed within feet | O | Sets the premise. Distance is constant [O] |
| E2 | Laptop `pull_bench`: 16/16 pulls, Dial 2 armed and disarmed | T | **The laptop keeps one association across all 16 pulls.** It never re-associates, so it is no control for N1 |
| E3 | Dial logs `low mem ... deferring accept` (~29 K) under back-to-back laptop pulls | T | Only defers a *second* client (D9) |
| E4 | F1 on the Dial: `sent=4096/5113` frozen ~28 s, deadline counting down, reaped at deadline, no RST | T | No RST from the wand also means the wand never re-associated in that window (F2 followed) |
| E5 | No exception during the stall | T | Kills H12 |
| E6 | Freeze offsets vary: 3072, 3072, 4096, 4096, 7680 | T | Rules out a fixed size threshold |
| E7 | Dial screen shows "receiving" while the wand is already retrying | O | Explained by D3 + D11 |
| E8 | 12+ scripted `pull_flag`+reset cycles all passed (early session) | T | **Superseded by T2.** Still informative: those runs started clean and ended clean (see 4.3) |
| E9–E12 | Antenna was wrong; fixed; −22 dBm; F1 and F2 continue | T | Kills H2, H3, H4 |
| E13 | Devices consistently feet apart | O | Removes distance as a variable |
| E14 | Dial heartbeats continuous through failures; no crash | T | The Dial stays alive |
| E15 | "~36 pulls" vs Dial `pulls` counter of 8 | O | **Explained by code** (D7): no longer evidence of anything |
| E16 | One `# serve aborted by EXIT` on Dial 2, in a 9-min free run with humans handling devices | T | H18 only |
| E17 | Hysteresis: good stays good, bad stays bad; clears with idle time or a full reset of both | O | The central property |
| E18 | T1: Dial 1 49 ok / 5 fail named pulls, plus 138 `pull ? fail` in a tight burst; Dial 2 16 ok / 14 fail | T | Timestamps are per-boot `ticks_ms` (D7), so gaps across boots mean nothing. `?` = client dropped before its request resolved; source unknown, and not the wand path |
| E19 | T2 (paced, scripted, Dial 2 untouched): 10/10 failed, mostly F2 | T | Wand hard-reset every cycle. Dial 2 had been reset and re-armed just before T2 after an mpremote halt. **Which reset was used there is not recorded** |
| E20 | T2: `clients=1 stations=1` during a stuck join; then `clients=0 stations=1` for ~85 s after the wand gave up; then `stations=0` on its own, with `idf_free` rising in the same tick | T | **The most direct observation of N1 so far**: a station entry outliving the wand's attempt, then aging out |
| E21 | T4: reset of Dial 2 alone, wand untouched → next pull succeeded first try | T | Supports "state on the Dial". Consistent with N1 and H-heap alike |
| E22 | T6: two stalls, `sel` flat while in `body` | T | **Does not discriminate** (section 6, item 1). Neither kills nor supports H5 |
| E23 | T5 Phase A (only Dial 1 armed): 2/2 failed, one F1 then F2. Phase B (both armed): 2/2 F2 | T | n=2 each; Dial 1 had not been reset. Needs the scan-log check (3.1, last row) |
| E24 | PN532 `RuntimeError: Bad ACK` at boot, twice, only during rapid wand resets | T | Side effect of the test cadence. Not the pull path |
| E25 | Update 3: two consecutive sub-attempts of one tap **both stalled**, at different offsets | T | Attempt 2 was in F4 and still re-associated. Then it failed as F1, not F2. **A counterexample to N1 as absolute** |
| E26 | User, 9/22: "the second attempts will ALWAYS fail"; "the timeouts are out of sync" | O | Every attempt 2 is in F4 by code (section 2). The outcome inside F4 varies (E25) |

### 4.2 What the evidence establishes

1. **F1 is a dead link, not a slow one.** The Dial's socket stays unwritable
   for ~28 s: the wand acknowledges nothing (E4). Separately, the wand's
   `readinto` gets zero bytes for 10 s (ETIMEDOUT). Retransmissions over a
   working association would have got through in that time.
2. **The Dial process stays healthy** through both modes (E5, E14, E16's
   single exception aside).
3. **The sticky state lives on the Dial side** (E19, E21; low–medium weight
   given section 7), and survives many hard resets of the wand.
4. **A station entry can outlive the wand's attempt by about 85 s** (E20).
5. **Signal strength, antenna and AP selection are not the cause** (E9–E13).

### 4.3 How F4 (and N1 within it) fits the pattern — and where it doesn't

- **Sticky good:** a pull that succeeds ends with a live link, so the
  wand's close and deauth actually arrive (D4). Nothing is left behind, and
  the next pull re-associates cleanly. E8's 12 clean scripted cycles are
  this case.
- **Sticky bad:** after F1 the link is dead, so the close and deauth never
  arrive. The wand resets within about a second (D4), and its retry
  re-associates **from the same MAC** a few seconds later (D5). The Dial
  still holds the old entry (E20). Each failed join can leave a fresh
  partial entry, so cycles closer together than the age-out keep it
  failing (E19).
- **Clears with idle time:** the entry ages out, ~85 s in E20.
- **Clears with a Dial reset:** the station table is destroyed (E21).
- **"Second attempts ALWAYS fail":** the only way to reach a second boot
  is an F1 (D6). So every second attempt lands on an unclean exit.
- **The laptop never fails:** it never re-associates (E2).

**Where it doesn't fit:** in E25 the retry re-associated during the
holdover, then stalled. Either the station entry had already cleared, or the
holdover harms the retry some other way (H17b: the stale TCP client, or TCP
state for the same IP). Test H separates the two.

[X] Whether the ESP32 SoftAP actually rejects re-association from a MAC it
still lists, and what its age-out timer is on this IDF build, is
unverified. Test A decides it without needing to know.

**F4 explains nothing about the first failure** of a pairing, which is
always an F1 or F2 outside F4. That is the other open question.

## 5. Live code analysis (`7efa4ff`)

### 5.1 Wand pull path (MockWand)

The tap and the pull run in different boots:

1. **The tap** (`main.py:1139-1168`) parses `getcode:<slug>@<host>`, writes
   `/pullpending`, plays feedback, and calls `machine.reset()`. The pull
   boot does not reset or touch the PN532. Whatever state that chip was
   left in persists, unless it is reset by hardware; the code doesn't show
   whether it is.
2. **Pull boot, before the radio:**
   - `main.py` runs all its module-scope imports and object construction
     (lines 16-49, 300-311: LEDs, I2C, buzzer, pins), then `main()`
     (`main.py:807-810`).
   - `_run_pull_mode()` (`main.py:705-801`) spends one attempt
     (`pull_flag.bump()`) and lights LEDs. `buz.start()` plays a blocking
     tune. Then it imports `code_puller`, which prints its revision at
     import (`code_puller.py:42`).
   - `pull()` calls `memprobe.probe()` and `memprobe.frag()`, which prints
     `micropython.mem_info(1)` — the full heap map — immediately before the
     join (`code_puller.py:678, 692`; `memprobe.ENABLED = True`).
3. **Join** (`_connect_wifi`, `code_puller.py:533-618`). Up to 2 attempts
   per boot. Each attempt:
   - `_reset_sta()`: `disconnect()` + `active(False)` + 300 ms if already
     active; antenna pins (GPIO3=0, 100 ms, GPIO14=1); `active(True)`;
     300 ms.
   - Scan: 3 tries on the first attempt, 1 on the second.
   - `connect(ssid, pwd, bssid=...)`, then poll `isconnected()` every
     200 ms for up to 6 s.
   - The STA MAC is never changed, so the AP sees the same MAC on every
     attempt and every boot.
4. **Transfer** (`code_puller.py:697-777`):
   - `pm=0`; socket timeout 10 s, per `recv`; connect to `192.168.4.1:8266`.
   - Request frame; header read.
   - Body loop (`_recv_body`, 223-259): `readinto` ≤512 B → flash write →
     sha256 → `_pull_progress` rewrites all 60 NeoPixels
     (`main.py:691-702`) → `sleep_ms(20)`.
   - 2-byte `OK`/`NO`.
5. **Exit** (`code_puller.py:809-824`): `finally` closes the socket, then
   `sta.disconnect()` and `sta.active(False)`. Nothing checks that the FIN
   or deauth was delivered. `main.py` resets about 600 ms later
   (`main.py:784-801`).
6. **Retry policy** (`main.py:759-801`, `code_puller.py:791-808`):
   - `noap`, `nojoin` (join failed, or an `OSError` before the body) and
     `norequest` all give up.
   - Only a failure **during the body** returns `False`, which leaves the
     flag set and resets for attempt 2 of 2.

### 5.2 Dial serve path

1. **Boot** (`bdial_server.py:1137-1189`): `M5.begin()`, then
   `prewarm_ap()` (AP on/off once), then LVGL UI, NFC, stats and game scan.
   Entering SERVE calls `arm()`.
2. **`arm()`** (`code_server.py:464-506`): `gc.collect()`, then
   `_start_ap()`. The AP is WPA/WPA2-PSK, channel 1, `pm=0`,
   `max_clients=4`, at 192.168.4.1 on every Dial. Then a listening socket
   with backlog 4 and timeout 0. The probe module is imported only after
   this, when `DEBUG_SERVE` is on.
3. **Main loop** (`bdial_server.py:1193-1207`): `link.pump()` (≤20 ms idle
   wait, ≤40 ms drain), `M5.update()` and input, `_poll_serve()`, a
   heartbeat, `sleep_ms(1)`.
4. **`poll()`** (`code_server.py:527-600`):
   - Accept up to 4 clients (`_accept_new`, 602-622). An extra client is
     deferred while `gc_free < 30000`.
   - Reap clients past their deadline.
   - `select()` with 0 timeout: clients in `hdr`/`body`/`icount` go on the
     **write list only**; clients in `req`/`ack` on the read list only. The
     exceptional list is empty.
   - Advance each ready client one step.
   - `sleep_ms(20)` whenever any client is in `body`.
5. **Body** (`_step_body`, 826-864): one chunk per ready tick. A write that
   moves nothing counts as `blocked`; progress refreshes a **30 s**
   deadline.
6. **Finish** (`_finish`, 656-678): close, emit an event (LVGL repaint),
   then `stats_log.record_pull()`. That appends to flash and rewrites up to
   200 lines (`stats_log.py:50-78`) inside the serve loop.

### 5.3 What changed in the window

- The multi-client server (`max_clients`, the `_Client` state machine) landed
  in `28ce41c` on **2026-09-15**, not with the multi-device work.
- `95898a1` (2026-09-23 00:41) changed the SSID to `SP-FILEPUSH-<id>` and
  `_find_ap()` to exact-or-strongest matching. The wand already connected by
  BSSID before that commit.
- Every other change on 09-22/23 is antenna, buffer, exception or
  instrumentation work, made after failures were already seen.

### 5.4 Code facts and defects that bear on the hypotheses

| ID | Fact (live code) | Bears on |
|---|---|---|
| D1 | `code_server.py:588-598` (Dial only): the `# DEBUG client state` print is **not** gated by `DEBUG_SERVE`. Its format string is allocated at import, before `prewarm_ap()`. The Box copy lacks it — a PEER divergence. Added in `d6205a2` | memory-order rule; PEER sync |
| D2 | `memprobe.ENABLED = True` on the wand (`lib/memprobe.py:37`). `probe()` prints and `frag()` dumps `mem_info(1)` before `sta.active(True)` on every pull (`code_puller.py:678, 692`; `main.py:723, 744`). `code_puller.py:42` prints at import | N4; memory-order rule |
| D3 | The Dial never sees a peer close during `body`. The socket is only on the write list, and the exceptional list is empty. A dead client is held until 30 s after its last progress | E7; stale TCP state |
| D4 | The wand exits a failed pull by closing and disconnecting, then resetting within ~1 s. On a dead link neither the FIN nor the deauth can arrive | N1 |
| D5 | Same STA MAC every boot. The retry boot re-associates seconds after the unclean exit | N1 |
| D6 | Only a body failure earns a second boot, so a second boot always follows an F1 | "second attempts always fail" |
| D7 | `stats_log` stamps lines with per-boot `ticks_ms()` and keeps the newest 200 lines, shared with tag writes. `aggregate()` counts only `ok` lines in that window | E15 explained; E18 gaps invalid |
| D8 | `_finish()` does a flash append and a rewrite of up to 200 lines inside the serve loop, on every pull end | H14 (concurrent transfers) |
| D9 | `MIN_FREE_ACCEPT` defers an accept only when a client is already present. A stale client plus `gc_free < 30000` would defer the retry's accept. The heartbeat showed 40–51 K, so this is unlikely | minor |
| D10 | Per chunk, the wand does a flash write, a 60-LED NeoPixel write and a 20 ms sleep. `pull_bench` on the laptop does none of these | H8, H14-analog on the wand |
| D11 | Timeouts: wand join 6 s, wand `recv` idle 10 s; Dial request 5 s, reply 30 s | E7 |
| D12 | Every Dial: channel 1, same PSK, 192.168.4.1, `max_clients=4` | H1/H22 |

### 5.5 Timeline of an F1 → F4 → F2 tap, from code and logs

Rows from ~11 s to ~30 s are the F4 window for the TCP client. The station
half runs to ~90 s.

| t (s) | Wand | Dial |
|---|---|---|
| 0 | last byte arrives | `sent` stops advancing; the socket fills and stays unwritable |
| ~10 | `recv` times out → close, disconnect, `active(False)` | still `body`, retransmitting (no ACKs) |
| ~11 | `machine.reset()` | station entry still listed (E20) |
| ~13–20 | pull boot → antenna → scan → `connect()` from the same MAC | TCP client still held (E7); station entry still listed |
| ~19–26 | F2: 6 s join fails → attempt 2 fails → `pairing failed -- giving up`. (In E25 the join succeeded here and the body stalled again: F1) | no accept (or, in E25, a second client alongside the stale one) |
| ~30 | normal boot | TCP client reaped at the deadline, no RST (E4) |
| ~90+ | — | station entry ages out (E20) |

## 6. Corrections to earlier conclusions in this session

1. **T6 is void.** When a peer stops acking, the TCP send buffer fills, and
   a full buffer isn't writable — so `sel` goes flat both when the peer is
   gone and when the Dial's driver is stuck. The rule that "flat `sel`
   points at the loop or driver, not the peer" was wrong. It was corrected
   in `serve_probe.py` in `7efa4ff`. H5 is open.
2. **The multi-client rewrite was dated wrongly.** It landed 2026-09-15
   (`28ce41c`), not 2026-09-21. It is not the multi-device work.
3. **T1 settled nothing about timing or origin (H24).** `stats.log`
   timestamps restart every boot (D7).
4. **E15 is explained by code** (D7) and is not evidence.
5. **E8 is superseded** by T2 as a test of H23.
6. **`mpremote reset` is a hard reset** (`machine.reset()`), not a soft
   one. That removes the "contradiction" between the arm-time OOM (a boot
   order that re-created the fragmentation on every boot) and T4.
7. **The arm-time OOM (`95f684c`) and the T0 gate are unrelated** to the
   pull failure. That was a defect introduced during the investigation, and
   it is closed.
8. **The first version of this report (`142afdd`) collapsed the four failure
   types into two.** It dropped F3 (TCP client issue), and it marked H17
   "disproven" while only refuting slot exhaustion, not the timeout
   mismatch (F4). It also called N1 a fit for every observation, missing
   E25. All three are corrected here.

## 7. Confounds in the existing data

- **mpremote interrupts serving Dials.** `mpremote fs`/`exec` halts
  `run()`. Its `finally` calls `disarm()`, so the AP goes down
  (`bdial_server.py:1208-1227`). At least one run lost Dial 2's AP this
  way. Any run with mpremote activity against an armed Dial is suspect.
- **Reset type is unrecorded** for the Dial 2 recovery before T2, and for
  most other resets.
- **Reflashes, flag flips and instrumentation changes happened mid-session.**
  Dials ran different builds at different times.
- **One wand.** Nothing separates "wands" from "this wand" (H25).
- **Firmware versions are unrecorded.** MicroPython and ESP-IDF versions on
  either board are unknown. Any [X] claim depends on them.
- **Rapid reset cadence** produced side effects (E24) until pacing was fixed.

## 8. Next tests (hands-off unless marked), ranked

Before every run:

- **Hard-reset both Dials** and record `sys.version`/`os.uname()` once.
- **Arm with `DEBUG_SERVE=True`** on the Dial.
- **Keep mpremote off any armed Dial** for the whole run. Read serial
  passively only (`tools/serial_monitor.py`).
- **Pace wand cycles on its settle marker** (`pull OK`, `attempt budget
  spent`, `pairing failed`, `Tap a TRIGGER tag`).
- **Record which Dials are armed**, and confirm it from the wand's scan
  list, not the command sent.

**A. Retry timed against `stations=` (station half of F4, N1; no code change).**
From a failing state, fire a scripted pull while `stations>=1` and the wand
is not connected; then again right after `stations` drops to 0. Repeat
≥5 times each, and record the failure-to-`stations=0` time.

- *N1 predicts:* fail while the entry is listed; succeed after it clears.
- *H-heap predicts:* no dependence on `stations`.

Add the station MAC list to `serve_probe.stations()` first. It runs after
bring-up, so this is safe. That confirms the lingering entry is the
wand's MAC.

**B. AP restart without a reset (N1 vs H-heap).** From a failing state:
switch SERVE→WRITE→SERVE over `json_drive` (an in-place `disarm()`/`arm()`,
no reset). Record `idf_largest` before and after, then pull.

- *N1 predicts:* success, with `idf_largest` about the same.
- *H-heap predicts:* still failing unless `idf_largest` rises.

**C. Vary the wand's STA MAC per boot (confirms N1 by removal).** Set a
random locally-administered MAC after `sta.active(True)` and before
`connect()`, behind a flag. Put the logic in a module imported *after*
`active(True)`, never in `code_puller.py`'s import-time body.

- *N1 predicts:* F2 stops following F1, and the sticky-bad state
  disappears. F1 still occurs.

**D. Capture a stall from both sides (decides H5 for F1).** Run
`DEBUG_PULL=True` on the wand and `DEBUG_SERVE=True` on the Dial, until
F1 appears.

- Wand `assoc=False` during `STALLED` → association lost (H5).
- `assoc=True` with `STALLED`, and the Dial still lists the station → both
  ends think they are associated and no data moves. That is RF or driver;
  go to E.

**E. Controls for what starts F1.**

- **Disable wand memprobe** (`ENABLED=False`) for one run (N4).
- **One AP vs two**, ≥10 cycles each, from freshly reset Dials, with the
  scan list confirming which SSIDs were audible (H1).
- **Leave the progress LEDs off** for one run (D10, H8).

**F. Reason codes.** Try IDF WiFi logging (`esp.osdebug`) on the wand and
the Dial, to get STA disconnect reasons and SoftAP join/leave events. First
confirm where the output goes: on the S3's native USB it may go to a UART
nobody is reading. Put any call made on the wand before the join through
the memory-order rule (section 9).

**G. [hands] A second wand**, same tests A and D (H25).

**H. Take F4 apart, one half at a time (H17b vs N1).** Two value-only
changes, run one at a time. Neither adds module-scope content.

- **Close the TCP half:** drop `SOCK_REPLY_TIMEOUT_S` on the Dial from 30 to
  8, below the wand's 10 s `recv` timeout, so the stale client is reaped
  before the retry arrives. If attempt 2 now succeeds, H17b is the cause.
- **Close the station half:** delay the wand's retry reset
  (`main.py:796-801`) past the observed station age-out, e.g. 100 s, on the
  bench only. If attempt 2 now succeeds and the first change alone did not,
  N1 is the cause.

Record every attempt as F1/F2/F3, plus whether it was in F4.

**I. Make F3 visible.**

- **Re-read existing wand logs.** Class each `pairing failed` by whether
  `joined` and `connected to` precede it.
- **Split the wand's failure line.** Give the `OSError`-before-body branch
  its own return value and message, distinct from a join failure
  (`code_puller.py:801-808`, `main.py:770-774`). Both files are imported
  before the radio claims its memory, so any new literal in either one is
  allocated ahead of it. Keep the change to one short return token, and
  reuse an existing print format for the message. Then gate the change: a
  scripted pull must still join before anything else is tested.
- **Find the source of the Dial's `pull ? fail` burst.** Log the peer
  address on accept in `serve_probe.accepted()`.

**What would close it:**

- H identifies which half of F4 breaks the retry, and A/C confirm it. That
  explains the repeat failures and the hysteresis. The fix then goes on the
  wand (a longer retry delay, or a new MAC per attempt) or on the Dial
  (reap sooner, or deauth stale stations).
- D shows association loss → F1 is H5, and the question becomes what
  drops it: E's controls, then F's reason codes.

## 9. Constraints for the next agent

- **Nothing may allocate before the radio claims its memory.** That holds
  on the Dial (before `prewarm_ap()`/`_start_ap()`) and on the wand (before
  `enow.init()` on a normal boot, and before `sta.active(True)` in pull
  mode). No new module-scope content — prints, format strings, docstrings —
  in `code_server.py` or `code_puller.py`. Diagnostics go in
  `serve_probe.py` / `pull_probe.py`, imported after bring-up. See
  `docs_and_design/2026-09-23-ap-memory-order.md`. D1 and D2 are existing
  violations; fix or control for them deliberately, not in passing.
- **PEER copies:** `code_server.py` and `serve_probe.py` exist in the Dial
  and Box trees; `code_puller.py` and `pull_probe.py` in MockWand and
  IconDisplay. Fix one copy and say which.
- Follow `Bag3/Code/HARDWARE_PROTOCOL.md`: `resume` on every `mpremote`
  call, and ask before opening an unidentified port.
- Uncommitted bench scripts from the last session:
  `tools/devtests/sticky_state_bench.sh`, `one_vs_two_bench.sh`. They are
  on the local machine; review and commit them.

## Appendix: key log excerpts

F1, Dial side (Update 2):

```
# DEBUG client state=body sent=4096/5113 ms_to_deadline=28753
# DEBUG client state=body sent=4096/5113 ms_to_deadline=26736
...
# DEBUG client state=body sent=4096/5113 ms_to_deadline=456
(reaped at deadline; no exception)
```

F1 then F2, wand side (Instance 1):

```
joined SP-FILEPUSH-5094, ip=192.168.4.2
[XFER] receiving /games/apple_button.py, 5113 bytes expected
[XFER] failed: [Errno 116] ETIMEDOUT            (~11 s after header)
-- reset, attempt 2/2 --
status seen while joining: STAT_CONNECTING (1001)
[XFER] join attempt 1/2 failed, status=STAT_CONNECTING (1001)
status seen while joining: STAT_IDLE (1000)
[XFER] join attempt 2/2 failed, status=STAT_IDLE (1000)
```

Lingering station, Dial side (Update 6, T2):

```
clients=1 stations=1      while the wand's join was stuck
clients=0 stations=1      ~85 s after the wand gave up
stations=0                self-cleared; idf_free rose in the same tick
```

A clean pull under instrumentation (Update 6, T0):

```
# DBG accepted: clients=1 stations=1 gc_free=54704
# DBG finish ok=True state=ack sent=5113/5113 age_ms=1647 sel=15 blocked=0 clients=0 stations=1
```
