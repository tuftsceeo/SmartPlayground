# Broadcast Box — screen inventory

Build-accurate reference for design work: every screen the Box can show, what
each button does on it, which screens exist in code but are never reached, and
what is missing. Built from `bbox_ui.py` and `bbox_server.py`, verified against `a7afceb`.

Rendered version with true-scale screen mocks:
https://claude.ai/code/artifact/0d5d746e-d8c4-4f35-897d-d962d0eea44e

Screen bodies below are the literal text the device draws, in draw order.

## Constraints

**The canvas.** 240×135 px landscape colour LCD. Text starts at x=8, y=8 and
flows down; there is no layout engine, no wrapping, no scrolling widget. Five
type sizes only — 9, 12, 18, 24, 40 px (DejaVu); anything else silently falls
back, and in practice only 9/12/18/24 are used. About four 12 px rows fit under
a 9 px header; longer lists window around the cursor rather than scrolling.

**Palette.** Ground `#111111`, text `#FFFFFF`, muted `#888888`, accent
`#3FE0C2` (success / live), warn `#FF7A4A` (caution / off), amber `#FFA000`
used as a full-screen ground for transitions.

**Audio.** Four cues: click (every button), scan (card detected), success
(rising triad), fail (falling pair).

**Controls.** **A** = large front button (choose / scan / confirm), **B** =
small side button (next / back / dismiss). Every action is a press. Exactly one
hold exists in the product: A for 1 s to leave pickup mode. No touch, no third
input, nothing discoverable except from the screen.

## Screens that exist and are reachable

### S1 · Booting — `paint_booting`
Amber full-screen ground, black text. Transient, 5 s fixed.
```
Starting
```
| | |
|---|---|
| Entered | Power on / reset |
| Leaves | After the 5 s grace, to S4 or S2 |
| A / B | nothing |

### S2 · Idle, no game — `paint_idle`
```
Broadcast Box
linked to laptop          (accent; "not linked" in muted otherwise)
no game loaded yet
```
| | |
|---|---|
| Entered | Boot with no game on flash |
| Leaves | Only via a laptop upload, which reboots the Box |
| A / B | **nothing — IDLE reads no input at all** (see G2) |

### S3 · Mode change — `paint_mode_change`
Amber full-screen ground. Transient, **duration undefined** — lasts as long as
the radio switch takes.
```
-> SERVE
```
| | |
|---|---|
| Entered | Every WRITE ⇄ SERVE switch |
| A / B | nothing |
| Note | Developer language; see G8 |

### S4 · Card list — `paint_tag_list` — *home of WRITE mode*
```
BtnA=scan BtnB=next  pickup off     (9 px, warn)
> getcode  (2)
  jumpin   (0)
  DONE                              (accent)
```
| | |
|---|---|
| Entered | Boot with a game; return from any WRITE sub-screen |
| A | On a tag row → **S5**. On `DONE` → **S11** |
| B | Move cursor down, wrapping |

### S5 · Scanning — `paint_scanning`
**The only screen where the RF field is energized.**
```
Scanning: getcode
hold card on top                    (accent)
BtnB = back                         (9 px, muted)
```
| | |
|---|---|
| Entered | A on a tag row |
| A | nothing |
| B | Back to S4, field off |
| Card | Blank → S7 · same text → S10 · other text → S6 |
| Timeout | **none — waits forever with the field up** (see G1) |

### S6 · Overwrite? — `paint_overwrite`
The only destructive confirm in the product.
```
Card already has:                   (muted)
"melody"
Overwrite with "getcode"?           (warn)
BtnA = overwrite   BtnB = cancel    (9 px, muted)
```
| | |
|---|---|
| A | Write it → S7 |
| B | Cancel → S4 |

### S7 · Writing — `paint_writing`
Transient, blocking; duration varies (a MIFARE card is many block writes with a
30 ms settle each).
```
Writing "getcode"...
hold card steady                    (muted)
```
| | |
|---|---|
| Leaves | S8 on success, S9 on failure |
| A / B | nothing — the write blocks the loop |

### S8 · Written — `paint_written`
```
"getcode" written!                  (accent)
3 this session                      (muted)
press any button                    (9 px, muted)
```
| | |
|---|---|
| Sound | success |
| A / B | either → S4 |
| Dwell | stays until dismissed, no auto-advance |

### S9 · Write failed — `paint_write_failed`
```
Write failed                        (warn)
getcode                             (muted)
press any button                    (9 px, muted)
```
| | |
|---|---|
| Entered | Write, or read-back verify, failed |
| Sound | fail |
| A / B | either → S4 |
| Weakness | says nothing about why or what to try (see G5) |

### S10 · Already correct — `paint_already`
```
Already "getcode"                   (accent)
no change needed                    (muted)
press any button                    (9 px, muted)
```
| | |
|---|---|
| Entered | Card already carries the target text |
| A / B | either → S4 |
| Note | not counted in the session tally |

### S11 · Serving — `paint_serve`
```
Serving                             (accent)
SP-FILEPUSH
pickups: 0                          (muted)
hold BtnA to write tags             (9 px, muted)
```
| | |
|---|---|
| Radio | **AP up, reader unpowered** |
| A | **hold 1 s** → S4. A short press does nothing |
| B | nothing |
| Live | pickup count increments as wands download |

