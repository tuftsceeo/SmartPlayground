# Bag3 multi-device game framework — design recommendation

Target: ChatBroadcast generates multi-player games made of **role files**, one per device, and the
Bag3 firmware runs them on wands and stations through one shared framework.

Scope of this document: the device framework and lib, the ESP-NOW protocol, the game package and its
delivery, per-station updates, a verification plan, and a game list.

No backward compatibility is preserved. Every tree is re-flashed together.

---

## 1. The model

A **game** is a set of role files plus named assets, held together by the Box under one slug.

```
goalrush/
  goalrush_teama.py     role file, runs on wands
  goalrush_teamb.py     role file, runs on wands
  goalrush_display.py   role file, runs on the icon station
  tree.py  whale.py     assets, 16x16 icons for the display role
```

Three facts describe a running device:

| | Source | Changes |
|---|---|---|
| **hubtype** | `/hubtype.txt`, written at flash time | never |
| **slug** | the game currently running | per round |
| **role** | which part of that game this device plays | when the teacher hands out a new role card |

The teacher assigns roles physically: team-A kids tap the team-A card, team-B kids tap the team-B
card, the teacher taps the display station's card. Then one `start` from the paper remote runs
everyone at once, each in its own role.

### 1.1 Naming

A module name is `<slug>` for a single-role game, `<slug>_<role>` otherwise.

- slug: `^[a-z][a-z0-9]*$`, ≤14 chars — **no underscore**, so the first `_` always separates.
- role: `^[a-z][a-z0-9_]*$`, ≤9 chars.
- module name: ≤24 chars, a legal Python identifier, since `__import__` takes it directly.

Enforced in three places that must agree: `ChatBroadcast/js/gameName.js`, `lib/nfc_reader.py`
(what a card may say), `lib/game_store.py` (what may land on flash).

### 1.2 Role resolution

The filesystem is the index. `/games/` holds at most one module per slug, because pulling a role
file for slug X deletes any other role file for slug X.

```
resolve(slug) -> module name or None
    "<slug>.py" if present, else the single "<slug>_*.py" present, else None
```

A `sys start <slug>` broadcast therefore means the same thing on every device and needs no per-device
lookup table.

### 1.3 Cards

Two labels per role, plus one play card per game:

```
getcode:goalrush_teama    pull the team-A role file (and its assets)
goalrush                  start the game locally in whatever role this device holds
```

`DONE` stays as the Box's UI sentinel and never reaches a card.

---

## 2. Device framework

### 2.1 `lib/hubtype.py`

```python
HUB_TYPE    # str, from /hubtype.txt
HUB_CONFIG  # pins and geometry for this hubtype
CAPS        # frozenset of capability names this hubtype provides
```

Changes from current behaviour:

- An unknown or missing `hubtype.txt` **raises** at import instead of silently becoming `wand`.
  A device with the wrong identity is a fault, not a default.
- `CAPS` is the single source of truth for what a hubtype can do, and is actually consulted —
  by `devices.build()`, by the capability dispatcher, and by ChatBroadcast when it decides which
  knowledge sections to load.

Hubtypes:

| hubtype | CAPS |
|---|---|
| `wand` | `matrix5`, `buzzer`, `accel`, `button`, `nfc`, `motor`, `battery` |
| `code_station` | `slots4`, `nfc`, `button`, `slotleds` |
| `score_station` | `bars4`, `nfc` |
| `icon_station` | `icon16`, `nfc` |
| `dial_station` | `audio`, `encoder`, `screen`, `nfc` |
| `splat_station` | `splat`, `nfc` (design only) |
| `radar_station` | `tracks3`, `nfc` (design only) |

Every playable hubtype has `nfc`, because every device takes its role from a tapped card. That is a
hardware addition on the score and icon stations.

### 2.2 `lib/devices.py` (new)

`build()` reads `HUB_TYPE`/`HUB_CONFIG` and returns a `Device` carrying only this hubtype's
peripherals. It replaces `main.py`'s module-level, wand-shaped construction, which raises `KeyError`
on any station today.

```python
dev.hub_type   dev.slug   dev.role   dev.mac
dev.net        # ESPNowManager
dev.nfc  dev.leds  dev.buz  dev.accel  dev.i2c  dev.button      # wand
dev.slots  dev.bars  dev.icon  dev.dial                          # stations
```

