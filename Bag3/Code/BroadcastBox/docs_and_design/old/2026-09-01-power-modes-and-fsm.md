# Power modes + task-flow state machines — Box, Wand, ChatApp

**Original design outline, superseded in parts.** Phase A is built; Phases B
and C are not. Kept as the record of the reasoning, with the phase notes at the
end amended 2026-09-02 against the code. Everything above those notes describes
the plan as first drawn, not what shipped — in particular the B1/B2 GPIO side
keys do not exist (the unit has `M5.BtnA` and `M5.BtnB`), the card flow ended up
press-driven rather than hold-driven, and there is no `RECEIVING` state. For
what is actually built, read `design/box-ux-and-state-machine.md` and
`design/box-screen-inventory.md`.

## Context

The Box draws too much from a USB port when the SoftAP and the NFC reader are
active at the same time. Today that is the *normal* state: `bbox_server.run()`
calls `_try_arm()` at boot, and any `payload.py` on flash raises the AP **and**
enables card writing simultaneously, for as long as the box is powered
(`bbox_server.py:_try_arm`, `code_server.py:_start_ap`). Swapping the PN532 for
the WS1850S and gating the RF field on G11 lowered the peaks; it did not remove
the overlap.

The fix proposed here is structural rather than incremental: **the radio and
the reader are never on at the same time.** The Box becomes explicitly modal,
and the teacher moves between modes with the two side buttons.

The second change in scope: games get names. Today every upload lands at
`/flash/payload.py` and is served to wands under the fixed name `jumpin.py`
(`code_server.py:DEFAULT_DEST`), overwriting the built-in game of that name. A
teacher cannot have two games in play at once, and a card cannot say which game
it fetches.

## Hardware controls (Box)

| Control | Role |
|---|---|
| **B1** = G11 side key | Scan / write / confirm. Hold = leave serve mode. |
| **B2** = G12 side key | Scroll the tag list. |
| `M5.BtnA` (front) | Unassigned in the new flow; currently the overwrite confirm. Keep as an alias for B1 during bring-up so the flow is testable before the side keys are proven. |

## The invariant

> At most one of {WiFi AP, NFC RF field} is energized at any instant.

Everything below exists to make that true without making the teacher's job
harder. USB serial to the app is orthogonal — it stays available in every mode
and costs nothing — but an upload never happens with the AP up.

---

## Teacher task flow → states

| # | Teacher does | Box state | Wand state | App state |
|---|---|---|---|---|
| 1 | Authors code on the website | (off / any) | idle / playing | `AUTHORING` |
| 2 | Connects Box over USB | `LINKED` | — | `CONNECTED` |
| 3 | Uploads named game | `RECEIVING` | — | `SENDING` |
| 4 | Writes NFC tags | `WRITE` (radio off) | — | `TAG_CHECKLIST` |
| 5 | Switches Box to pickup mode | `SERVE` (NFC off) | — | idle |
| 6 | Kid taps `getcode:<game>` | `SERVE` | `PULL` (reboot-bracketed) | — |
| 7 | Kid taps `<game>` | `SERVE` | `PLAY <game>` | — |
| 8 | Teacher iterates | `WRITE` (B1 held from serve) | — | `AUTHORING` |

---

## Box FSM (`bbox_server.py`)

```
BOOT
 └─ UI, WS1850S init (antenna OFF), buttons, hello
 └─ radio stays DOWN  ← change: no auto-arm of the AP
      │
      ▼
LINKED / IDLE ───(app: push game)──► RECEIVING ──(reset, game stored)──► WRITE
 │  ▲                                                                     │
 │  └──────────────────(B1 hold, from any mode)────────────────────────┐  │
 ▼                                                                     │  │
WRITE  (AP down; NFC polled only while B1 is down)                     │  │
 ├─ B2 short        → next tag in the list (getcode:g1, g1, g2, … DONE)│  │
 ├─ B2 at DONE +B1  → SERVE                                            │  │
 ├─ B1 down + card  → SCAN → matches target text?  yes → ALREADY_OK    │  │
 │                                        no, blank → WRITING          │  │
 │                                        no, other → OVERWRITE?       │  │
 ├─ OVERWRITE? B1 hold → WRITING ; B2 → back to WRITE                  │  │
 └─ WRITING → WROTE_OK (advance) | WRITE_FAIL (retry same tag)         │  │
                                                                       │  │
SERVE  (NFC antenna off, no I2C polling; AP up; TCP accept/serve)      │  │
 ├─ client pulls a game → SERVING → back to SERVE                      │  │
 └─ B1 held ≥1 s → AP down, ~200 ms settle ───────────────────────────►┘  │
                                                                          │
(any state) app upload ──────────────────────────────────────────────────►┘
```

