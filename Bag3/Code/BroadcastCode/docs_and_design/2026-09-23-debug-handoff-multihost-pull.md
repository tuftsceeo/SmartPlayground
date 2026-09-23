**Note for the sparring partner**: T2/T4 traced most of today's failures to
per-Dial IDF-heap fragmentation from repeated `arm()`/`serve()` cycles (clears
with a plain soft reset, no power cycle needed), and T6 independently landed
on the same `sel`-flat-during-a-stall symptom your `7efa4ff`/`5781335` already
fix -- worth re-running these tests against that newer firmware.

## Update 6: revert confirmed the fix; T0 (flag gate) passed; T1 (stats.log) settled

Pulled and reflashed in order: `41f78dc` (revert of `95f684c`'s instrumentation),
`c59638a` (re-added DEBUG_SERVE/DEBUG_PULL via lazy `serve_probe.py`/
`pull_probe.py` imported only after AP/radio bring-up), `06eac45` (docs only).
All three device trees (Dial 1, Dial 2, MockWand) reflashed and verified
byte-for-byte via read-back diff before every reset.

**41f78dc fixed the WiFi-Out-of-Memory blocker.** Both Dials armed
successfully on the very first attempt after reflash: Dial 1 `SP-FILEPUSH-5094`
and Dial 2 `SP-FILEPUSH-004c` both returned `{"type":"armed"}` then
`{"type":"ok","cmd":"arm"}`. Confirms the sparring partner's diagnosis: the
instrumentation string data was allocated at import time (before
`prewarm_ap()`/`_start_ap()` runs), fragmenting the heap ahead of the AP's
contiguous-block grab. `idf_largest=7680` vs `idf_free=12456` (from Update 5)
was fragmentation, not real exhaustion -- correcting my own earlier framing.

**T0 (arm-with-flag-on gate): PASS, both Dials, plus a full real pull served
under instrumentation.** With `DEBUG_SERVE=True` flashed to Dial 1 and
`DEBUG_PULL=True` flashed to MockWand, ran a zero-hands pull
(`pull_flag.set_pending` + reset) of `apple_button` from the wand against
Dial 1. Full success, no OOM, no stall:
```
wand:  joined SP-FILEPUSH-5094, ip=192.168.4.2
       [XFER] receiving /games/apple_button.py, 5113 bytes expected
       [XFER] OK: /games/apple_button.py promoted, 5113 bytes
       # pull OK -- resetting into the new game
dial1: # DBG accepted: clients=1 stations=1 gc_free=54704
       # DEBUG client state=req sent=0/0 ms_to_deadline=5099
       # DBG finish ok=True state=ack sent=5113/5113 age_ms=1647 sel=15 blocked=0 clients=0 stations=1
```
Byte counts match exactly (5113/5113) on both sides. Dial 2 also confirmed
armed with `DEBUG_SERVE=True` (`SP-FILEPUSH-004c` -> armed -> ok). The lazy,
post-bring-up import design in `c59638a` works as intended -- this gate did
**not** fail, so instrumentation is back on the table.

**T1 (stats.log) settled, does not invalidate anything.** Fresh pull (200/30
lines, each file's own trim cap):
- Dial 1: 200 lines, 57 "ok" / 143 "fail". But 138 of those 143 fails are
  `pull ? fail` (unresolved slug) in a tight ~140-165ms-apart burst -- the
  same pre-existing artifact flagged in Update 4, confirmed still present and
  still separable. Real named-slug (`apple_button`) pulls: 49 ok / 5 fail =
  **~9% real failure rate**.
- Dial 2: 30 lines, 16 ok / 14 fail, all named `tilt_tones`, no burst pattern
  (gaps range 1s-5.5min -- genuinely scattered, real attempts). **~48% real
  failure rate** (14/29 named attempts).
- The Dial1-vs-Dial2 asymmetry (~9% vs ~48%) is real and reproduces across two
  separate readings of stats.log taken hours apart. Still unexplained -- carries
  into T5 (one-Dial-vs-two) as the thing to watch for.

**Process bug caught mid-T2, corrected**: reading Dial 2's `/flash/stats.log`
via `mpremote fs cp` after arming it halted its running SERVE loop into raw
REPL (per HARDWARE_PROTOCOL.md: fs/exec always halts the running program,
`resume` only skips the soft-reset) and I never re-armed it afterward. Every
T2 cycle run against Dial 2 in that window failed with `NoAP` -- not a real
finding, just Dial 2's AP being genuinely down because nothing was running.
Caught via the continuous Dial 2 monitor showing zero output for 4+ minutes.
Fixed: reset + re-armed Dial 2, confirmed `identify`/heartbeat responding
normally. Discarding all cycle data from that window and restarting T2 clean.
Also hit one unrelated transient hardware glitch on the wand mid-recovery: a
`RuntimeError: Bad ACK` from the PN532 NFC chip's `begin()` during one boot,
uncaught, dropping to raw REPL (visible on the wand's own boot-screen LEDs as
red). The very next reset came up clean (NFC ready, normal boot). One-off
I2C glitch, not reproduced on immediate retry -- noting it, not chasing it.

**Pacing correction, mid-T2 (user caught this live, watching the bench)**:
my first T2 loop cadence (write pullpending + reset every ~24s) was too fast
-- the wand's own boot-retry-reboot sequence (LED/buzzer feedback, up to 2
internal join retries, up to 2 pull_flag attempts) can legitimately take
longer than that, and resetting again before it settles is an external
interrupt, not a natural retry. Slowed to a 60s capture window + 8s settle
pause per cycle, with each cycle's log checked for an actual settle marker
(`pull OK`, `attempt budget spent`, or `Tap a TRIGGER tag`) before the next
cycle fires. Also observed the wand's NFC (PN532) `Bad ACK` crash (see
earlier note) recur twice in quick succession specifically during this rapid-
reset window -- worth flagging as a possible side effect of resetting the
board faster than its own hardware settle time, not necessarily independent
of the testing itself. Not chasing this now, just recording the correlation.