- A capability this hubtype does not have is **absent**, so a game touching it fails with
  `AttributeError` naming the attribute.
- A capability that is present but whose driver failed to initialise is set to `None` and printed as
  `[FAIL] <name>`. The device stays usable for games that do not need it; a game that does need it
  fails immediately and visibly.

### 2.3 The game entry point

```python
def play(dev):
    while dev.running():
        ev = dev.event()
        ...
        dev.tick(20)
```

Replaces `play(nfc, leds, buz, accel, i2c, enow)`. All existing wand games migrate; there is no
compatibility shim.

- `dev.running()` pumps the radio every call and the NFC reader on its own cadence, consumes system
  messages, and returns `False` when the game must end (stop, a start for another game, or an exit
  tag). Forgetting to poll is no longer possible, which removes the failure that makes a game
  unstoppable today.
- `dev.event()` returns the next queued `(ev, data, mac)` or `None`. System traffic never reaches it.
- `dev.tick(ms)` sleeps and does per-frame housekeeping. It always yields at least 1 ms.
- `play()` returns to end. `dev` restores its own outputs afterwards; a game no longer needs a
  `try/finally: leds.off()`.

`_StartGameCapture` disappears — chaining is handled inside `Device`.

### 2.4 Loading

Unchanged in shape from the current wand: a game module is imported on tap and dropped afterwards,
because heap headroom for `esp_wifi_init()` is tight. `GAME_MODULES` (built-ins) plus
`game_store.resolve()` (pulled roles) feed one loader used by every hubtype.

Whether each station can afford a shared `main.py` or needs its own is a measurement, not a
judgement — see §7.1.

### 2.5 Migrating the existing wand games

Fifteen built-in games move to `play(dev)`. The changes are mechanical and each one removes code.

| Today | After |
|---|---|
| `def play(nfc, leds, buz, accel, i2c, enow)` | `def play(dev)` |
| `leds`, `buz`, `accel`, `nfc` as locals | `dev.leds`, `dev.buz`, `dev.accel`, `dev.nfc` |
| `_EXIT_TAGS = exit_tags_excluding("<tag>")` and the per-loop exit block | deleted — `dev.running()` owns it |
| `msg_type, _, _ = enow.poll()` then `if msg_type in ("stop","start_game"): return` | deleted |
| `try: ... finally: leds.off()` | deleted — `dev` restores its own outputs |
| Module-level `I2C_SDA`, `BUZZER_PIN`, `PN532_ADDR`, `NUM_LEDS`, `SWITCH_PIN` | `HUB_CONFIG`, via `dev` |
| A game opening its own `Pin(SWITCH_PIN)` | `dev.button` |
| `rainbow.py`'s extra `batt=` keyword and its special case in `_launch_game` | `dev.batt` |
| `opcodes.py` card encoding | NDEF text; `opcodes.py` is retired |

Two games change more than mechanically, and they are the §6 reference cases.

**`color_quest.py`** — the score unicast to `target.SCORE_MAC` becomes
`dev.net.broadcast_cap("score_station", "push", {"v": elapsed_ms, "c": colour})`, and the inline
`{"type":"scan_request"}` becomes `dev.net.broadcast_cap("code_station", "scan")`. The sequence
arrives as `evt seq` instead of a bare JSON list. `target.py` is deleted from all three trees. The
game keeps its own 5×5 layout maths.

**`freeze_dance.py`** — the five-times-repeated raw byte broadcasts become
`dev.net.broadcast_cap("dial_station", "play"|"pause")` for the music and
`dev.net.broadcast_evt("go"|"freeze"|"dance")` for the other wands. The repeat-and-guard idiom stays:
there is still no acknowledgement. Role select by NFC card stays as it is — it is the same idea as a
role file, at a smaller scale, and works today.

`main.py` keeps `GAME_MODULES` for built-ins and consults `game_store.resolve()` for pulled roles, so
a built-in and a pulled role load, run and unload by the same path.

---

## 3. ESP-NOW protocol

`lib/espnow_manager.py` keeps its current shape: polling, no callbacks, JSON payloads,
`poll()` returning `(msg_type, data, mac_str)`, async unacked broadcast with one retry. What changes
is the message vocabulary and the fact that games can extend it without editing the library.

### 3.1 Three message types

