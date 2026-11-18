# Device: <Label>  (`[DEVICE: <role>]`)

<!--
Template for a new device knowledge file. Copy to devices/<role>.md and replace every
<placeholder> and every comment. This file itself is NOT loaded into the prompt: chat.js loads
only the files named by `knowledgeFile` in js/roles.js.

Rules for filling it in:
- Every fact must come from the device's firmware tree (main.py launch call, lib/ APIs). Put the
  source path in a comment next to anything non-obvious. If you cannot verify something, leave it
  out or mark it "unverified" — the assistant is told to trust this file over its own memory.
- Shared rules (no f-strings, ESP-NOW basics, markers, size budget, exit behavior) live in
  platform.md. Do not repeat them here; only add what differs for this device.
- Write the "What it is" section for a teacher; write the rest for the model.
-->

## What it is and who sees it

<!-- 2-4 sentences: what the device physically is, where it sits in the playground (held by each
child? one shared station?), board and MicroPython version. -->

It has **no <list the outputs and sensors other devices have that this one lacks>**.
<!-- This line prevents the model from borrowing another device's API. -->

## The `play()` contract

```python
def play(<args exactly as main.py passes them>):
```
<!-- Source: <firmware tree>/main.py, the call that launches a game. -->

| Argument | What it is | Notes |
|---|---|---|
| `<arg>` | <type, and whether it arrives already built> | <may it be None? the guard required> |

Never create <objects the firmware already owns: radio, drivers, buses> inside a game.
<!-- Also state: does the game read cards itself, or does the station deliver card taps as enow
"stop"/"start_game"? -->

## Canonical template

```python
<!-- A complete, minimal, working game: enow.poll() every loop with return on stop/start_game,
exit cards if this device reads them, outputs off in finally. Keep it short: generated games start
from this and must stay within the size budget. -->
```

## API

<!-- Tables of calls with one-line descriptions. Only calls that exist in the firmware.
If the device has an INVENTORY of named things (icons, sounds, actions) that a game may name:
- do not list the names here;
- say "Use only the names in '<LIST HEADING>' sent with the request";
- follow the inventory steps in ../ADDING_A_DEVICE.md so the list is generated and checked. -->

## Everyday words → code

| The teacher says | Use |
|---|---|
| "<plain request>" | `<call>` |

## Limits and why

<!-- Each limit with its reason: polling rates, blocking calls, power/brightness ceilings,
memory, things that crash the device. -->

## Checklist

- [ ] `[DEVICE: <role>]` before the block
- [ ] `def play(<args>):`
- [ ] `enow.poll()` every loop; return on `"stop"` / `"start_game"`
- [ ] <device-specific guards>
- [ ] Outputs off in `finally`