**T2 real data so far (partial, 6 cycles before the pacing fix, kept)**: one
genuine join failure reproduced -- wand found `SP-FILEPUSH-004c` at a strong
`rssi=-33` but stuck in `STAT_CONNECTING` on join attempt 1/2 (the exact
"stuck STAT_CONNECTING" mode from pull_flag.py's own docstring). On Dial 2's
side at the same time: `clients=1 stations=1` while the join was stuck, then
`clients=0 stations=1` for ~85s after the wand gave up on that client slot --
the WiFi-level station association measurably outlived the client-level
cleanup, then self-cleared back to `stations=0` on its own (no reset, no
intervention) with `idf_free` jumping back up in the same tick. This is a
real, live instance of H26 (stale AP stations lingering past client cleanup),
**and** it answers part of T3 for free: this particular stuck station cleared
by itself well under 2 minutes of idle, no soft reset needed.

**T2 final tally, fully paced run (never interrupting a live pull, 8s-90s
between cycles depending on settle time, ~30+ min total): 10/10 cycles
failed.** Essentially every cycle reproduced the same `STAT_CONNECTING` ->
`STAT_IDLE` "AP visible but pairing failed" outcome (one mid-transfer fail).
This is far worse than the ~48% historical baseline, and the wand got a
completely fresh cold-radio boot every single cycle (pull_flag + reset) yet
still failed every time -- strong evidence the stuck state is NOT on the
wand side, since the one thing held constant across every failure was Dial 2
never being touched.

**T4 (recovery by soft reset, Dial side only): CONFIRMED, settles the
question.** With the wand untouched, did `mpremote reset` on Dial 2 alone,
re-armed it, and the very next wand pull joined and succeeded (`pull OK`) on
its first attempt. Also directly measured the mechanism: Dial 2's
`idf_largest` (contiguous IDF DRAM) was sitting at a degraded **7680 bytes**
throughout the entire 10/10-fail run, and jumped to **20480 bytes**
immediately after the soft reset -- essentially 3x. This is heap
fragmentation accumulating from many arm()/serve() cycles over one long
session, not a literal stuck WiFi station association, and **a plain
software reset (no power cycle) fully clears it.** This updates the
"sticky state" framing: the state that persists across pull attempts is a
shrinking largest-contiguous-free-block on the Dial, not RTC-persisted radio
calibration -- and unlike the WiFi-Out-of-Memory blocker from `95f684c`
(which a soft reset could *not* clear, per Update 5), this one *can* be
cleared by a soft reset. The two look similar on the surface (both are
IDF-heap-fragmentation failures) but behave differently under a soft reset,
which itself may be worth someone's attention.

Net effect: T3's idle-recovery ladder (30s/60s/120s/300s) is moot for this
specific failure mode -- ~30 minutes of cumulative idle time across the T2
run never once cleared it on its own, so idle alone is not the answer here;
only the Dial-side reset was. (A *different*, shorter-lived station-level
stickiness *did* self-clear via idle alone earlier in this session -- see
the passive `stations=1` -> `stations=0` observation after ~85s, further up
this update -- so both mechanisms exist, at different timescales, and idle
recovery works for one but not the other.)

Given this, **the user's offered physical power-cycle is no longer needed to
answer T4's core question** -- a soft reset already answers it. It could
still be interesting as a separate check on whether repeated-arming heap
fragmentation reproduces identically after a genuine power-on (vs whatever
soft reset actually resets at the ESP-IDF level), but that's now a bonus
comparison, not a blocker.

**T6 (sel vs blocked), settled from data already in hand -- free.** Two
mid-transfer stalls captured during T2: `sent=7680/8208` frozen for 6s+ with
`sel=18` constant, and `sent=4096/8208` frozen for the full 30s window with
`sel=11` constant -- in both, `sel` never increments while the client sits
in `body`. Per the sparring partner's own decision tree, "sel flat while
client sits in body -> select() never offered it (loop or driver, not the
peer)". This kills H5 (peer link died mid-transfer) in favor of H14/H16
(the main loop or driver failing to re-signal writable), for these two
stalls specifically.

**T5 (one Dial vs two, wand-driven), compressed for time -- 2 cycles each
phase, not the full ~10:**
- Phase A (only Dial 1 armed, `apple_button`/5094): **2/2 failed**
  (`pull failed mid-transfer`, then `pairing failed -- giving up`).
- Phase B (both Dials armed): **2/2 failed**, identical outcome
  (`pairing failed -- giving up` both times, ~27s each) to Phase A. **No
  difference between one-Dial and two-Dial conditions** in this (small,
  time-boxed) sample -- Dial 1 failed 4/4 total regardless of whether Dial 2
  was armed. This does not support H1's co-channel/two-radio framing for
  this failure mode: a single already-fragmented Dial fails on its own, a
  second AP nearby neither caused nor worsened it in this sample. Sample
  size is small (2+2, time-boxed to under 10 minutes total for T5/T6
  combined) -- worth a larger run next session, but the direction is
  consistent with T4's mechanism (per-Dial heap fragmentation) rather than
  inter-radio interference.
- Notable even from Phase A alone: Dial 1 failing solo, with Dial 2 not even
  armed, means Dial 1 has *also* accumulated its own fragmentation over the
  session (it was armed continuously and served several pulls without a
  reset since the earlier fix) -- consistent with the T4 mechanism being a
  property of each Dial individually (heap fragmentation from repeated
  arm()/serve() cycles), not something that requires two Dials' AP traffic
  to interfere. This weakens H1's original "co-channel/two-radio" framing
  for *this* failure mode -- a single Dial run long enough will fail on its
  own, no second AP needed. Do not treat the earlier "N SP-FILEPUSH*
  visible" count as the deciding factor here without re-checking against a
  freshly-reset Dial 1, since one that's already degraded will fail
  regardless of what else is nearby.

**Session-wide correction to the running theory**: what looked like
"sticky state" across most of today's investigation (T2's 10/10 fails, T5's
Phase A 2/2 fails) is best explained by IDF-heap fragmentation accumulating
per-Dial across repeated arm()/serve() cycles within one long boot, clearable
by a soft reset (T4), not by anything the wand does, not by RTC-persisted
radio calibration, and not (based on Phase A alone) by a second Dial's
presence. The remaining open question is exactly how many arm()/serve()
cycles it takes before a given Dial degrades enough to fail, and whether
that count is materially different with a second Dial armed nearby --
Phase B's data (once complete) speaks to the second half of that.

