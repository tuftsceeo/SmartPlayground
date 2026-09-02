# Phase A handoff — T7 + finalization

For the agent picking up T7, T8 and the hardware verification. Everything
here is as of `44560ce` on `claude/broadcast-box-exploration-7f9qs8`.

Companion documents, in reading order:
- `design/phase-a-box-power-modes.plan.md` — the plan being executed, with the
  frozen interfaces, the radio contract and the per-task acceptance criteria.
- `design/2026-09-01-power-modes-and-fsm.md` — the FSM design this phase is
  the first slice of.
- `BBoxFirmware/known_issue.md` — the failure being chased and the hypotheses.

## Why this work exists

The Box browns out on a current-limited USB port. Until Phase A, a game on
flash meant the SoftAP **and** the NFC reader were both energized, at boot,
indefinitely: `run()` called `_try_arm()` unconditionally, which raised the AP
and enabled card writing together. The PN532→WS1850S swap (~150 mA → ~30 mA
read burst) and the G11 field gate lowered the peaks without removing the
overlap.

Two hypotheses remain live and unseparated (`known_issue.md`): **H1** a
brownout from charge current stacked on the always-on load, **H2** a watchdog
reset from a `SoftI2C` stall on the reader. Unplugging the reader on
2026-09-01 took the box from a 30 s–2 min reset cycle to 73 s+ clean uptime,
but that removes the RF draw and the I2C path together, so it cannot tell H1
from H2.

**Phase A's objective is therefore two things at once:**

1. Make the box modal so the invariant holds — *at most one of {WiFi AP, NFC
   RF field} is energized at any instant* — which is the fix if H1 is real.
2. Add reset-cause logging, so that running the box in each single-subsystem
   mode and reading the cause on the next boot finally separates H1 from H2.
   A `BROWNOUT`/`PWRON` in one mode but not the other is the measurement that
   has been missing all along.

Nothing in Phase A is proven on hardware yet. That is what remains.

## The teacher-facing outcome

Box modes and the gestures that move between them (B1 = G11, B2 = G12):

| Mode | AP | Reader | How you leave it |
|---|---|---|---|
| `WRITE` | down | on only while B1 held | cursor to `DONE`, press B1 → `SERVE` |
| `SERVE` | up | antenna off, no I2C at all | hold B1 ≥1 s → `WRITE` |
| `IDLE` | down | off | no game on flash; nothing to do |

In `WRITE`, B2 scrolls the list `getcode → jumpin → DONE`. Holding B1 with a
card on the reader writes the selected entry; a card already carrying that
text is reported rather than rewritten; a card with different text raises an
overwrite prompt that commits only if B1 stays held 1 s **after the prompt
appears**. The box no longer serves code until a teacher chooses `DONE` + B1 —
that is a deliberate behavior change, and the `WRITE` screen says so.

## State: done vs remaining

| Task | State | Commit |
|---|---|---|
| T1 `probe_ap_cycle.py` | **written, NOT RUN** | `d1cc3ef` |
| T2 `reset_log.py` | done, reviewed, fixed | `9b86d4c` + `1adeed1` |
| T3 `code_server.py` | done, reviewed, fixed | `54d4c9d` + `1adeed1` |
| T4 `bbox_ui.py` | done, reviewed, fixed | `40ffba7` + `1adeed1` |
| T5 `buttons.py` | done, reviewed, fixed | `4c8525a` + `1adeed1` |
| T6 `bbox_server.py` mode machine | done, stub-tested | `44560ce` |
| **T7 manifest + README** | **not started** | — |
| **T8 guardrail audit** | partially done in `44560ce` | — |
| **Hardware verification** | **not started** | — |

T6 was verified against a CPython stub harness — 48 checks, 17 scenarios, with
the AP/reader invariant asserted on every loop iteration. That proves the state
machine's logic, not the hardware.

## T7 — what to do

**`BBoxFirmware/manifest.js`.** Add `buttons.py` and `reset_log.py` to
`BOX_FILES`. Leave `probe_ap_cycle.py` and `probe_stick.py` out — bench tools,
not firmware.

**This is a release blocker, not a tidy-up.** `bbox_server.py` now does
`import reset_log` and `from buttons import Buttons` at module scope. Any box
flashed through `manifest.js` without those two entries fails at boot with an
ImportError, and `main.py`'s handler prints a `fatal` JSON — a bricked-looking
box. Nothing can be hardware-tested until this lands or the two files are
copied by hand.

**`BBoxFirmware/README.md`.** Replace the button row of the hardware table
with B1 = G11 / B2 = G12 and their gestures; document the three modes and the
mutual-exclusion invariant; state plainly that the box does not serve code
until a teacher selects `DONE` + B1. Describe current behavior only — no
development narrative, and no power claims that have not been measured.

## T8 — guardrail audit

Most of this ran in `44560ce`; re-run it after T7 and after any hardware fix.

- `git diff --stat <base> -- Bag3/Code/BroadcastBox/MockWand/` must be **empty**.
  The wand's ESP-NOW/WiFi sequence is hardware-validated (4/4 field test,
  commits `cfed7a4` and `c6f0716`) and out of scope for this whole round. The
  plan's **GUARDRAIL** section lists the four files and the ordering
  invariants they encode; read it before touching anything.
