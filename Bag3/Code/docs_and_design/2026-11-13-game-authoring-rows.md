# Game authoring by row: game types, axes, and the Splat authoring plan

Status: proposal, 2026-11-13. Implemented as an unproven experiment in `Bag3/Code/Experiments/SplatAuthoringRows/` (not on hardware; Wand Module unchanged).
Sources read: `Wand Module/` on branch `wand-splat-update` (`3cb1c884`), `ChatBroadcast/knowledge/`, `ChatBroadcast/js/splat/splatGameCheck.js`.

## Priorities

1. **Simple, repeatable, memorable, consistent** over complete. A rule that covers 90 % of games
   and fits in a five-year-old's head beats one that covers 100 %.
2. **Accurate, repeatable agent construction**: the agent picks one shape and copies it.
3. **Memory**: a game loads only the code its type needs.
4. **One- or two-step starts.** Multi-step lobby joining on wands is a distant last resort: the wand
   interface is limited and young children recall one or two starting steps at most.

## Axes

Two axes and one modifier.

### Axis 1: who decides

| Value | Players | Joining | Child's start |
|---|---|---|---|
| **alone** | one child, or every child separately | none | tap the game card |
| **leader** | whole class; one wand or station sends, the rest follow | open | tap the game card |
| **equal** | whole class; every wand broadcasts | open | tap the game card |
| **host** | a limited group; a station runs a closed group | closed, at the host | tap the game card on the host |

Player count and joining are not separate axes: alone/leader/equal are open and need no
coordination state; host is the only closed, stateful row.

### Axis 2: stations used

`none`, or one or more stations. **A Splat is a station that needs a wand to translate BLE**:

| Translator | Splats | Use |
|---|---|---|
| the child's own wand | up to **2** | individual play |
| a Splat host wand | up to **4** | a group's station |

There is no limit on stations; the number of Splats is bounded only by the number of translator
wands. **Pooled Splats (each wand bringing its own into a shared lobby) are removed.**

### Modifier: teams

`none`, or teams by **NFC card** or **teacher command**. No team assignment by lobby.

## Game types

| # | Example | Who decides | Stations | Notes |
|---|---|---|---|---|
| 1 | solo wand game | alone | none | default |
| 2 | cooking, ice cream | alone | 1–2 Splats on own wand | default when Splats are mentioned |
| 3 | melody | alone | a shared station, last write wins | |
| 4 | freeze dance | leader (teacher wand) | none | |
| 5 | freeze dance with music | equal, or the station leads | speaker or display | |
| 6 | team games | leader or equal | optional | + teams |
| 8 | group game at a station | host = station | that station | teams optional (card or teacher) |
| 9 | Splat host group game | host = Splat host wand | its ≤ 4 Splats | type 8 with the Splat host as station |
| 7 | group game, wand lobby | host = a wand | none | **last resort** |

## Gaps the axes expose

| Gap | Cell | Example | Proposed handling |
|---|---|---|---|
| G1 | leader + Splat host | the teacher wand cues the class Splats on freeze/go | Splat host **station mode** (below) |
| G2 | equal + Splat host | any wand lights a shared Splat | station mode |
| G3 | alone + Splat host | solo games against shared Splats | station mode |
| G4 | host + > 4 Splats | a 6–8 Splat group | Two parallel groups, not a combined host. Not supported as one group. |
| G5 | several groups at once | four Splat host groups in a room | Already fits: a child joins the host they tap; host colors must differ. |
| G6 | equal + none | wands broadcast to each other with no leader | Pattern exists (`game_patterns.md`); add a named example only if asked. |
| G7 | host + teams | teams inside a Splat host group | Allowed; teams by card or teacher command only. |

## Plans considered

- **Plan A, template per row (chosen).** The agent writes the whole file from one template per
  row. Knowledge files are cut to match. Two small firmware changes, no game framework.