**CANNOT be done without hands, collected here per the redirect's
instructions:**
1. Physical power-cycle recovery comparison (T4's power-on-arm case) --
   soft reset already clears the fragmentation, so this is now a bonus
   comparison (does a genuine power-on differ from a soft reset at the
   ESP-IDF level?), not a blocker. Offered by the user mid-session; not
   done since the soft-reset test answered the core question first.
2. Writing or tapping any NFC card (T2/T5's wand-side trigger is fully
   automated via pull_flag.py; only a literal physical tap is out of reach).
3. Swapping the Icon Display in -- not on the bench this session. Its
   `code_puller.py`/`main.py`/`pull_probe.py` changes from `c59638a` are
   unverified on real Icon Display hardware; only reasoned about from code.
4. T7 (concurrency, laptop `pull_bench.py` against one Dial while the other
   serves) was not attempted this session: it requires joining this Mac's
   own WiFi to the Dial's SoftAP, which the user has an explicit standing
   privacy preference against Claude doing autonomously (stated earlier
   this project: "I will switch the wifi to the dial when you tell me").
   Deferred to the user's own hands, not attempted silently.

**Tooling promoted out of scratchpad into the repo, per standing
instruction not to leave test tools uncommitted**:
`tools/devtests/sticky_state_bench.sh` and `tools/devtests/one_vs_two_bench.sh`
-- both non-interrupting (wait for the wand's own settle marker, never reset
mid-pull), both auto-recover from the wand's unrelated NFC Bad-ACK glitch
rather than idling out their safety cap. Not yet committed to git as of this
update -- next session should either commit them or fold in review feedback
first.

Continuing now with T2 (STICKY-STATE) through T7 per the current instructions,
unsupervised, at the corrected pace.

## Update 5: 95f684c (DEBUG_SERVE/DEBUG_PULL) deployed; Test 3 (stats.log) done;
## Tests 1/2 currently blocked

Deployed and verified `95f684c` to Dial 1, Dial 2, MockWand (Icon Display still
not on the bench). Builds cleanly on the earlier debug print, no conflicts.

**Blocker discovered immediately**: after redeploy+reset, BOTH Dials refused to
arm -- `# CodeServer.arm: AP start failed: WiFi Out of Memory`, reproduced 2x
each, including after an explicit disarm + 5s settle + retry. `gc.mem_free()`
was 82-84 KB free at the time (far above anything seen failing before), so this
is not Python-heap exhaustion -- `gc.collect()` already runs immediately before
the `_start_ap()` call. Reads as ESP-IDF-level WiFi driver resource exhaustion
that a software disarm/re-arm cycle cannot clear, after this session's very
large number of AP up/down cycles. This is itself on-theme (state that survives
a software-level reset cycle) but on the Dial's AP-bringup side rather than the
wand's join side. A full software reboot (`mpremote reset`, i.e. `esp_restart()`, not just a
Python-level disarm/re-arm) was tried on Dial 1 and did **not** clear it
either -- still `WiFi Out of Memory` on the very next arm attempt post-boot,
on a genuinely fresh boot (`up` in the single-digit seconds, first arm attempt
of that boot). A 5-minute idle wait before retrying also did not clear it.

