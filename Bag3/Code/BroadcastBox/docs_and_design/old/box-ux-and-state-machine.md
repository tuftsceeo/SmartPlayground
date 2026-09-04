# Broadcast Box — how it works, and what a teacher actually does

Orientation for someone new to this system. No prior context assumed. Describes
the firmware at `85c1f16`. Card writing has been exercised on real hardware; the
power measurements it was built for have not been taken yet — see Status.

## The three things

| Thing | What it physically is | Its job |
|---|---|---|
| **ChatBroadcast** | A web app the teacher opens on a laptop | Author a small game in chat, then push it to the Box over a USB cable |
| **Broadcast Box** | An M5Stack StickS3 — a matchbox-sized ESP32 with a 240×135 screen, two side buttons, and an NFC reader on a Grove cable | Holds the game. Writes NFC cards. Hands the game to wands over its own WiFi |
| **Wand** | A kid-held ESP32-C6 with LEDs, a buzzer, an accelerometer and its own NFC reader | Reads cards. Fetches the game from the Box. Plays it |

Kids never touch the laptop. The Box is the bridge: it goes out to the
playground in a pocket, and everything after the upload happens without it.

## The one rule that shapes the whole design

> **The Box's WiFi and its NFC reader are never on at the same time.**

Both drawing at once browns out the board on a USB port — that's the bug this
design exists to fix. So the Box is *modal*: it is either writing cards **or**
serving code, never both. The teacher moves between the two with a button.

Everything below is a consequence of that rule.

## The Box's controls and screens

The unit has exactly two physical buttons, confirmed on hardware 2026-09-02:

- **Button A** — the large button on the front. The "do it" button: choose,
  scan, confirm.
- **Button B** — the small button on the side. The "next" button: scrolls the
  list, and backs out of whatever screen you are on.

**Every action is a plain press.** The one exception is leaving pickup mode,
which needs a one-second hold on A — deliberately, so a bump in a bag cannot
take the WiFi down mid-lesson.

The 240×135 screen always names the current mode and sub-screen, so there is no
hidden state.

## The teacher's walkthrough

**1 — Write a game.** In ChatBroadcast on the laptop, describe the game you
want. You get code and a preview.

**2 — Plug in the Box.** USB cable, laptop to Box. The app shows connected.

**3 — Send the game.** One click. The app writes the game onto the Box's
storage and restarts it. Takes a few seconds.
*Underneath: the app drives the Box's Python prompt directly and reboots it —
the Box's own program isn't running during the transfer.*

**4 — Write the NFC cards.** The Box comes back showing a list:

```
WRITE - pickup off (DONE+A)
> getcode  (0)
  jumpin   (0)
  DONE
```

You need at least two cards per game:
- a **`getcode`** card — the one a kid taps to fetch the game
- a **`jumpin`** card — the one a kid taps to start playing it

Press **B** to move the cursor down the list. Press **A** on the card you want
to write and the Box switches to a scanning screen with the reader powered:
touch a card to it and it writes, beeps, and shows the result. Press either
button to return to the list. Make duplicates by scanning again — a class needs
several of each.