**State table**

| State | AP | NFC field | Screen | Exits |
|---|---|---|---|---|
| `BOOT` | off | off | booting | → `IDLE` |
| `IDLE` | off | off | idle + link dot | app push → `RECEIVING`; B1 → `WRITE` |
| `RECEIVING` | off | off | receiving | done → `WRITE`; fail → `IDLE` |
| `WRITE` | **off** | on **only while B1 down** | tag n/N + list cursor | B2 scroll; DONE+B1 → `SERVE`; app push → `RECEIVING` |
| `SCAN`/`OVERWRITE?`/`WRITING`/`WROTE_OK`/`WRITE_FAIL` | off | on | existing `paint_*` screens | → `WRITE` |
| `SERVE` | **on** | **off** | "pickup ready — hold B1 to stop" | B1 hold → `WRITE`; app push → `RECEIVING` |
| `SERVING` | on | off | receiving/serving | → `SERVE` |

Notes:
- Entering `SERVE` calls `nfc.antenna_off()` and skips `_poll_nfc()` entirely;
  entering `WRITE` calls `code.disarm()` (AP down) before the first poll.
- `_try_arm()` loses its AP responsibility: a `payload.py`/game on flash makes
  the box *ready to write tags*, not *broadcasting*. Being armed off-USB in the
  field still works — it just starts in `WRITE`.
- `CodeServer.poll()` serves a whole file synchronously (up to 30 s) and its
  `'serving'` branch is unreachable, so `paint_receiving()` never fires
  (`REBOOT_PULL_PLAN.md` Deferred). In `SERVE` that blocking is now acceptable
  — nothing else needs the loop — but the unreachable branch should be fixed so
  the screen tells the teacher a pickup happened.

---

## Wand FSM (`MockWand/main.py`)

Radio rule is unchanged and non-negotiable: **never ESP-NOW → WiFi within one
boot** (`REBOOT_PULL_PLAN.md`). The reboot bracket stays; only the payload
naming changes.

```
BOOT
 └─ /pullpending exists?
      ├─ yes → PULL(name)   ← radio cold; ESP-NOW not yet constructed
      │         budget spent → clear flag, error blink, fall through
      │         pull ok      → register <name>, clear flag, machine.reset()
      │         pull fail    → machine.reset() (bounded retry)
      └─ no  → NORMAL
                └─ sensors, NFC, ESPNowManager.init(), idle loop
                     ├─ tag "getcode:<name>" → write flag(name), beep, reset  → PULL
                     ├─ tag "<name>" in built-ins → PLAY (GAME_DISPATCH)
                     ├─ tag "<name>" in pulled registry → PLAY (dynamic import)
                     ├─ tag unknown → ignore/blink
                     └─ 30 s idle → NFC_SLEEP (wake on motion/button)
```

Dispatch is the **hybrid**: `GAME_DISPATCH` is consulted first and keeps its
boot-time consistency check against `GAME_TAGS`; misses fall through to a
registry of pulled games. Pulled names are added to the reader's command set at
boot so `NfcReader` recognizes them.

New/changed wand files:
- `pull_flag.py` — flag file carries the requested **game name**, not just a
  bit (`set_pending(name)` / `pending_name()`).
- `code_puller.py` — `pull(name=…)` sends the name; saves `<name>.py`; keeps
  the existing `.part` → `.bak` → promote sequence.
- New `pulled_games.py` — tiny registry over `/pulled/` + an index file:
  `names()`, `add(name)`, `play(name, …)` doing `__import__(name)`.
- `main.py` — prefix-parse `getcode:`; second dispatch path; union registry
  names into `ALL_COMMANDS`.

---

## ChatApp FSM (`ChatBroadcast/js`)

```
AUTHORING ──"Send to Box"──► CONNECT? ──(WebSerial)──► CONNECTED
                                                          │
                                              name the game (new/overwrite)
                                                          ▼
                                                      SENDING ──ok──► TAG_CHECKLIST
                                                          │              │
                                                          └──fail────────┘
TAG_CHECKLIST: lists the cards this game needs
   • getcode:<name>   (pickup card)
   • <name>           (play card, ×N duplicates the teacher wants)
   ticks off live from the Box's card_written events
GAME_LIBRARY: names on the Box, delete/replace
```