```json
{"type":"sys", "op":"stop"}
{"type":"sys", "op":"start", "slug":"goalrush"}
{"type":"sys", "op":"who"}
{"type":"sys", "op":"here", "hub":"icon_station", "id":"a4"}
{"type":"sys", "op":"ident", "mac":"AA:BB:CC:DD:EE:FF"}
{"type":"sys", "op":"batt", "soc":83, "rssi":-54}

{"type":"cap", "hub":"dial_station", "op":"play"}
{"type":"cap", "hub":"score_station", "op":"push", "a":{"v":8420, "c":"blue"}}

{"type":"evt", "src":"code_station", "ev":"seq", "d":["red","blue","green"]}
{"type":"evt", "src":"wand", "slug":"goalrush", "ev":"goal", "d":{"team":"a"}}
```

- **`sys`** — framework traffic. Handled inside `Device`; never delivered to a game.
- **`cap`** — a command to a station's hardware, addressed **by hubtype, not by MAC**. Every station
  of that hubtype acts on it. This is what lets a wand-only game drive a station with no station-side
  code at all.
- **`evt`** — anything a device wants to report. Game-authored events live here, keyed by `slug`, so
  a generated game invents its own vocabulary without touching the library. `Device` delivers `evt`
  to the running game via `dev.event()`, filtered to its own slug plus station reports.

The closed routing enum (`colors`, `score`, `splat_config`, `scan_request`, `status_poll`, …) is
removed. So is the bare-bytes dialect (`b"FD_GO"`, `b"FD_FREEZE"`, `b"FD_DANCE"`, `b"FD_RESET"`,
`b"stop"`) — `send_raw()` stays for genuine binary but nothing in the system uses it for control.

**One stop.** `{"type":"sys","op":"stop"}` is the only stop. Today the dial and speaker compare a
decoded payload against the bare string `"stop"` while `broadcast_stop()` sends `["stop"]`, so only
Freeze Dance's raw path can stop the music. After this change a stop from any source — an NFC stop
tag, the paper remote, the USB hub, another wand — stops every device.

### 3.2 Addressing

Broadcast by hubtype is the primary mechanism, and it removes `target.py::SCORE_MAC` and its two
duplicates with no new state: a game says "score stations, push this value" and does not care which
MAC that is.

`sys who` / `sys here` exists for the case of two stations of the same hubtype in one space. Replies
reuse the existing slotting so they do not collide: slot `= mac_last_byte % 16`, delay
`400 ms + slot * 180 ms`. `net.find(hubtype)` returns a cached MAC from those replies, and
`net.send_to(mac, …)` unicasts. Nothing in the games below needs it.

### 3.3 Size

ESP-NOW carries 250 bytes. `broadcast()` and `send_to()` check the encoded length before sending and
raise `ValueError` naming the message. Today an oversized payload is a caught exception and a `False`
return, which reads as "sent" to every caller that ignores it.

### 3.4 What the protocol does not do

No delivery guarantee, no ordering, no acknowledgement, no de-duplication, no fragmentation. A game
that needs an event to land repeats it and guards on state, the way Freeze Dance already does.
Coordinator-less means no roster and no authority: aggregate scoring over an unknown set of players
is not expressible. "Who was first" is decided by the device that renders the outcome, from the first
`evt` it hears.

### 3.5 New methods

```python
net.broadcast_sys(op, **kw)
net.broadcast_cap(hub, op, args=None)
net.broadcast_evt(ev, data=None, slug=None)
net.find(hub)                 # cached MAC from sys here, or None
net.send_to(mac_str, obj)     # unchanged
```

`init()`, `shutdown()`, `add_peer()`, `poll()`, `drain()`, `get_rssi()`, the antenna selection and
the slotted status reply all keep their current behaviour. The MockWand copy's selectable antenna and
its `shutdown()` that actually releases the radio become the shared version.

---

## 4. Game package and delivery

### 4.1 On the Box

```
/flash/games/index.json          {slug: {"roles": {role: module}, "assets": [name, ...]}}
/flash/games/<module>.py         one per role
/flash/games/assets/<name>.py    icons, shared by the roles that name them
/flash/active.txt                slug selected for serving
```

`_rebuild_entries()` emits, per game: one `getcode:<module>` per role, one bare `<slug>` play card,
plus `DONE`.

### 4.2 Wire contract, wand/station ↔ Box

The current session serves exactly one file. It becomes a small multi-file session so a role file
arrives with the assets it needs.