Three things can happen when a card meets the reader:
- **Blank card** → written straight away, then a result screen.
- **Already says the right thing** → the Box says so and leaves the card alone.
- **Says something else** (an old game's card) → the Box asks first. **A**
  overwrites it, **B** backs out without writing.

The reader is powered only on the scanning screen — not while you are reading
the list or a result. WiFi is off for this entire step; wands cannot fetch code
yet, and the top line says so.

**5 — Switch to pickup mode.** Press **B** until the cursor reaches `DONE`,
then press **A**. The reader switches off, the Box's WiFi comes up, and the
screen changes to:

```
Serving
SP-FILEPUSH
pickups: 0
hold A to write tags
```

The Box is now a tiny WiFi hotspot with the game on it. You can unplug it and
carry it to the playground.

**6 — A kid fetches the game.** Tap a wand on the `getcode` card. The wand
beeps, restarts itself, joins the Box's WiFi, downloads the game, and restarts
again into it. **This takes roughly 20–30 seconds and involves two visible
reboots — that is normal, not a fault** (see below). The Box's pickup counter
goes up.

**7 — Kids play.** Tap a wand on the `jumpin` card to start the game. Cards for
other games switch between them.

**8 — Change the game.** Hold **A** for a second: WiFi drops and you're back
at the card list. Or plug back into the laptop and send a new game, which puts
you back at step 3.

## Why the wand reboots twice

It looks broken and isn't. The wand's radio can only do one thing at a time —
either its wand-to-wand messaging (ESP-NOW) or joining WiFi — and once the
messaging has run, joining WiFi fails, reproducibly. There is no way to reset
that from the wand's software.

So the wand doesn't try. Tapping `getcode` makes it write a note to itself and
restart. On the way back up, *before* touching the messaging radio, it sees the
note, joins the Box on a clean radio, downloads the game, and restarts once more
to run it. Tested 4/4 in the field. Anyone changing wand code needs to leave
that ordering alone.

## The Box's state machine

```
                  ┌──────────────────────────────────┐
   power on ──►   │  no game on flash?  →  IDLE      │
                  │  game on flash?     →  WRITE     │
                  └──────────────────────────────────┘

  ┌────────────────────── WRITE ───────────────────────┐
  │  WiFi: OFF     Reader: on only on the scan screen  │
  │                                                    │
  │   MENU ──A──► SCAN ──card──► RESULT ──A or B──┐    │
  │    ▲  │        │  ▲             ▲             │    │
  │    │  B        B  └── A ── OVERWRITE?         │    │
  │    │  (next)   (back)          (B backs out)  │    │
  │    └───────────────────────────────────────────┘   │
  │                                                    │
  │   MENU + cursor on "DONE" + A  →  SERVE ─────┐     │
  └──────────────────────────────────────────────┼─────┘
                     ▲                           ▼
                     │            ┌───────── SERVE ──────────┐
     hold A for 1s ──┘            │  WiFi: ON  Reader: OFF   │
                                  │  wands download the game │
                                  └──────────────────────────┘

    laptop sends a new game → Box restarts → back to WRITE
```

| Mode | WiFi | NFC reader | Screen |
|---|---|---|---|
| `IDLE` | off | off | "no game loaded yet" |
| `WRITE` | **off** | on only on the scan screen | list / scanning / overwrite? / result |
| `SERVE` | **on** | off — not even powered | "Serving" + pickup count |

The two energized states are mutually exclusive by construction: every mode
change runs through one function that switches the old mode's hardware off
before switching the new mode's on.

## Design decisions a newcomer will wonder about

**Why doesn't the Box just always serve?** It used to. Having WiFi and the
reader both live is what browns the board out. Requiring a deliberate `DONE` +
A is the cost of the fix — and it means a Box in a bag isn't broadcasting.

**Why a separate scanning screen instead of scanning all the time?** The
reader's radio field is most of its power draw. Giving scanning its own screen
means the field is up only while a teacher is deliberately holding a card to
the Box, and down again the moment the result appears.

**Why presses rather than press-and-hold?** An earlier draft gated scanning on
holding a button down. On hardware that turned out to be worse: it occupies the
hand that also has to hold the card steady, and it made the overwrite confirm
ambiguous. The rule now is that every action in the card flow is a plain press,
and the only hold left in the firmware is leaving pickup mode — rare, and worth
protecting from a stray bump.

**Why does a MIFARE card sometimes stop being detected?** It used to, and the
cause is worth knowing: authenticating to a MIFARE Classic card latches the
reader into encrypted mode, and while that latch is set the reader will not
answer the plain query that detects a card at all. Toggling the antenna does not
clear it — only an explicit reset does. That is why, before the fix, the first
scan after boot was the only one that worked. Every scan now clears the latch
before starting.

**Why only two card names?** Phase A keeps the exact card text today's wands
already recognize (`getcode`, `jumpin`). Named games — `getcode:melody` and a
matching `melody` card — need a matching change on the wand and are the next
phase.

## Where this lives in the code

| File | Role |
|---|---|
| `BBoxFirmware/bbox_server.py` | The mode machine — everything above |
| `BBoxFirmware/bbox_ui.py` | The screens |
| `BBoxFirmware/buttons.py` | Button A/B reads and the one hold timer |
| `BBoxFirmware/card_writer.py` | Reading and writing NFC cards |
| `BBoxFirmware/code_server.py` | The WiFi hotspot and the file handover |
| `BBoxFirmware/reset_log.py` | Records why the Box last restarted |
| `MockWand/main.py`, `code_puller.py`, `pull_flag.py` | The wand side, including the two-reboot sequence |
| `ChatBroadcast/` | The laptop web app |

## Status

**Card writing works on hardware.** The button layout is confirmed, the card
flow has been exercised, and the encrypted-mode bug above was found and fixed
by running it.

**The power result this was all built for is still unmeasured.** Two things
remain open, both listed in `design/phase-a-handoff.md`: whether the Box's WiFi
comes back reliably after being switched off and on within one power cycle
(the `probe_ap_cycle.py` bench test, not yet run), and whether splitting the
modes actually stops the resets — which needs the Box run in each mode with the
reset cause read back on the following boot.