- **Plan B, handler runtime (not chosen).** A wand library owns the loop; games are handler
  functions. Generated files are shorter, but every wand carries the runtime in RAM. It adds a
  second authoring shape alongside plain wand games, needs an escape hatch for motion and timing
  games, and is harder to reverse. That conflicts with priorities 1 and 3. Revisit if Plan A's
  host-row errors stay high after the validator changes.

## Plan A: template per row

### A1. Agent flow

1. **Pick the row** before writing code: who decides × stations × teams. State it in one line in
   the reply ("Type 2: one wand, two Splats").
2. **Copy that row's template.** Fill only the marked game-logic region.
3. **The send-time check** enforces the row's declarations and forbidden calls.

The row is the one decision that selects instructions and template. Everything else is filled in.

### A2. Templates

| Template | Rows | Signature | New in firmware |
|---|---|---|---|
| `wand` (existing) | 1, 4, 5, 6, 3, 8 (player side), G6 | 7 args | none |
| `wand + splats` | 2 | 8 args, `splats=None` | **local Splat API** |
| `wand → splat station` | G1–G3 | 7 args | **Splat host station mode** |
| `splat host group` | 9 | 8 args, `net=None` | trim existing `lobby_game` host path |
| `wand lobby` | 7 | 8 args, `net=None` | existing; appendix only |

The existing wand template already covers rows 3–6 and 8 through `enow.broadcast` and roles by card.
Those rows need worked examples, not new templates.

### A3. Firmware change 1: local Splat API (type 2)

Today every Splat game is a lobby game (`lobby_games.md`; `SPLATS_LOCAL` is refused by
`splatGameCheck.js`). A single child with two Splats walks through a lobby they don't need.

Proposal:

- The game declares `SPLATS_LOCAL = 1` or `2` (reversing the current refusal).
- `main.py` passes the wand's paired group (`_pair_ctl.group`, already built by `splatpair`) as the
  8th argument, `splats`, instead of entering `lobby_game`. `lobby_game` is not imported.
- The game sees `splats.count`, `splats.unit(i)` with the existing `color / note / sound / play /
  off`, and `splats.poll()` → `("press", i)` / `("release", i)` or `None`.
- The game keeps the ordinary wand loop: `enow.poll()` every loop, return on `stop` /
  `start_game`. Same shape as template 1 plus one `splats.poll()` line.
- When a declared Splat isn't connected, the wand shows the existing lost feedback and the game
  still starts. `splats.count` reports what is connected.

Memory: removes `lobby_game` (852 lines source) from the type 2 path.

### A4. Firmware change 2: Splat host station mode (G1–G3)

A Splat host that is not running a group game listens for open, last-write-wins commands, like the
melody station:

- **In:** `{"type": "splat", "s": i, "a": ["turnred", "note_c"]}` broadcast by any wand. `s` omitted
  = every Splat. Actions are validated against the same SPLAT ACTION NAMES list.
- **Out:** a press is broadcast as `{"type": "splat_press", "s": i, "c": "<host color>"}`, so any
  wand game can react.
- No membership, no lobby, no game file on the host. The host stays in its idle loop.
- `splat` and `splat_press` are added to the reserved-type list in `platform.md`, or named
  with a prefix the slug rule cannot produce.

This makes the Splat host behave like every other station, so rows 1, 4, 5 and 6 use it with
`enow.broadcast` and no new concepts.

Open question: whether a broadcast should target one host when several are in range (host color
in the message vs nearest).

### A5. Type 9: Splat host group template

The host row keeps `lobby_game`'s host path; it is the only stateful row. The template:

- Declares `SPLAT_HOST = True`, `SPLATS_MIN`, `SPLATS_MAX` (≤ 4), `PLAYERS_MIN`, `GAME_ICON`.
- Loop: `ev = net.poll()` first; return on `("end",)` / `("leader_lost",)`; cards every
  `NFC_EVERY`; `time.sleep_ms()`; `leds.off()` in `finally`. No `enow.poll()`.