```
client -> box : 1 byte len | <len> bytes UTF-8 module name   (len 0 = serve active)
box    -> cli : 2 bytes N (BE)  — number of files, 0 = refusal
  per file:
box    -> cli : kind(1B) | size(4B BE) | sha256(32B) | name_len(1B) | name
box    -> cli : body, 512-byte chunks, 20 ms yield
cli    -> box : 2-byte ack, b'OK' or b'NO'
```

`kind` is `0` for the role module and `1` for an asset. Destination follows kind, so no filename
sniffing: modules land in `/games/<name>`, assets in `/icons/<name>`.

Per file the client keeps what it does today — write to `<dest>.part`, verify length and sha256,
`compile()` the source, rename the previous copy to `.bak`, then promote. A file that fails any check
is deleted and NAKed; the previous copy stays. `N = 0` is an explicit refusal the client treats as
terminal, spending no retry.

Constants stay hand-mirrored between `BBoxFirmware/code_server.py` and the client puller, both marked
`PEER:`; they run on different devices with no shared module.

Measured sizes: a 16×16 icon file is 3.3–3.7 KB, so a role plus two icons is roughly 12 KB, about 24
chunks. The transfer is not the cost — the mode switch and the reset are.

### 4.3 Pull on a station

Same three-step shape the wand already uses, for the same reason: a WiFi join only succeeds on a
radio ESP-NOW has not touched this boot.

```
tap "getcode:<module>"  ->  pull_flag.set_pending(module)  ->  machine.reset()
next boot               ->  flag checked first, before ESP-NOW exists  ->  pull  ->  reset
```

`pull_flag` and `code_puller` move into the shared `lib/` and are used unchanged by every hubtype.
The attempt budget is still spent before each attempt, so a crash mid-pull cannot boot-loop.

The Box energises either its WiFi AP or its NFC field, never both, and serves one client per `poll()`.
A class therefore picks up code serially. §7.5 measures what that costs before anything depends on it.

### 4.4 ChatBroadcast

- **Output**: one fenced block per role. Each is preceded by `[ROLE: <role> <hubtype>]`; the game
  keeps its single `[GAME_NAME: …]`. Icons are emitted as `[ICON: <name>]` plus a block in the
  `ICON = ((r,g,b), …)` form `icon_store` already parses.
- **`extractCode()`** returns a list of `{role, hubtype, code}` rather than the first block.
- **`confirmSend()`** writes every role and asset in one Box session and shows the teacher which
  roles exist and which cards still need writing.
- **`validateJumpin()`** becomes `validateRole()`: the signature must be exactly `def play(dev)`.
- **Knowledge** splits from one 913-line file into `core` plus one section per hubtype, and `chat.js`
  loads `core` plus only the hubtypes in the current game. Sections carry no `jumpin` naming.
- The simulator runs one device with a write-only radio, so it cannot exercise any of this. That is
  stated to the teacher rather than implied away.

---

## 5. Stations

Every station gains: `hubtype.txt`, the shared `lib/` (`hubtype`, `devices`, `espnow_manager`,
`game_store`, `pull_flag`, `code_puller`, `nfc_reader`, `pn532`), a PN532 for role cards, a
capability handler, and the ability to run a role file.

A station with no role file is still fully usable — it answers `cap` messages. A station with a role
file runs `play(dev)` and drives its own hardware directly.

Loop shape, every station:

```python
dev = devices.build()
while True:
    dev.pump()              # sys + cap, non-blocking
    if dev.pending_game():
        dev.run_game()      # play(dev) for this device's role
    dev.tick(20)
```

`Icon Display` and `Radar` already idle on `select.poll()` in `json_link.py` at zero CPU; that stays
for their USB path, which remains for authoring and bring-up.

### 5.1 Dial station — `dial_station`

Today: M5Dial under UIFlow2, its own `RemoteControl` doing raw `espnow`, matching bare strings
`FD_GO` / `FD_FREEZE` / `stop`. `AudioController` beneath it is already a general track API
(`set_volume`, `play_by_index`, `pause`, `resume`, `stop`, `get_total_files`, `read_file_name`,
400 ms debounce).

| verb | args | maps to |
|---|---|---|
| `play` | — | `resume()` |
| `pause` | — | `pause()` |
| `stop` | — | `stop()` |
| `track` | `i` | `play_by_index(i)` |
| `vol` | `v` | `set_volume(v)` |

