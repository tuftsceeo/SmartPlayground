# Multi-client SERVE — hardware bench test plan (Dial **and** Box)

**For:** a Claude Code session with physical access to the Dial or Box + wand
hardware.
**Branch:** `Chat_to_Tap_Doggle`, from the merge of
`claude/multi-connection-code-servers-7n1bo6` into the v2 pull protocol
(hubtype + icon leg) — both devices now run the same multi-client server.
**Nothing in this change has run on real hardware yet.** Static checks and
off-device CPython harnesses only — see "What changed" below for what those
covered.

Run every test below on **both** devices. They run the same `code_server.py`
(bar heap comments and the Dial-only `prewarm_ap()`), but not the same radio,
heap budget or SERVE-mode glue, so a pass on one is not a pass on the other.
Where a step names a Dial-only gesture, the Box equivalent is the B1 hold.

## Read first

**`Bag3/Code/BroadcastBox/HARDWARE_PROTOCOL.md`.** It is written for the Box, but
every rule in it applies unchanged to the Dial + wand: the CDC/`mpremote` traps,
"ask which port, never guess," "ask before opening a port and wait for an explicit
go," the no-`exec`-on-a-live-board rule, `serial_monitor.py` usage, and the
"you cannot see the screen — every physical result comes from the user" section.
This plan does not repeat those rules; follow them as written. It only adds what's
specific to this change.

Also read `Bag3/Code/BroadcastDial/README.md`'s **"SERVE mode concurrency"**
section before starting — it has the design rationale for everything below.

## What changed, in one paragraph

`code_server.py` on **both** devices now serves up to 4 devices at once instead
of one at a time, via a non-blocking per-client state machine +
`select.select()`. The wire protocol on the wire is unchanged — a single wand
should behave exactly as before, and the v2 request frame (hubtype) and icon
leg an icon display pulls are carried inside the same state machine.
`bdial_server.py` and `bbox_server.py`'s SERVE-mode glue (event handling,
abort, error display) was rewritten to match.

Host-side, `BroadcastBox/tools/devtests/wire_test.py` and `wire_test_dial.py`
already cover the protocol and concurrency logic against both copies
(`wire_contract.py` holds the cases): v1/v2 requests, the icon leg, three
concurrent mixed-role pulls, a refusal beside live transfers, and abort. What
they cannot cover — and what this plan is for — is the radio, the heap, and
real wand timing.

## Known unknowns going in — check these first if anything fails to boot

- `select.select()` over raw sockets is new to this codebase's MicroPython side —
  unverified on this ESP32 port. A boot failure mentioning `select` is the first
  thing to suspect.
- `ap.config(max_clients=...)` (in `_start_ap()`) is best-effort and unverified;
  the boot log should show either silence (supported) or
  `# CodeServer: ap.config(max_clients=...) unsupported on this port` (guarded,
  not fatal).
- `MIN_FREE_ACCEPT = 30000` (bytes free heap required to accept a client beyond
  the first) is a starting guess, not a measured floor. Test 6 below exists to
  give it a real number.

## 0. Setup

1. **Ask which port is which board** (Dial vs. wand) before touching anything —
   do not infer from `ls /dev/cu.usbmodem*`.
2. Checkout the branch above; confirm `git log -1` shows the multi-client commit.
3. Confirm the working tree is clean (`git status`) before deploying.

## 1. Deploy

**Ask before opening the port; wait for "go."** Use `tools/deploy_dial.py`
(added 2026-09-21, after the batched one-shot `mpremote ... + reset` chain in
the README was found to silently drop a write on this board — see the
README's "Deploy" section for the finding):

```bash
python3 tools/deploy_dial.py $PORT
```

It copies one file per `mpremote` invocation, reads each one back to verify
the write actually landed, and retries a failed file. Its `--pause` between
files defaults to 8s (the value that worked in the session that found this
bug — not a confirmed minimum); if a file still fails verification, try a
larger `--pause`. If you use the batched block instead, verify file sizes
afterward — don't assume a silent success.

Capture the boot log with `serial_monitor.py` (path:
`Bag3/Code/BroadcastBox/tools/serial_monitor.py` — board-agnostic, just reads a
port):

```bash
python3 Bag3/Code/BroadcastBox/tools/serial_monitor.py /dev/cu.usbmodemXXXX 900 > run.log
```

Read `run.log` for the two unverified items above before declaring the boot good.

## 2. Single-wand regression — must pass before anything else

If this fails, stop here and report; nothing below will tell you anything useful.

1. Ask the user to put the Dial in SERVE (`DONE` + `ACT`).
2. Ask for one wand (real or MockWand) to pull the active game.
3. Watch `run.log` for the completed-serve line and `stats.log` growth; ask the
   user to confirm the wand's own screen/behavior showed success.

## 3. Concurrency proof — `tools/pull_bench.py` (no wand needed)

This step is host-drivable per `HARDWARE_PROTOCOL.md`'s "driving the boards
without a person" section — it needs a laptop joined to `SP-FILEPUSH`, not a
physical wand.

```bash
cd Bag3/Code/BroadcastDial/BDialFirmware
python3 tools/pull_bench.py --n 4
```

Confirm: 4/4 OK, correct SHA-256 per file, and the printed start/end windows
actually overlap (the script warns if they don't). If the user is watching the
Dial, ask them to confirm the screen showed a wand count ("N Wands") rather than
staying on a single-wand "Getting game..." label.

## 4. Stall isolation

```bash
python3 tools/pull_bench.py --n 4 --stall 1
```

Confirm the stalled client's connection is dropped around its ~30s deadline
while the other 3 finish normally and promptly (not delayed by the stalled one).

## 5. Abort gesture — needs a person

1. Start `pull_bench.py --n 4` in the background.
2. Ask the user to hold the encoder button (or tap CLOSE) mid-burst.
3. Confirm in `run.log`: every in-flight socket closes, the Dial leaves SERVE.
   If real wands were used instead of `pull_bench.py`, confirm each wand's
   `.part` file is gone (ask the user, or read it back if they can access flash).

## 6. Memory watch

During test 3's or 5's burst, watch the `heartbeat` JSON's `"mem"` field in the
JSON link output. Report the lowest value seen. **Do not change `MAX_CLIENTS` or
`MIN_FREE_ACCEPT` in `code_server.py` without asking first** — report the number
and let the user decide whether to tune it.

## 7. Mixed-slug check

Confirms the per-client `_lookup()` fix (the one real correctness bug this
rewrite had to close — two wands requesting different games must never
cross-contaminate).

Either:
- Run two `pull_bench.py` invocations concurrently with different `--slug`
  values (e.g. `--slug melody` and `--slug jump`, backgrounded together), or
- Ask for two real wands each set to a different active game.

Confirm each side receives **its own** correct file (name + hash), never the
other's.

## Reporting

- Report one line per numbered test: pass/fail, log excerpt, and — for anything
  judged by the screen or a physical gesture — what the user said they saw, not
  what you inferred. Follow `HARDWARE_PROTOCOL.md`'s "never report that something
  works" rule literally.
- On any failure: capture the log, stop, and report rather than attempting a
  fix without asking. Add logging that shows state at the point of failure
  (per `HARDWARE_PROTOCOL.md`'s "instrument before theorizing") before guessing.