**Correction, superseding the "sticky RTC state" read above**: since this
reproduces on a truly fresh boot (not just after a long session of cycling),
sticky/RTC-persisted radio state is the wrong explanation for *this specific*
failure. Ran a direct A/B: reflashed Dial 1 with the code_server.py from just
before `95f684c` (i.e. `9141482`, which already has the buffer-reuse +
widened-exception fix, just not the new debug dump) and, on a fresh boot,
**it armed successfully first try** (`free=68224` before, `free=63072` after
-- both comfortably clear). None of the new `95f684c` code actually executes
before or during `_start_ap()` (`_debug_dump`/`_stations`/etc. are all
downstream, in `poll()`/`_accept_new()`/`_finish()`), so this looks like a
heap-fragmentation regression from the module simply being bigger at import
time (977 vs 913 lines), not a logic bug in the new instrumentation's own
code path. **User is now working on a memory-side fix for this** rather than
this being treated as evidence for the core investigation.

Current bench state, left as a control pair: Dial 1 running the pre-`95f684c`
code (armed, working, SSID `SP-FILEPUSH-5094`); Dial 2 still on `95f684c`
(unarmed, still hits `WiFi Out of Memory`). Tests 1 and 2 remain blocked on
getting `95f684c`'s fragmentation issue fixed (or reverted) so the DEBUG_SERVE
output it provides is actually available to use.

**Test 3 (read /flash/stats.log) done** -- note the file lives on the Dial
(`stats_log.py`, `/flash/stats.log`), not the wand; the prompt's path was
probably shorthand. `stats.get` JSON gives only the success aggregate; pulled
the raw 200-line (trimmed) file from both Dials directly.

- **Dial 1** (`apple_button`): 143 lines match "fail", but **137 of them are
  `pull ? fail`** (slug unrecorded) packed into a ~35s burst with 100-800ms
  gaps -- far too fast to be real individual pull attempts. This is a
  pre-existing artifact from before slug-tracking existed in this log format,
  unrelated to the current multi-host work, exactly the case the prompt
  anticipated ("predates the multi-device work entirely"). Excluding it: only
  **5 real named-slug fails out of ~62 real attempts** (~8%) -- genuinely
  intermittent, not a wall of failures.