Emits `{"type":"evt","src":"dial_station","ev":"track","d":{"i":n,"name":"..."}}` on a local encoder
change, so a game can follow the teacher's selection.

`RemoteControl` is deleted; the station uses the shared `ESPNowManager`. Whether an M5 target can
share `/lib/` or needs flat root copies is §7.4. The debug `# region agent log` prints in the polling
path go.

### 5.2 Coding station — `code_station`

Today: 4 PN532s behind an I²C mux at `0x70`, 18 LEDs (2 per slot, `LED_LUT = {3:(7,8), 2:(10,11),
1:(13,14), 0:(16,17)}`), a fixed `TAG_COLOR` table, and a `do_scan()` that blocks for seconds while
hard-resetting readers.

| verb | args | behaviour |
|---|---|---|
| `scan` | — | start a scan; report when finished |
| `slot` | `n`, `c` | set slot `n` to colour name `c` |
| `clear` | — | all slots off |

Reports `{"type":"evt","src":"code_station","ev":"seq","d":["red","blue","green"]}`.
A button press starts the same scan and reports the same event.

Changes:

- `do_scan()` becomes a step machine driven from the loop, one reader per pass, so the radio is
  polled throughout instead of being starved for seconds.
- Unknown tag text no longer raises `KeyError` inside a broad `except` that silently abandons the
  whole scan. An unrecognised tag is reported in the sequence as `"?"` and printed.
- The station reads `led_pin` / `num_leds` from `HUB_CONFIG` instead of hardcoding
  `NeoPixel(Pin(21), 18)` alongside the values it already reads and ignores.
- The colour vocabulary is the tag text itself (`red`, `blue`, …), not a wand opcode name.

### 5.3 Slide score station — `score_station`

Today: receive-only, 40 LEDs in a 4×10 serpentine, a Color-Quest colour vocabulary, the colour list
used as the game key, and an inverse-time scale (smaller `time_ms` = taller bar) baked into
`update_display()`.

| verb | args | behaviour |
|---|---|---|
| `push` | `v`, `c` | add value `v` in colour name `c` |
| `clear` | — | empty the board |
| `scale` | `mode` | `"low"` (smaller is better, current behaviour) or `"high"` |

The board becomes a generic display sink: it holds the last four values and renders them, with no
opinion about what they mean and no Color-Quest vocabulary. Colour comes from the caller.

Changes:

- `score_arrival_animation()` becomes frame-stepped from the loop instead of ~1.3 s of blocking
  `sleep_ms` during which further messages queue in the radio ring buffer.
- `score_queue = deque((), NUM_BARS)` with a plain `append()` is replaced by an explicit
  fixed-length list. See §7.6 — MicroPython's `deque` raises `IndexError` when full unless built with
  `flags=1`, and the `while True` around it is unprotected. That is a hypothesis to reproduce first,
  not a fix to apply blind.

### 5.4 Icon display station — `icon_station`

Today: 256 WS2812B in a 16×16 serpentine, icons stored as `icons/<name>.py` holding
`ICON = ((r,g,b), …)` parsed line-at-a-time, a truncating brightness LUT clamped at `MAX_INTENSITY =
0.50`, and an NDJSON-over-USB server. No radio, no NFC.

| verb | args | behaviour |
|---|---|---|
| `icon` | `n` | show stored icon `n` |
| `clear` | — | blank |
| `bright` | `v` | set intensity, still clamped at 0.50 |
| `cycle` | `names`, `ms` | cycle a list |

Its role file gets the same verbs directly as `dev.icon.show("tree")`, and the icons it names arrive
with it as assets.

Additions: PN532 for role cards, ESP-NOW alongside the existing USB server, `hubtype.txt`. The USB
NDJSON path stays — it is how icons are authored.

Power discipline from its own bring-up measurements is a design input: at 50% intensity on 5 V,
solid white fails at 8 of 16 rows; on 12 V, rainbow content clears the full matrix. Static content
runs below the tested ceiling; full-brightness moments stay short.

### 5.5 Design only

**Radar station** (`radar_station`) already computes tracks, zones, speed buckets and
approach/recede for ≤3 people over USB NDJSON. Proposed verbs: `stream` on/off; emits
`{"ev":"tracks","d":[{"id","x","y","sp","hd"}]}` and `{"ev":"zone","d":{...}}` at a rate the game
sets. Its internal bucket named `run` is serialised as `fast`; pick one name.

