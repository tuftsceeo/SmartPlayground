---
title: Multi-controller test plan — data for the device-list, Find Me and grouping design choices
date: 2026-11-18
status: draft (waiting on the questions at the end)
related:
  - Bag3/Code/docs_and_design/2026-11-18-stress-test-debrief.md
  - Bag3/Code/known_issues/2026-11-18-stress-test-find-and-scan.md
---

# Multi-controller test plan, 2026-11-18

This plan is arranged by the **design decision** each test informs, not by complaint. Each
test gives the decision it informs, the setup, whether someone must be present, how long it
takes, and which result points which way.

## What a single Dial already showed (2026-11-18, 17 devices)

Details and numbers are in the debrief.

- **One Dial scanning quietly gets a complete list.**
  - 60 scans at 10 s or 6.5 s gaps: 17/17 in 57 of them, 16 in the other 3.
  - Replies were lost in fewer than 1% of cases, so the Dial's receive buffer is not the
    limit at this size.
- **Frequent polls silence most devices.**
  - With a poll every 1 s or 0.5 s, only the 2–4 devices with the shortest reply wait
    (0.4 s) answered while polling went on.
  - The rest answered only once polling stopped.
  - Every 2 s, the devices with the longest wait start to drop out.
- **Random scan times reproduce the room.**
  - Mean gap 1.3 s: each 6 s list held 3–17 devices (median 12).
  - Mean gap 2.1 s: 9–17 (median 16).
- **Only 4 reply slots are in use.** Every MAC's last byte is a multiple of 4, so
  `% 16` gives slots 0, 4, 8 and 12 only.
- **Find Me restarts three times.** It reached its wand 6 times out of 6. The Dial sends 3
  copies, though, and each one restarts `finddevice`: start → stopped 0.2 s later → start →
  stopped → then the 5 s identify, about 2 s after the press.
- **What triggers a scan in the app.**
  - Opening Distribute after a Send (the Dial reboots, then scans).
  - The Rescan button.
  - A short list invites Rescan, and Rescan makes the next list shorter: a feedback loop.

**What one Dial cannot show.**
- Polls from several independent radios.
- Several controllers' scan windows overlapping.
- Pulls and scans competing for airtime.
- Devices in the middle of a game.

## Tests

### T1 — Real multi-controller scan contention (unattended, ~15 min)

**Decides:**
- Is fixing reply scheduling enough for a usable list?
- Or does each controller need its own **roster** (tap-to-join, or a group ID)?

**Setup.**
- 2 Dials and 1 Box, each on its own USB port.
- One host script holds all three ports, so every event shares one clock.
- Before starting, confirm with `identify` that each one has `fleet`.
- All controllers idle on a menu screen with the radio up.

**Runs.**

| Run | Pattern | Duration |
|---|---|---|
| a | Controllers take turns, never overlapping. Baseline per controller. | 3 min |
| b | Each scans at random times, mean gap 20 s each (calm room). | 4 min |
| c | Each scans at random times, mean gap 8 s each (people pressing Rescan). | 4 min |
| d | All three scan within the same 0.5 s, 10 times (everyone sent at once). | 2 min |

**Measures.**
- Per controller and per scan: devices listed out of 18, and which reply slots they were in.
- Whether one controller's list fills from replies to another's poll. Replies are broadcast,
  so overlapping windows should *share* replies.

**Reading the result.**
- **Lists stay complete in b and c:** contention is mild with 3 radios. The room's 8
  controllers would then need testing with more controllers or a simulation.
- **Lists collapse in c or d as in the single-Dial storm:** reply scheduling is the cause,
  and the firmware fix in T5 is worth trying.

### T2 — Scan + pull contention (attended block, ~10 min)

**Decides:**
- Why the card-tap pull survived the room when the list did not.
- Whether the **tap path can carry identity and grouping** (tap-to-join) under load.

**Setup.**
- Same 3 controllers, with T1 run (c) running in the background.
- Dial A distributes a small game to 4 bench wands while B and the Box scan.
- Then you tap 4 wands on Dial B's game card, one at a time, about 10 s apart.

