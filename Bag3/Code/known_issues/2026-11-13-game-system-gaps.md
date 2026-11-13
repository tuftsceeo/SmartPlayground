---
title: System gaps found while designing built-in and example games
date: 2026-11-13
status: open (recorded from game design; none implemented)
devices: [Wand (Mock Wand), Splat host wand, Splats, IconDisplay, speaker station (not built)]
components: [IconDisplay games, Splat host, wand game APIs, ESP-NOW messages, ChatBroadcast knowledge]
code:
  - Bag3/Code/Stations/IconDisplay/main.py
  - Bag3/Code/Stations/IconDisplay/games/scoreboard.py
  - Bag3/Code/Stations/IconDisplay/lib/draw16.py
  - Bag3/Code/Experiments/SplatAuthoringRows/wand/lib/splat_host.py
  - Bag3/Code/Experiments/SplatAuthoringRows/wand/lib/pairing.py
  - Bag3/Code/Wand Module/lib/espnow_manager.py
  - Bag3/Code/BroadcastCode/ChatBroadcast/knowledge/accessibility.md
open:
  - D2 dance message and D3 display station mode (needed by Move Mixer).
  - M3 targeted messages conflict with "never filter by sender or target"; needs a decision.
  - M1 display roles and M2 Splat host federation (needed by bonus games only).
  - S1/S2 speaker station does not exist as a working device.
  - K1 mobility guidance missing from accessibility.md.
keywords: [game design, built-in games, icon display, station mode, Splat host, federation, speaker,
  accessibility, mobility, vibration, team totals, targeted messages, dance, Move Mixer]
---

# System gaps found while designing games

Source: `Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md` ("New system asks") and
`playground_game_examples.md` ("System asks"). Game ideas these gaps block are in
`2026-11-13-game-ideas-backlog.md`.

Status words: **verified** (checked in code, evidence given), **unverified** (not checked),
**not supported** (checked; absent).

## Icon display

| ID | Need | Games | Status |
|---|---|---|---|
| D1 | Display game logic that checks a card order or set, using the display's own NFC reader | Code Breakers (built-in), Recipe Mix-Up | Reader: verified, optional hardware (`IconDisplay/main.py`: `nfc` is "None until the card reader is fitted"). Game logic: written per game. |
| D2 | A `dance` message the display loops as last-received, each held for 2 full loops, no sender data | Move Mixer (built-in) | Not built. Fits the existing rule that icon displays never filter by sender. |
| D3 | Display station mode: with no game running, obey `show` messages (named icon, a few pixels, short text) from any wand | Move Mixer, Melody (with a speaker) | Not built. Mirrors the experiment's Splat station mode. Drawing primitives exist (`lib/draw16.py`); `start_game` over ESP-NOW is handled (`IconDisplay/main.py:549`). |
| M1 | Display roles: a host display runs a game, peripheral displays show what it sends | Habitat Hop (bonus) | Not built. Depends on M3. |
| — | No buzzer and no accelerometer on the display | All display games | Verified (`IconDisplay/main.py:19`). Every display event is silent; sound must come from wands. |

## Splat host

| ID | Need | Games | Status |
|---|---|---|---|
| M2 | Host federation: a lead host drives peripheral hosts' Splats (4 each) and receives their presses, for 8 or 12 Splats | Stepping Song, Frog Crossing (bonus) | Not built. Host limit is 4 (`pairing.HOST_MAX_SPLATS = 4`, "more than 2 per wand is not yet tested on hardware"); 2 on MicroPython v1.29.0 (`2026-11-12-splat-host-v129-firmware.md`). Host-to-host only; unlike the removed pooled path for player wands. Adds one radio hop per step. |
| A1 | Know which child stomped a Splat | Per-child scoring in Whack-a-Splat and similar | Not supported: a press event carries the Splat index only. Workarounds: one Splat per child, or score the group. |

## Wand

| ID | Need | Games | Status |
|---|---|---|---|
| A2 | A stillness check ("moved while frozen") separate from shake counting | Traffic Light, Magic Freeze, Color Says freeze | Partly verified: Freeze Dance has a motion check and a `caller` leader role (`freeze_dance.py`). No shared API. |
| A3 | Team totals: a leader wand collects scores from many wands | Treasure Hunt Race, Team Charge | Unverified for team games; the Splat host collects scores in type 9. |
| A4 | Pass a token to a random wand in a group | Hot Potato, Secret Agents | Unverified. The type 7 wand lobby exists; random pass is not built. |
| A5 | A leader's shake rhythm reaches all wands fast enough to feel in time | Wizard Beat | Unverified; ESP-NOW broadcast delay not measured for this use. |
| A6 | Wand-to-wand proximity | Little Train, Pass the Secret (dropped) | Not supported as a game API. `espnow_manager.get_rssi()` exists; accuracy as a distance is unverified. |
| K2 | Vibration for touch feedback | Echo Beat, Magic Freeze, Hot Potato | Not supported: no vibration or haptic code in `Wand Module/lib` or `main.py`. Buzzer and lights only. `accessibility.md` assumes vibration. |

## Speaker station

| ID | Need | Games | Status |
|---|---|---|---|
| S1 | A working speaker station that wands (or a card reader) control: play, stop, switch sounds, animal sounds, and a broadcast when the music stops | Melody as type 3, DJ Switch, Musical Colors, Action Echo | Not built. `Experiments/Music Board Station` is listed in AGENTS.md as non-functioning. |
| S2 | Layered sounds | Campfire Band | Not built (depends on S1). |

## Cross-cutting decision

| ID | Need | Status |
|---|---|---|
| M3 | Messages addressed to one display or one host | **Decision needed.** Conflicts with the 2026-11-13 decision that icon displays and Splat station mode act on every message and never filter by sender or target. One option: an optional target field that single-station games ignore. Blocks M1 and M2. |

## Knowledge

| ID | Need | Status |
|---|---|---|
| K1 | Mobility guidance in ChatBroadcast `knowledge/accessibility.md` (press Splats by hand, zones instead of running, partner roles, seated moves) | Not present: no "mobility" or "wheelchair" in `ChatBroadcast/knowledge/*.md`. |
| K2 | `accessibility.md` recommends "a short wand vibration"; wands have no vibration (above) | Knowledge text should say buzzer and lights. |