- `if net.is_host:` the host decides everything and drives `net.splat(i)`; players show what the
  host sends and send input with `net.send(0, {...})`.
- Three marked regions: host on event, host on timer, player on message.
- `live_splats()` / `live_players()` helpers from `splat_lost` / `wand_lost` events.
- Uses only documented APIs: `leds.fill` and color names, not `leds.np`, `WAND_RGB`, `net.ident`,
  `read_tag_command` or `HUB_CONFIG`.

The shipped `games/host_splattag.py`, `host_relaycolor.py` and `host_lobbytest.py` are rewritten
from this template so the knowledge examples and the device games are the same code.

### A6. Knowledge files

| File | Change |
|---|---|
| new `game_types.md` | the axes table, the type table, and "pick the row first". Sent always; short. |
| `devices/wand.md` | template 1 unchanged; add template 2 (`wand + splats`) beside it |
| `lobby_games.md` | **replace** with `splat_host_games.md`: the type 9 template, one example, the trimmed `net` and event tables. Remove pooled Splats, leaders, `net.local`, `net.owner`, `wand_splats`, the "up to 2" intro. |
| `game_patterns.md` | name each pattern with its row number; add the Splat host station mode broadcast as a station example |
| `platform.md` | `[GAME_SETTINGS:]`: drop `wand_splats`; add `splats` (1–2) for type 2; keep `splat_host` |
| type 7 | a short appendix: "only when the teacher asks for a group game with no station" |

### A7. Send-time check (`splatGameCheck.js`)

| Declaration | Requires | Refuses |
|---|---|---|
| `SPLATS_LOCAL = 1..2` | 8th param `splats` | `net`, `SPLATS_MIN`, `SPLAT_HOST` |
| `SPLAT_HOST = True` | 8th param `net`, `SPLATS_MIN` ≤ 4, a `"end"` return, `net.splat(` only with `is_host` in the file | `enow.poll(`, `SPLATS_LOCAL` |
| neither | 7 params | `net`, `splats` |

### A8. Decisions needed before building

1. **Splat turn-off at game end**: the guide says the wand does it; the host games do it in
   `finally`; `Net.close()` does not. Pick one owner: the wand, after `play()` returns.
2. **Identity color → Splat color name**: document a mapping or guarantee player identity names are
   Splat color names.
3. **Paired-wand lobby code**: with pooled Splats removed, delete that path from `lobby_game.py` or
   leave it unreachable. Deleting it reduces memory for type 9.
4. **Station mode targeting** (A4 open question).

### A9. Order of work

1. Decisions A8.1–A8.3.
2. Local Splat API (A3) + template 2 + check rule. Covers the default Splat game.
3. `game_types.md`, `splat_host_games.md`; port the three host games (A5); Simulator `sync_sources.py`.
4. Station mode (A4), then examples for G1–G3.
5. Hardware check of types 2 and 9 on MicroPython v1.28.0
   (`known_issues/2026-11-12-splat-host-v129-firmware.md`).

## Problems in the current material (reference)

| # | Problem | Fixed by |
|---|---|---|
| P1 | No Splat host example; both examples are pooled lobby games | A5, A6 |
| P2 | `lobby_games.md` says "up to 2" and describes the leader flow on the host path | A6 |
| P3 | Wand template polls `enow`; Splat rules forbid it; 7 vs 8 args | A2, A7 |
| P4 | Host games use undocumented `leds.np`, `WAND_RGB`, `net.ident`, `read_tag_command`, `HUB_CONFIG` | A5 |
| P5 | Splat turn-off owner unclear | A8.1 |
| P6 | Host games have no `GAME_ICON` | A5 |
| P7 | Identity color passed to `splat.color()` without a documented mapping | A8.2 |
| P8 | Validator checks declarations only | A7 |