**Splat / big button** (`splat_station`) is the closest thing already to a capability device —
"configure me with an action chain, then react to presses". Proposed verbs: `led`, `sound`, `note`;
emits `press` / `release`. Note the defect in §7.6 before touching it.

**Speaker** is folded into `dial_station`'s verb set or retired; it is a single-track appliance that
boots paused waiting for `FD_GO`.

**Bag1 Plushie** and its `{'topic','value'}` dialect are out of scope.

---

## 6. Verification plan

Each test is a hypothesis with a stated falsifier. Serial capture drives what can be driven from the
host; a person judges anything shown on LEDs, a screen or a speaker. Nothing is reported as working
from a log alone.

Host-drivable without a person: the Box's JSON command path over CDC; `pull_flag.set_pending(<module>)`
followed by `machine.reset()` to exercise a pull with no card; `nfc_reader` matchers called against
synthetic strings. A faked tap does not exercise the NDEF decode path and is reported as what it is.

### 6.1 Freeze Dance on the dial station

Reference case for `cap` replacing the bare-bytes dialect. Roles: `freezedance_caller` and
`freezedance_player` on wands; the dial runs no role file and answers `cap` only.

The caller's button drives `net.broadcast_cap("dial_station", "play")` on press and `"pause"` on
release; players react to the matching `evt` the caller also broadcasts.

| # | Hypothesis | Steps | Falsified if |
|---|---|---|---|
| 1 | A stop from **any** source pauses the music | Start the game. Stop three times, once per source: the wand's `stop` NFC tag, the paper remote's stop, the USB hub's stop. | Music keeps playing after any one of the three. This is the case that fails today. |
| 2 | Caller press/release drives the dial with no dial-side game code | Flash the dial with firmware only, no role file. Press and release the caller's button. | Audio does not start or does not pause. |
| 3 | Players react without the dial in the room | Power the dial off. Run caller + 2 players. | Players stop responding to GO/FREEZE. |
| 4 | A late-joining wand plays | Start a round, then tap a player card on a third wand and press its button. | The third wand never enters play. |
| 5 | Track selection is visible to the game | Turn the dial's encoder mid-round. | No `evt track` is seen in a wand-side capture. |

### 6.2 Color Quest on the coding and score stations

Reference case for a three-hubtype game and for hubtype addressing replacing `SCORE_MAC`. Roles:
`colorquest_player` on wands; coding and score stations answer `cap` only.

| # | Hypothesis | Steps | Falsified if |
|---|---|---|---|
| 1 | The score station is reached with no MAC configured anywhere | Grep the tree for a hardcoded score MAC — there must be none. Finish a round. | The bar does not appear, or a MAC literal is still required. |
| 2 | The coding station reports a sequence without blocking the radio | Place 3 colour cards, press the station button, and during the scan send a `sys stop` from the paper remote. | The stop is missed, or the scan aborts silently on an unreadable tag. |
| 3 | An unknown tag degrades loudly, not silently | Place one non-colour tag among three colour tags. Scan. | The whole scan is abandoned with nothing reported. |
| 4 | The board holds 5+ rounds | Complete 5 rounds without resetting the station. | The station drops to the REPL, or stops updating. Settles §7.6. |
| 5 | Two wands' results both land | Two wands finish the same sequence. | Only one bar appears. |
| 6 | `scale` changes the reading | Send `cap score_station scale high`, then push two values. | Bar heights do not invert. |

### 6.3 Role delivery

The test the whole design exists for.

| # | Hypothesis | Steps | Falsified if |
|---|---|---|---|
| 1 | One game, three roles, three devices | In ChatBroadcast generate a two-team game with a display role. Send it to the Box. Write three `getcode:` cards. Tap each on its device. | Any device fails to pull, or pulls the wrong role. |
| 2 | Assets arrive with the role | The display role names two icons. | The station pulls the module but not the icons, or shows nothing. |
| 3 | One start runs all three in role | Press start on the paper remote. | Any device stays idle, or runs the wrong role. |
| 4 | Re-roling replaces, does not accumulate | Tap the team-B card on a wand already holding team-A for the same slug. | Both role files remain in `/games`, or resolution becomes ambiguous. |
| 5 | A refused pull costs nothing | Tap a `getcode:` card for a game the Box does not have. | The wand spends its retry budget or error-blinks twice. |
| 6 | A corrupt role never runs | Send a role file with a deliberate syntax error. | The bad file is promoted, or the previous copy is lost. |