### S12 · Sending to a wand — `paint_receiving`
Transient, ~0.5 s for a typical 4.6 KB pull.
```
Getting game...
game                                (muted)
```
| | |
|---|---|
| Entered | A wand connects and starts downloading |
| A | hold 1 s aborts the transfer and exits to S4 |
| Copy bug | says "Getting game..." while the Box is *sending* (see G9) |

### S13 · Can't serve — `paint_error`
Centred warn text. Transient, 1.5 s fixed.
```
no game to serve
```
| | |
|---|---|
| Entered | `DONE` + A but the AP would not start |
| A / B | nothing |

### S14 · Transfer failed — `paint_error`
Centred warn text. Transient, 1 s fixed.
```
transfer failed
```
| | |
|---|---|
| Entered | A wand's download did not complete |
| A / B | nothing |
| Weakness | 1 s is easy to miss and nothing records it happened |

## Screens in the code that are never shown

Four paints survive from the pre-modal design with no caller. Worth deleting or
re-adopting rather than leaving to rot.

| Function | What it drew | Why orphaned |
|---|---|---|
| `paint_armed` | "Tag 1/1 · getcode · hold card on reader" | replaced by S4 + S5 |
| `paint_done` | "getcode done! · 1 of 1 written" | replaced by S8, which needed a dismiss action |
| `paint_complete` | "All tags ready!" | nothing tracks a target count any more (see G7) |
| `paint_no_pickup_hint` | "pickup off · DONE + B1 to serve" | folded into S4's header; the leftover still says "B1" |

## Gaps — missing screens

Ordered by whether a teacher can get stuck. G1–G4 are states the Box can be in
today with nothing on screen to explain them.

**G1 — Scanning has no timeout and no empty state.** *(blocking, costs power)*
S5 waits forever with the RF field on. Walk away mid-scan and the Box sits at
its highest WRITE-mode draw indefinitely, in a product whose whole purpose is
power. Needs an auto-return to S4 after ~20–30 s, and a "still waiting" cue
before that so *ready* reads differently from *stuck*.

**G2 — Idle is a dead end.** *(blocking)* S2 says "no game loaded yet" and then
neither button is read. It should say what to do ("connect to a laptop to load
a game"), and arguably one button should re-check flash rather than leaving a
teacher pressing a device that cannot respond.

**G3 — No screen when the card reader fails to start.** *(blocking)* The
failure prints to a serial port that is not attached in the field, and the Box
proceeds to WRITE as though fine; every scan then fails for a reason the screen
never gives. Needs a persistent "card reader not found" state that carries into
the card list.

**G4 — No screen for a wedged reader.** *(blocking)* After 15 consecutive read
errors the firmware silently reinitialises the reader. From outside, S5 simply
never finds a card. A "reader trouble — retrying" state makes an invisible
recovery something a teacher can wait out.

**G5 — Write failure doesn't say what to do.** *(quality)* S9 gives the tag
name and nothing else. Card lifted early, wrong card type and locked card want
different responses; at minimum "try again, hold it still".

**G6 — No acknowledgement that a wand picked up.** *(quality)* The count on S11
increments and that is all. A pickup is the moment the teacher is waiting for
and deserves a beat of its own — a highlight or a sound that registers from
across a playground.

**G7 — No sense of "enough cards written".** *(quality)* Counts rise forever
with no target. Either set an expected count per tag and show progress, or make
the counter clearly a running tally. `paint_complete` already exists for the
former and is unused.

**G8 — Mode-change screen is developer language, of unknown length.**
*(copy)* S3 shows `-> SERVE` for however long the switch takes. Should name the
destination in teacher words ("Starting pickup…"), and its duration should be
designed rather than incidental — it is the only signal that a slow switch is
progressing rather than hung.

**G9 — "Getting game…" is backwards.** *(copy)* S12 shows while the Box
*sends*. Should name the direction: "Sending to a wand".

**G10 — Leaving pickup mode can silently kill a download.** *(safety)* Holding
A during a transfer aborts a kid's download with no warning before and no
acknowledgement after. Either warn when a transfer is in flight, or confirm
afterwards that serving stopped.

**G11 — No battery, and no view of the Box's own state.** *(missing surface)*
Nothing shows power level, on a device whose defining bug is running out of it
and which is meant to be carried away from the laptop. There is also no
on-device view of firmware version, network name, reader status or last reset
cause — all of it lives on a serial link that is not attached in the field. One
status screen reachable from the card list would cover both.

## Two things to design around

**Button labels are burned into the screens.** Most screens spell out
`BtnA`/`BtnB` in their footer, and one orphan still says `B1`. Renaming the
buttons for teachers means editing copy in eight places, not one.

**Transient screens use four different clocks.** Fixed 5 s (boot), fixed 1.5 s
and 1 s (the two errors), duration-of-the-work (writing, mode change, sending),
and stay-until-dismissed (the three result screens). Worth deciding which of
those four behaviours each kind of message should have.