- **Dial 2** (`tilt_tones`): no artifact at all -- every one of its 30 log
  lines has a real slug, and since `tilt_tones` only existed on this Dial
  since this session, **all 30 are from today**. Raw count: **14 fails / 30
  attempts (~47%)** -- dramatically higher than Dial 1's real rate. This
  Dial-to-Dial asymmetry is new and worth chasing on its own; not yet
  explained by anything above (both Dials now run identical `code_server.py`;
  antenna fixes are wand-side, not Dial-side, so they don't differentiate the
  two Dials at all).

---

## Update 4: antenna fixes (7166071, fa9da73, 03073bc) deployed and tested

Merged and reflashed to the wand (Icon Display not on the bench this session,
still needs it). Both bugs verified as real and fixed on their own terms:

- **Bug 1 confirmed fixed**: boot log now reads `antenna: external (u.FL)`,
  not `internal (onboard)`. RSSI on the first join after reflash: **-22 dBm**,
  dramatically stronger than anything seen before this fix (prior best was
  roughly -33 to -45). Real, verified improvement.
- **Bug 2 confirmed *active***: the antenna line now reprints
  `external (u.FL)` before *every* join sub-attempt, including retries --
  previously it configured once and never again. The fix is deployed and
  doing what it's supposed to do.

**But Bug 2 does not fully explain the retry-association failures.** Two
separate test cycles after the fix:

1. First cycle: attempt 1 joined fine (rssi=-22) and got as far as the
   header, then stalled mid-body exactly as in Update 2/3 (still a live,
   separate mid-transfer stall, unaffected by the antenna fix, as expected --
   Bug 2 only touches the join/retry path, not an in-progress transfer).
2. Second cycle: **both join sub-attempts failed** (`STAT_CONNECTING` then
   `STAT_IDLE`) even with the antenna correctly reselected before each one
   and RSSI holding at a normal -33/-34 (not a degraded-antenna reading).
   This is the exact failure signature Bug 2 targeted, still reproducing
   with Bug 2's fix live and confirmed running.

Net: the antenna fixes are real, verified, and worth keeping, but they are
not the whole story -- something else can still fail the join itself
(distinct from the mid-transfer stall in Update 2/3), even with everything
Bug 1/2 fix in place. "Why 12+ automated `machine.reset()` cycles passed and
the power-cycle tap failed" is still open, as your partner flagged.

Still to do: reflash Icon Display once it's back on the bench (Bug 2 applies
to it too, per the corrected antenna note in 03073bc).

---

## Update 3: correction to Update 2's "always 4096" claim, plus a real symptom
## and two testing impairments

**Correction**: "sent freezes at exactly 4096" does not hold up across more
samples. Full set of stalls observed (Dial : game : byte offset frozen at /
total size): Dial 1 apple_button 4096/5113; Dial 2 tilt_tones 4096/8208,
7680/8208, 3072/8208, 3072/8208 (again, separate attempt). Every freeze
point is a multiple of 512 (the CHUNK size) -- structurally guaranteed,
since `sent` only updates on a fully-completed chunk, so a stall always
lands exactly on a chunk boundary. But *which* chunk varies (8th, 15th,
6th, 6th) -- not a fixed threshold. This argues against a fixed-size
buffer/window limit and fits better with something that can hit at
effectively any point in the transfer -- more consistent with intermittent
packet/ACK loss on the wand's radio side than a deterministic size-based
bug. Two consecutive sub-attempts of the same getcode tap both stalled,
at different offsets each time.

**New symptom, directly observed (not inferred from timestamps)**: the
user watched both screens live and confirmed the wand visibly begins its
*second* pull attempt while the Dial's own screen is still showing
"receiving" for the first (stale) client -- i.e. the Dial has not yet
reaped the client from the first stall by the time the wand retries. This
is now a directly observed fact, not just a timestamp-based inference from
the logs.

**Two testing impairments worth knowing about, separate from the bug
itself**: the server's 30s `SOCK_REPLY_TIMEOUT_S` deadline, and the wand's
own 2-attempt retry budget (each attempt potentially eating a full ~30s
stall before giving up), together make each reproduction cycle slow --
roughly a minute-plus per failing tap once both sub-attempts stall. This
is purely a diagnostic-velocity problem, not a symptom of the bug, but
it's worth the next person knowing about it, since it may be worth
temporarily lowering `SOCK_REPLY_TIMEOUT_S` (or the wand's own per-attempt
budget) for faster iteration while debugging, separate from whatever the
right production value is.