### 6.4 Static checks

`python -m py_compile` on every changed device file — the only static check available off-device.
Import graph walked against `BBoxFirmware/manifest.js` so no module reachable from `main.py` is
missing from `BOX_FILES`.

---

## 7. Open items

These are measurements and decisions this design does not settle.

1. **Heap budget.** No numbers exist in the repo; `lib/memprobe.py` and `import_bench.py` produce
   them on hardware. Run `bench_sequential`, `bench_isolated` and `bench_unload_cycle` on a wand and
   on one station before deciding whether stations share one `main.py` or carry their own. Games are
   imported on tap and dropped after because contiguous heap for `esp_wifi_init()` is tight; a
   station framework that eats that margin fails at radio init, not at load.
2. **Station hardware roster.** Which units exist for the verification pass, and which can take a
   PN532. This gates §6 entirely.
3. **Dial scope.** Whether the M5Dial takes an NFC reader and role files, or stays capability-only.
   §6.1 assumes capability-only, which is the smaller change.
4. **M5 file layout.** Whether UIFlow2 targets can share `/lib/` or need flat root copies. Decides
   whether the dial gets the shared `espnow_manager` by import or by hand-kept copy.
5. **Serving a class.** The Box serves one client per `poll()` and cannot hold WiFi and the NFC field
   at once. Time one pull end to end, including the two resets, then multiply by a classroom.
6. **Two defects to reproduce before fixing.**
   - `Slide Score/main.py`: `deque((), NUM_BARS)` then `append()`. MicroPython raises `IndexError`
     when full unless constructed with `flags=1`, and the loop around it is unprotected. §6.2 test 4
     settles it.
   - `Bag2/Code/Splat Companion/ble_splat.py` is a copy of the wand's BLE controller and does not
     define `OpenSplat`, while `main.py` imports `OpenSplat` from it and a root file shadows
     `/lib/ble_splat.py`. Verified by reading; confirm on hardware that the directory fails at import
     before rearranging it.

Smaller items folded into the work above rather than tracked separately: `Bag3/Code/Wand Module/boot.py`
builds a 60-LED strip; `paper_remote` and `usb_hub` ship a `hubtype.txt` value that is not a config
key; the narrator and paper remote carry stale bundled `game_tags.py`; the Bag3 knowledge copy maps
"tilt left/right" to the `x` axis while two other sections of the same file use `y`.

---

## 8. Games this enables

Grounded in the verbs above. Roles are named per game.

**Two-team, display-arbitrated** — the shape in the worked example.

- *Goal Rush* — `teama` / `teamb` wands, `display` icon station. First team to tap the goal tag wins
  the round; the display shows that team's icon. Exercises: roles, first-event arbitration, assets.
- *Colour War* — teams collect colour tags; the display shows whichever team's icon most recently
  led. Adds: repeated rounds without a reset.

**Station as the puzzle**

- *Combination Break* — the coding station holds a secret sequence; wands guess by tapping colour
  cards; the icon station shows how many positions match. Exercises: `code_station scan`,
  `icon_station icon`.
- *Recipe Relay* — each wand is handed one ingredient card; the coding station accepts them only in
  order; the dial plays a jingle per correct step. Exercises: two stations in one game, ordering
  without an authority.

**Movement and music**

- *Freeze Dance* — the §6.1 case, now with the dial driven by verbs rather than a private dialect.
- *Tempo Chase* — the dial cycles tracks; wands must match the tempo by shaking; the score station
  shows who held it longest. Exercises: `dial_station track`, `evt track`, `score_station push`.

**Score-station-centred**

- *Slide Sprint* — time from start tag to finish tag, pushed to the board per player. The current
  Color Quest use, generalised by `scale`.
- *Steady Hands* — hold still the longest; the board shows durations with `scale high`.

**Needing what this round defers** — listed so the boundary is explicit. Anything with team totals,
elimination brackets, a live player roster, or a shared clock needs an authority the coordinator-less
model does not provide. *Capture the Flag* with per-team scores, *Last One Standing*, and any
"best of N players" leaderboard fall here.