**Measures.**
- Pull time and success for each pushed and each tapped wand.
- List completeness on the other controllers while pulls run.
- Whether pulls fail with `busy` or `timeout`, or just slow down.

**Reading the result.**
- **Taps succeed while scans fail:** directed, one-device messages hold up in a busy room.
  This supports a roster or tap-to-join, and status sent to known devices instead of a
  broadcast.
- **Taps also degrade:** airtime is the limit, and RF channels or groups move up.

### T3 — Mid-game reachability (attended setup ~5 min, then unattended ~8 min)

**Decides:**
- Can any radio-based identify reach a wand mid-game? That covers a non-destructive Find
  that only blinks, and status replies from inside a game.
- Or is identify-by-tap the only reliable path?

Not re-testing that Find ends a game; that is recorded.

**Setup.** You start a different game on each of 6–8 wands: a lobby game, a Splat host
game, a sound or animation-heavy game, a simple colour game. They are left running.

**Runs.**
- Single quiet scans, 20 of them, 10 s apart.
- Per device: answered or not, and how late.
- Optional: Find on the two USB-logged wands only, each running a game. This times when the
  game exits and Find starts.

**Reading the result.**
- **Most games answer:** a blink that does not stop the game, handled in `poll()`, would
  reach most wands. Fix Find in firmware.
- **Many games are silent:** the radio cannot reliably reach a playing wand. Identify must
  work by tap, or by a sticker ID plus the running game shown in status.

### T4 — Cheap one-offs (during setup)

- **Box USB identity.** Read the Box's USB VID/PID and product string with
  `list_ports`, as already done for the Dial and wands.
  - Dial: `303a:81dd`, "Dial(UiFlow2)".
  - Wand: `303a:1001`, serial number = MAC.
- **The Chrome picker.** Have someone open it once and note what it lists. Chrome's
  picker is what users see, not `list_ports`.
- **The 18th device.** You count 18 and the Dial hears 17. Identify which one never answers,
  for example by checking which device has no status provider.

### T5 — Firmware A/B on 3–4 wands (proposal only; code change, needs your yes)

**Decides:** whether the scheduling fix alone removes the roulette. It is the only
*decisive* test of that fix.

**Change, on a few bench wands only.**
- A repeat poll does not reset a pending reply.
- The slot comes from more MAC bits or a random jitter, not the last byte `% 16`.
- Find copies are de-duplicated, so 3 copies start one identify.

**Measure.** Re-run T1 (c) and (d), comparing the changed wands with unchanged wands in the
same slots.

**Constraints.**
- The radio memory rule.
- `espnow_manager.py` is copied per tree; this touches the Wand Module copy only.

### T6 — RSSI by distance (optional)

On the bench, the reported RSSI was -27 to -64 dBm, varying 10–20 dB per device without
moving. Only worth running if a "near me" filter is a candidate. Place wands at 1, 3 and 8
m from a Dial and record 20 scans.

## Not covered by hardware tests

These are UX questions; timing data cannot decide them:

- Splat host confusion: 1 host + 4 Splats = 5 devices, and no instructions.
- The room map.
- Interview vs. form.

What would decide them:
- A paper or clickable mock of the form view and the room map, shown to 3–4 teachers.
- A first-use Splat host checklist tried on someone who has not set one up.

## Logistics and questions

1. **Ports.**
   - Three controllers plus ideally two logged wands need 5 ports. Is a USB hub OK?
   - Tell me which board is on which port. I'll read `list_ports` to confirm.
   - Before you swap anything, I stop my two wand logs (`usbmodem101`, `usbmodem1101`).
2. **Box firmware.** Does the Box have the `fleet.*` firmware (S12 or later)? I'll check with
   `identify`.
3. **Changing bench wands.** OK to distribute a game to, and start games on, the bench wands
   in T2 and T3? It changes their installed games.
4. **Attended time.** Can you be present for one ~15 min block (T2 taps, T3 game setup)?
5. **T5.** Yes or no on trying the firmware fix on 3–4 wands later. Not doing it without
   your yes.
6. **The first baseline.** The first single-Dial run, before Chrome was quit, got
   14/14/14/13/12/9/13/13, and later runs got 17 every time. Was anything else polling then,
   such as an open ChatBroadcast tab or another controller?