- `code_server.py` against the plan's frozen wire table, row by row: SSID
  `SP-FILEPUSH`, password `playground1`, port 8266, channel 1, 512/20 ms
  chunking, dest name `jumpin.py`, the `size(4B BE) | sha256(32B) |
  name_len(1B) | name` header, the 2-byte `OK`/`NO` ack. Changing any row
  breaks the wand silently.
- `TAG_LIST` in `bbox_server.py` must contain only text the current wand
  matches by exact set membership. Verify by importing the wand's own module
  rather than by eye:
  ```bash
  cd Bag3/Code/BroadcastBox/MockWand/lib
  python3 -c "import sys; sys.path.insert(0,'.'); import opcodes; print('jumpin' in opcodes.GAME_TAGS)"
  ```
  `getcode` lives in `main.py`'s `BROADCAST` set. Both currently check out.

## Hardware etiquette — read before opening any port

1. **Ask which board is on which port.** Ports change between sessions.
   `/dev/cu.usbmodem3101` (box) and `/dev/cu.usbmodem101` (wand) are examples
   from previous sessions, not fixtures. Never infer a port from a doc — this
   one included — and never guess from an `ls /dev/cu.*` listing: the two
   boards enumerate as sibling names, and hitting the wrong one at best wastes
   a trial and at worst resets a board mid-measurement.
2. **Ask before opening a port and wait for confirmation** that nothing else
   holds it. ChatBroadcast holds the box's port over WebSerial when connected.
3. **Every `mpremote` command resets the box**, and it boots in >20 s. Batch
   what you need into one `exec`.
4. `REBOOT_PULL_PLAN.md` says "Box: no serial access" — that described that
   session's standalone setup, not a hardware limit. The box is reachable for
   bench work; the README's deploy path depends on it.

## Verification, in order

Steps 3 onward need T7 landed (or the two modules copied by hand).

1. **T1, both halves.** Box: `probe_ap_cycle.run()` — 10 cycles, AP left up on
   the last as a hand-off. Wand, against that live AP:
   `code_puller.pull(verbose=True)` on a cold radio. A box-side 10/10 alone is
   **not** a pass: the failure being tested for is the wand's measured *"AP
   visible at good rssi but join times out"*, in which `ap.active()` reads True
   and a socket binds fine. Only a completed join distinguishes them. Void-trial
   rule applies — if the wand never sees `SP-FILEPUSH` in its scan, that trial
   says nothing; re-run it.
   - Both halves pass → in-place AP cycling stands as implemented.
   - Either fails → switch `_set_mode()` to write a mode flag and
     `machine.reset()` into the new mode (the wand's proven bracket). It is
     deliberately the only method that would change; cost is a >20 s boot per
     switch.
2. **Side keys.** `probe_ap_cycle.check_side_keys()` — confirm G11/G12 really
   are the small side buttons and report which is which. Still unverified, and
   T6's whole input model rests on it. If they are elsewhere, `buttons.py`
   needs two constants changed; if they do not exist, B1 fails open (cards
   still writable) and `M5.BtnA` long-press is the overwrite confirm.
3. **Screens.** `bbox_ui.demo()` — all screens legible at 240×135, especially
   `paint_tag_list`'s header plus four rows.
4. **WRITE mode, 10 min on USB**, B1 tapped occasionally to write. Then
   `reset_log.last()`.
5. **SERVE mode, 10 min on USB.** Same reading. **A reset in one mode but not
   the other is the H1/H2 discriminator this phase exists to produce.**
6. **Round trip.** Write `getcode` + `jumpin` cards in WRITE → `DONE` + B1 →
   SERVE → wand taps `getcode` → wand reboots, pulls on a cold radio, reboots
   into the game. This is the proof the wand path is untouched.
7. **Exit under load.** Hold B1 during a transfer. Note that a real ~4.6 KB
   pull is only ~180 ms of chunk yields, so a 1 s hold cannot complete inside
   one `poll()`: the transfer finishes and the mode switch happens after it.
   That is intended — no wand loses a pull to a gesture it could not have
   finished. The mid-transfer abort exists for a stalled client holding the
   socket toward the 30 s reply timeout.
8. **Repeat cycle.** WRITE → SERVE → WRITE → SERVE with no reboot, then a wand
   pull on the second SERVE. This is the case step 1 predicts; confirm the
   prediction on the real path.

## Open risks

- **In-place AP cycling is unvalidated** (step 1). The first `tags → wifi`
  transition after a boot is clean regardless; the risk is a repeat cycle
  within one boot.
- **G11/G12 assumed, not verified** (step 2).
- **H2 is untouched by Phase A.** The reader is still driven over
  `machine.SoftI2C` with no clock-stretch timeout. If step 5 reports `WDT`,
  the mode split is not the fix and the next round is the I2C path.
- **Phase A regresses field behavior on purpose.** A box carried to the
  playground boots into `WRITE`, so a wand tapping `getcode` before the
  teacher selects `DONE` + B1 burns its two-attempt budget (~31 s each) and
  error-blinks. Worth watching in step 6 for whether the UI makes this
  obvious enough in practice.

## Out of scope

Named games and `/flash/games/`, the `GET <name>` protocol, `getcode:<name>`
card text, wand dynamic dispatch, any ChatApp change, and a `SERVE` idle
timeout. All Phase B or later; the plan's final section lists them.