---

## Update 2: reproduced with instrumentation on a real wand failure -- decisive

Real hardware sequence (user's hands, no automation): wand physically power-cycled
(true power-off/on, not `machine.reset()`), then a real NFC getcode tap for
`apple_button@5094` -- the very first tap of this power cycle.

Wand side: joined `SP-FILEPUSH-5094` fine, connected, received the header
(5113 bytes expected), then `ETIMEDOUT` client-side after ~10.6s. Retried
(budget 2/2): could not even re-join (`STAT_CONNECTING` then `STAT_IDLE`),
gave up.

Dial 1 side (instrumented `code_server.py`, per-client state/sent/deadline
printed every 2s): during that same stall --

```
# DEBUG client state=body sent=4096/5113 ms_to_deadline=28753
# DEBUG client state=body sent=4096/5113 ms_to_deadline=26736
... (identical sent=4096/5113, deadline counting down normally, every 2s) ...
# DEBUG client state=body sent=4096/5113 ms_to_deadline=456
(then silence -- client reaped on deadline, no exception, no print, heartbeats resume)
```

`sent` frozen at exactly 4096 bytes (8 whole 512-byte CHUNKs) for the entire
~28s window, never advancing by even one more byte, while the deadline timer
itself ticked down correctly. No `MemoryError`, no exception of any kind --
the widened `except Exception` in `_advance()` (from `4bcbc5e`) never fired,
which it would have if that were the mechanism.

This rules out the memory-allocation hypothesis: that fix is live, and this
would have shown up as a caught-and-reaped exception with a printed reason.
Instead this is a genuine, live `sock.write()` stall -- the server has more
bytes ready and the socket refuses every further write for ~28s straight.
4096 is a suspicious number (a classic TCP/lwIP send-buffer size), which
points toward the *wand* simply ceasing to ACK data it already received,
not a Dial-side Python bug. The Dial kept faithfully retrying to send for
~28s server-side; the wand had already given up client-side at ~10.6s -- for
roughly 18s the Dial was pushing at a socket the wand had already abandoned.

Also notable: this was the *first* tap after this particular power-cycle,
not "the second" -- contradicts the user's earlier-recalled pattern that only
the second host ever fails. Worth treating "which host fails" as still open,
but "something about a wand power-cycle changes reliability" as the
part that's now solid.

Zero-hands caveat: this was NOT reproduced via `pull_flag.set_pending()` +
`machine.reset()` (12+ such automated cycles were all clean) -- only a true
hardware power-off/on before the tap reproduced it. The automated technique
exercises a different (and apparently insufficient) reset path.

---

## Update: co-channel isolation experiment result

Ran the recommended experiment: `pull_bench.py --n 1` looped 8x sequentially against
Dial 1, first with Dial 2 armed (beaconing `SP-FILEPUSH-004c` alongside Dial 1's
`SP-FILEPUSH-5094`), then with Dial 2 disarmed. Laptop WiFi (not the wand), both
Dials captured on serial throughout.

**Result: 16/16 pulls succeeded, both phases** (~0.7-2.2s each, `apple_button`,
5113 bytes). No failures from the laptop's WiFi chipset in either condition.

**New instrumentation added** (Dial's `code_server.py` only, not Box's copy):
`poll()` now prints each in-flight client's `state`/`sent`/`ms_to_deadline` every
2s while any client is active. During this run it logged 9 occurrences of the
existing `# CodeServer.poll: low mem (~29,000-29,400 free), deferring accept`
line (`MIN_FREE_ACCEPT` = 30,000) during the rapid back-to-back pulls -- real,
reproducible heap pressure under load, but it never produced a user-visible
failure here (pull_bench's 35s socket timeout absorbs a sub-second accept
delay).

Net: this result argues against simple co-channel RF contention being
sufficient on its own (a capable client sails through the identical
two-SoftAP environment every time), and points toward the problem being
wand-specific -- either the wand's radio/join behavior, or a server-side
condition that only a slower/weaker client radio triggers. The heap-pressure
finding is a real ingredient worth keeping in view, not the whole
explanation by itself.

---

# Task: sanity-check a hardware debugging trail (symptoms only, no theories yet)

You're being brought in as a second opinion on an intermittent hardware failure. A
prior session (not you) gathered the symptoms and log data below and formed some
working theories, but those theories are deliberately withheld from this prompt —
you're asked to look at the raw data fresh and form your own view before comparing
notes.

## Setup

- Repo: SmartPlayground, branch `Chat_to_Tap_Doggle`, working on top of commit
  `95898a1` ("Give each Broadcast host a per-device SSID identity for multi-host
  demos"). Full diff is available via `git show 95898a1` if useful.
- Read `Bag3/Code/HARDWARE_PROTOCOL.md` and
  `Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/README.md` before touching
  any hardware — this task involves live ESP32 devices on serial ports, and both
  docs have hard rules about that (ask before opening a port, never guess which
  port is which device, `resume` on every `mpremote` call, etc).
- Three physical devices, all just reflashed with the current tree and verified
  via read-back:
  - **Dial 1** — `broadcast_dial`, host_id `5094`, external Grove NFC reader,
    active game `apple_button` (present on this Dial before this session started;
    reportedly serving successfully "all morning" prior to the observed failures).
  - **Dial 2** — `broadcast_dial`, host_id `004c`, external Grove NFC reader,
    active game `tilt_tones` (a checked-in sample game, freshly loaded onto this
    Dial's `/flash/games/` this session via file copy + reboot + a `games.select`
    JSON command over serial, then armed into SERVE mode the same way).
  - **MockWand** — internal/onboard NFC antenna (confirmed from its own boot log:
    `antenna: internal (onboard)`).
- Both Dials confirmed via a serial `identify` JSON command to report distinct
  `host_id`s and distinct SSIDs (`SP-FILEPUSH-5094`, `SP-FILEPUSH-004c`), both
  `armed`/SERVE, both `payload_ready`.
- Querying `games.list` on both Dials shows identical storage shape for both
  games: one `<slug>.py` (+ optional `<slug>.tags.json`) under `/flash/games/`,
  merged into a device-side `index.json` at boot. No structural difference found
  between the pre-existing `apple_button` and the freshly-loaded `tilt_tones`.

## What is being tested

getcode NFC cards (written by hand on each Dial, not observed directly — only the
resulting wand behavior was captured) are tapped on the wand. Tapping queues a
pull request and reboots the wand; on the next boot the wand joins the tapped
host's SoftAP over WiFi and pulls that host's active game file over a raw TCP
socket (header: size + sha256 + name; then the body in 512-byte chunks; then a
2-byte OK/NO ack).

## Observed failures (from wand-side serial capture, `tools/serial_monitor.py`,
## passive/read-only)

### Instance 1 — `apple_button` from Dial 1 (`5094`)

Attempt 1/2:
```
found SP-FILEPUSH-5094 on ch=1 rssi=-45
joined SP-FILEPUSH-5094, ip=192.168.4.2
[XFER] connected to 192.168.4.1:8266
[XFER] requested 'apple_button' as '<v1>'
[XFER] receiving /games/apple_button.py, 5113 bytes expected
   ...(no further log lines for ~11s)...
[XFER] failed: [Errno 116] ETIMEDOUT
```

Attempt 2/2 (automatic, after the wand's own reboot-and-retry):
```
found SP-FILEPUSH-5094 on ch=1 rssi=-60
status seen while joining: STAT_CONNECTING (1001)
[XFER] join attempt 1/2 failed, status=STAT_CONNECTING (1001)
found SP-FILEPUSH-5094 on ch=1 rssi=-61
status seen while joining: STAT_IDLE (1000)
[XFER] join attempt 2/2 failed, status=STAT_IDLE (1000)
[XFER] scan saw 24 AP(s):
    SP-FILEPUSH-004c         ch=1 rssi=-40 sec=4
    SP-FILEPUSH-5094         ch=1 rssi=-61 sec=4  <-- wanted
    tufts_eecs               ch=1 rssi=-67 sec=3
    ... (21 more entries, mostly Tufts_* networks, channels 1/6/11, one
        unrelated SSID "Vayu Global Health" and one "ElucidateBio")
[XFER] join failed: could not join SP-FILEPUSH-5094 within 6s (status=STAT_IDLE (1000))
```

Dial 1's own serial output during this window (captured simultaneously): periodic
heartbeat only (`{"mem":..., "up":..., "type":"heartbeat"}` every 5s), memory
oscillating in the 47,328–50,368 byte range, no other lines printed, no drops.

### Instance 2 — `tilt_tones` from Dial 2 (`004c`), same wand, later in the session

Sequence as narrated by the user: the wand had just completed a successful pull
of `apple_button` from Dial 1, auto-launched into playing that game
("autoplay"), the user tapped a STOP tag to end that game, then tapped the
`tilt_tones` getcode card (Dial 2).

Attempt 1/2:
```
found SP-FILEPUSH-004c on ch=1 rssi=-37
joined SP-FILEPUSH-004c, ip=192.168.4.2
[XFER] connected to 192.168.4.1:8266
[XFER] requested 'tilt_tones' as '<v1>'
[XFER] receiving /games/tilt_tones.py, 8208 bytes expected
   ...(no further log lines for ~10.1s)...
[XFER] failed: [Errno 116] ETIMEDOUT
```
Attempt 2/2 began (`# pull mode: attempt 2/2 for 'tilt_tones' on host '004c'`) but
the capture window ended before it completed.

The user separately reported, from watching the Dial's own screen live (not from
a log capture): the Dial's SERVE screen was already showing its "receiving/
sending" state at the moment the second (retry) connection attempt began.

### User's own stated observations, verbatim intent preserved

- "the second attempts will ALWAYS fail."
- "the timeouts are out of sync."
- "the fail happens after a pull from a different dial" — i.e. the failure has
  so far only been observed on a getcode pull whose target host differs from
  whichever host was pulled from immediately before it in the same wand session.
- Reproduction recipe as described by the user: pull succeeds → wand
  auto-launches the just-pulled game → user taps a STOP tag → user taps a
  getcode card for the *other* Dial → that pull is the one that fails.
- The user recalled a separate, earlier (pre-dating this session) finding that
  the wand needs a reboot between using its ESP-NOW radio mode and doing a WiFi
  pull, in order for the pull to succeed.
- `apple_button` was reported by the user to have pulled successfully roughly 36
  times prior to this session's failures; the Dial's own `games.list` JSON query
  reports its lifetime `pulls` counter as `8`. This discrepancy is unresolved and
  unexplained — the two numbers were never reconciled.

## Longer free-run capture (~9 minutes per device, user testing unsupervised,
## included manual power-cycles of the wand and Dial 2)

- Dial 1: continuous heartbeat for the full window, memory oscillating
  43,936–50,992 bytes, no drops, no other printed lines, no crashes.
- Dial 2: heartbeat oscillating 40,080–51,120 bytes (a few brief dips into the
  40–45K range). One explicit event mid-window: `# serve aborted by EXIT`
  followed by `mode SERVE -> WRITE`, then a re-arm back into SERVE a few seconds
  later (`free=50368` before, `free=51104` after). Later in the window, the port
  dropped for two separate multi-second stretches
  (`[Errno 6] Device not configured`, then `[Errno 2] ... No such file or
  directory`) before reopening on its own; each reopening was followed by a full
  boot sequence (identity payload, `mode IDLE -> WRITE`, re-arm to SERVE). The
  user separately confirmed they physically unplugged the wand and a Dial "a
  couple of times" during this window to reset them.

## Deploy-tooling incident (during this session, separate from the pull-failure
## symptom above, included for completeness)

Mid-deploy to Dial 2, an interactive `tools/deploy.py` run was interrupted
(Ctrl-C) after several files failed with `mpremote`'s `TransportError: could not
enter raw repl`. After that, Dial 2 stopped responding to `mpremote` entirely on
that port until the user manually rewrote `boot.py` and `main.py` to the device.
`tools/deploy.py` was subsequently changed to write `boot.py`/`main.py` first, for
every device type, before any other file — that change is unrelated to the
pull-failure symptom above and is mentioned only in case it's relevant context.

## Confirmed, stated as fact rather than inference

- The diff introduced by commit `95898a1` to `code_server.py` (the file
  responsible for serving the TCP body to a requesting client, PEER-shared
  between Dial and Box) is limited to: computing `HOST_ID`/`SSID` once at boot,
  and one added `print()` statement at AP bring-up. The per-client transfer
  state machine in that file (accept/request/header/body/ack steps, the
  `SOCK_REPLY_TIMEOUT_S = 30` deadline, the `_Client` class) is byte-for-byte
  unchanged by this commit.

## What's being asked of you

Read the symptom data above (and pull whatever source files you need — this repo
is available in full) and form your own independent read on what's going on,
without being told the prior session's working theories. Report back:
1. What hypotheses does this data support or rule out, in your view?
2. What's the single most informative next experiment to run to distinguish
   between your top hypotheses, given the constraint that hands-on-hardware time
   (card taps, power cycles) is the user's own limited time, while port-level
   scripting/log capture can be done without asking?
3. Anything in the symptom list above that looks internally inconsistent or
   under-explained (e.g. the pulls-counter discrepancy) that's worth chasing on
   its own.