The app already carries the event surface this needs — `armed`,
`card_present`, `card_written`, `info`, `heartbeat`
(`bboxDeviceLink.js:FORWARDED_EVENTS`); today they are only logged
(`app.js:216-218`). The checklist is a consumer of events that already exist.

---

## Protocol and format deltas

**1. Card text** (`card_writer.py`, plain NDEF text — unchanged mechanism)

| Card | Text |
|---|---|
| Pickup | `getcode:<gamename>` |
| Play | `<gamename>` |

Wand matching becomes: exact-match against the command set, **plus** a
`getcode:` prefix rule. Box `CARD_LABEL` stops being a constant and becomes the
current entry in the tag list.

**2. Game storage on the Box**

```
/flash/games/<name>.py      one file per game
/flash/games/index.txt      one name per line (order = tag-list order)
```

`payload.py` remains as the compatibility path for one release, or is dropped
outright — decide when Phase B starts, not now.

**3. Pull protocol** (`code_server.py` ⇄ `code_puller.py`)

Today the server dictates: on accept it immediately writes
`size | sha256 | name_len | name | bytes`. Add a request turn:

```
client → "GET <name>\n"          (≤64 bytes, ASCII)
server → 0x00 + size|sha256|name_len|name|bytes     (found)
       → 0xFF + err_len + message                   (not found)
```

Both sides change together; there is no mixed-version fleet. Keep the sha256
verify and `.part`/rename promote exactly as they are.

**4. App → Box upload** (`boxFirmwareInstaller.js:pushPayload`)

Takes a name: writes `/flash/games/<name>.py`, appends to `index.txt`, soft
resets. The self-arm-on-reboot behavior stays, but arms into `WRITE`, not into
an AP.

---

## Phased plan

**Phase A — power modes only.** No protocol, no naming, no app change. Box gets
the mode machine: boot into `WRITE` with the radio down, B1 gates NFC as it
does now, B2 unused, `SERVE` entered explicitly and turns the reader off. Still
one game, still `payload.py` → `jumpin.py`.
*This is the phase that addresses the actual power complaint, and it is
independently shippable.*

Hardware test: box on USB, armed, left in `WRITE` for 10 min, then `SERVE` for
10 min. Record `machine.reset_cause()` persisted to flash across any reset
(test 1 in `known_issue.md`). A reset in either single-subsystem mode, but not
in the other, is the measurement that has been missing.

**Phase B — named games.** Storage layout, `GET <name>` protocol, card text
format, wand registry + dynamic dispatch.

*(Amended 2026-09-02: B2 tag-list scrolling was listed here and in fact shipped
in Phase A — `_poll_write` scrolls the list and `paint_tag_list` draws the
cursor. Phase A also went further than planned on the Box UI, adding the four
WRITE sub-states and their screens.)*

Hardware test: two games on the Box; a wand pulls each by its own card; both
play; a third wand pulling a name the Box does not have gets a clean error, not
a hang.

**Phase C — app UX.** Game naming at send time, tag checklist driven by
`card_written`, game library view with delete.

*(Amended 2026-09-02: smaller than written. The app already tracks
`this.gameName`, `this.gameDesc` and `this.requiredTags` — the tag list a game
needs — and already passes them to `sendGame(code, meta)`. `pushPayload()` then
drops `meta` and hardcodes `/flash/payload.py`. So "naming at send time" is
plumbing an existing value through, not adding naming, and the checklist has
its expected-tags source already; what it lacks is a consumer for the
`card_written` events, which the app currently only logs.)*

Hardware test: full teacher loop, steps 1–8, no USB attached after step 5.

**Ordering rationale:** A fixes the failure that is blocking classroom use and
needs no coordinated change across three codebases. B is where the coordinated
protocol change lands, so it wants A's mode machine already stable underneath
it. C is pure surface once B's data exists.

## Open questions

- **Flash budget on the Box** for a games directory — unmeasured. If it is
  tight, `index.txt` needs a cap and the app needs a delete path in Phase B,
  not Phase C.
- **Wand RAM for dynamic import.** `main.py` already imports 15 game modules at
  boot; a pulled game adds another. Whether `gc.collect()` between game exits
  is enough is untested.
- **Concurrent pulls.** `CodeServer` accepts one client at a time and serves
  synchronously. With a class set of wands tapping `getcode` at once, the
  queueing behavior is unknown — worth a deliberate test in Phase B rather than
  discovering it in a classroom.
- **Does `SERVE` need a timeout** back to `WRITE` (or to a fully idle state) if
  no wand pulls for N minutes? Lower average draw, but a teacher who walks away
  and returns finds the box off-air.
