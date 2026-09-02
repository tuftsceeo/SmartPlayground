# Broadcast Box — how it works, and what a teacher actually does

Orientation for someone new to this system. No prior context assumed. Describes
the Phase A design as implemented (`44560ce`); the hardware verification run has
not happened yet, so read this as "what the code does", not "what has been
proven on a bench".

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

Two small buttons on the side:

- **B1** (pin G11) — the "do it" button: hold to scan/write a card, press to
  confirm a choice.
- **B2** (pin G12) — the "next" button: scrolls through the list of cards to
  write.

The 240×135 screen always shows which mode the Box is in, so there is no hidden
state. `M5.BtnA`, the big button on the front, is a fallback confirm if the side
buttons turn out not to work.

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
WRITE - pickup off (DONE+B1)
> getcode  (0)
  jumpin   (0)
  DONE
```

You need at least two cards per game:
- a **`getcode`** card — the one a kid taps to fetch the game
- a **`jumpin`** card — the one a kid taps to start playing it

Hold **B1** and touch a blank card to the reader: it writes, beeps, and the
count goes up. Make duplicates by tapping more cards — a class needs several.
Press **B2** to move to the next card in the list.

Three things can happen when a card touches the reader:
- **Blank card** → written immediately.
- **Already says the right thing** → the Box tells you and leaves it alone.
- **Says something else** (an old game's card) → the Box asks before
  overwriting. Keep holding B1 for one more second to confirm; let go to cancel.

WiFi is off this entire time. Wands cannot fetch code yet, and the screen says
so on the top line.

**5 — Switch to pickup mode.** Press **B2** until the cursor reaches `DONE`,
then press **B1**. The reader switches off, the Box's WiFi comes up, and the
screen changes to:

```
Serving
SP-FILEPUSH
pickups: 0
hold B1 to write tags
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

**8 — Change the game.** Hold **B1** for a second: WiFi drops and you're back
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

    ┌──────────────────── WRITE ─────────────────────┐
    │  WiFi: OFF        Reader: on only while B1 held│
    │                                                │
    │  B2            → next card in the list         │
    │  B1 + card     → write it (or ask, or report)  │
    │  B1 on "DONE"  → SERVE ─────────────────┐      │
    └─────────────────────────────────────────┼──────┘
                        ▲                     ▼
                        │        ┌────────── SERVE ───────────┐
      hold B1 for 1s ───┘        │  WiFi: ON   Reader: OFF    │
                                 │  wands download the game   │
                                 └────────────────────────────┘

    laptop sends a new game → Box restarts → back to WRITE
```

| Mode | WiFi | NFC reader | Screen says |
|---|---|---|---|
| `IDLE` | off | off | "no game loaded yet" |
| `WRITE` | **off** | on only while B1 is held | the card list |
| `SERVE` | **on** | off — not even powered | "Serving" + pickup count |

The two energized states are mutually exclusive by construction: every
transition runs through one function that switches the old mode's hardware off
before switching the new mode's on.

## Design decisions a newcomer will wonder about

**Why doesn't the Box just always serve?** It used to. Having WiFi and the
reader both live is what browns the board out. Requiring a deliberate `DONE` +
B1 is the cost of the fix — and it means a Box in a bag isn't broadcasting.

**Why hold B1 to scan instead of scanning continuously?** The reader's radio
field is most of its power draw. Held-to-scan means it is off except in the
second or two a card is actually being written.

**Why is confirming an overwrite a *longer hold* rather than a second button?**
Two buttons were already spoken for. The confirm window is measured from when
the prompt appears, not from when the button went down, so a teacher who is
already mid-hold still sees the prompt for a full second before anything is
overwritten.

**Why only two card names?** Phase A keeps the exact card text today's wands
already recognize (`getcode`, `jumpin`). Named games — `getcode:melody` and a
matching `melody` card — need a matching change on the wand and are the next
phase.

## Where this lives in the code

| File | Role |
|---|---|
| `BBoxFirmware/bbox_server.py` | The mode machine — everything above |
| `BBoxFirmware/bbox_ui.py` | The screens |
| `BBoxFirmware/buttons.py` | B1/B2 debouncing and hold timing |
| `BBoxFirmware/card_writer.py` | Reading and writing NFC cards |
| `BBoxFirmware/code_server.py` | The WiFi hotspot and the file handover |
| `BBoxFirmware/reset_log.py` | Records why the Box last restarted |
| `MockWand/main.py`, `code_puller.py`, `pull_flag.py` | The wand side, including the two-reboot sequence |
| `ChatBroadcast/` | The laptop web app |

## Status

Written and logic-tested; **not yet verified on hardware.** Open questions are
listed in `design/phase-a-handoff.md` — chiefly whether the Box's WiFi comes
back reliably after being switched off and on within one power cycle, and
whether the two side buttons are really on the pins this assumes.
