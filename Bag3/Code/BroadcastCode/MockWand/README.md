# Mock Wand — Bag3 wand copy for Broadcast Box tap-to-pull

Copy of `Bag3/Code/Wand Module/` plus `code_puller.py` for Phase 1 end-to-end
testing. Same C6 hardware and pin map as the fielded Bag3 wand.

## lib/ copies

`lib/opcodes.py` and `lib/game_tags.py` are **further uncoordinated copies** of
the tag vocabulary (alongside each Bag's `lib/`, `hubCode2/game_tags.py`,
`commands.json`, and `wand_icons.html`).

**`getcode` must match** `BBoxFirmware/opcodes.py` byte-for-byte. After editing
either file, `diff` the two copies.

**PEER copies of the Splat libraries.** `lib/splat_hub.py`, `lib/splat_link.py`,
`lib/splat_api.py` and `lib/ble_splat.py` are byte copies of
`SplatCompanion/Companion/`'s (`ble_splat.py` also of `Bag3/Code/lib/`'s).
`splat_api.py` stays the source of truth for Splat action names. Fixing one
copy fixes only that copy; `tools/devtests/test_wand_copies.py` reports drift.

## getcode flow

1. Box writes a `getcode` opcode card.
2. Wand taps card in idle loop.
3. `code_puller.pull()` shuts down ESP-NOW, joins `SP-FILEPUSH-<id>`, pulls
   `jumpin.py`, verifies sha256, promotes atomically.
4. `machine.reset()` — next boot runs the new game via `from jumpin import play`.

On pull failure the existing `jumpin.py` on flash is untouched.

## Boot grace

Five-second countdown at the top of `main()` before NFC/ESP-NOW init. Ctrl-C
during the window reaches the REPL — recovery if a pull loop wedges.

## Driving the pull path without a person

Set the flag the tap would have set, then reset:
`pull_flag.set_pending('<slug>')`, then `machine.reset()`.

Tag-text parsing can be driven the same way: call
`NfcReader._match_prefixed()` / `is_valid_slug()` on-device against
synthetic strings. This does not exercise the NDEF decode path — a real
card read is a separate check.

## Wand tree invariants

On-device layout: `/lib` for libraries, flash root for `main.py` and the
built-in games, `/games/<slug>.py` for pulled games. `/games` is appended to
`sys.path` by `main.py`. Pulled games must never land in the root — root
precedes `/games` on the path and would shadow the new copy with a stale one.

Load-bearing, must survive any future edit:

- The pull-flag check is `main()`'s first statement — a pull must happen
  before `ESPNowManager` is constructed.
- No ESP-NOW in the pull path — a WiFi join only succeeds on a radio
  ESP-NOW has never touched this boot.
- `machine.reset()` between radio modes — the tap queues the pull and
  resets; the pull succeeds and resets again.
- The attempt budget is spent before each attempt (`pull_flag.bump()`), so a
  crash mid-pull cannot boot-loop.
- **Nothing allocates ahead of the radio.** See below — this one is easy to
  break by adding a print.

## Radio memory order — do not add prints ahead of the join

`esp_wifi_init()`/`esp_wifi_start()` need one large **contiguous** block of
internal IDF heap, and the radio has to take it early: MicroPython's GC heap
is carved out of that same heap in splits that are never returned, so nothing
later can un-fragment it enough to find the block again. `gc.mem_free()` does
not measure this. The failure is **fragmentation, not exhaustion**, and it
reads as a comfortable free-heap number sitting next to
`OSError: WiFi Out of Memory`.

`lib/memprobe.py` exists because of exactly this failure at `enow.init()`.
Its `_idf_free()` returns total free **and largest free block** for that
reason — the second number is the one that decides.

Two places on this device claim the block, and both have a queue of imports
ahead of them:

- **Normal boot** — `ESPNowManager.init()`. `main.py` imports roughly fifteen
  modules at module scope before `main()` runs, and every game module it
  pulls in costs heap before the radio gets its turn. A new built-in game is
  not free.
- **Pull mode** — `sta.active(True)` in `code_puller._reset_sta()`.
  `main.py` imports `code_puller` inside `_run_pull_mode()`, *before* the
  join, so anything at that module's scope — a docstring, a format string, a
  function object — is allocated ahead of the block.

So:

1. No new module-scope content in `code_puller.py`. Import-time cost is paid
   whether or not the code runs.
2. Diagnostics go in `pull_probe.py`, imported lazily once
   `sta.isconnected()` is true, behind `DEBUG_PULL` (default off). With the
   flag off it is never parsed.
3. Anything logged about the boot itself — `reset_cause()`, battery — prints
   *after* the pull returns, not before it.

The same constraint bit the Dial and Box on 2026-09-23, from the server side:
[`docs_and_design/2026-09-23-ap-memory-order.md`](../docs_and_design/2026-09-23-ap-memory-order.md)
has the numbers and the rules for both ends.

## Slugs are module names

A slug is the filename on both devices and a MicroPython module name, since
`_load_play()` does `__import__(slug)`. Must be a legal identifier:
lowercase, leading letter, `[a-z0-9_]`, max 16 chars. Hyphens are invalid —
any surviving hyphenated game must be renamed on flash along with its
`index.json` key.

Three places enforce this and must agree:

- `ChatBroadcast/js/gameName.js` — `slugify()` / `isValidSlug()`, plus the
  reserved list (Python keywords, module names, wand built-in game tags).
- `MockWand/lib/nfc_reader.py` — `is_valid_slug()`, what a card may say.
- `MockWand/lib/game_store.py` — what is allowed on flash.

## Direct-USB push (no Box in the loop)

ChatBroadcast's connect overlay also takes a wand plugged straight into USB
— `ChatBroadcast/js/device/wandDeviceLink.js` and `wandGameInstaller.js`.
The Box is transport only; the payload is wand source
(`def play(nfc, leds, buz, accel, i2c, enow)`), so this path writes the
identical bytes directly to `/games/<slug>.py` over the raw REPL instead of
routing through `/flash/games/<slug>.py` and an ESP-NOW pull.

```
raw REPL: verify hubtype.txt == "wand", os.mkdir('/games') if needed,
          write /games/<slug>.py, game_store.set_last_pulled('<slug>')
exit raw REPL, Ctrl-D (soft reset)
```

`set_last_pulled()` reuses the auto-launch path a real ESP-NOW pull uses
(`MockWand/lib/game_store.py`, `MockWand/main.py`'s "Auto-launch a
just-pulled game") — the wand plays the game on the next boot, no card
involved.

The wand has no command listener. `MockWand/main.py` prints one JSON line
per event (`_emit()`), never reads one. Shapes mirror the Box's
`identity`/`heartbeat` so `bboxLink.js`'s NDJSON reader parses either device
unchanged:

```
{"type":"identity","device":"wand","version":<str>,"hub":<HUB_TYPE>,"games":[<slug>,...]}   — once, after boot completes
{"type":"heartbeat","up":<ticks_ms>}                                                        — every 5s, idle loop only
{"type":"game_start","slug":<slug>}  /  {"type":"game_end","slug":<slug>}                   — around _launch_game()'s body
{"type":"error","where":"game_load","slug":<slug>,"err":<str>}                              — from _game_load_failed()
```

`heartbeat` is idle-loop-only — a running game blocks the wand's main loop
for its duration, same as Box `SERVE` mode. ChatBroadcast's
`game_start`/`game_end` handlers raise and lower the silence watchdog the
same way its Box `mode`/`armed` handlers do for `SERVE`.

## Splat pairing

A wand can pair with one or two Splats, identified by BLE MAC, and drives them over its own BLE radio.
Design: [`docs_and_design/2026-10-07-splat-pairing/SPEC.md`](../docs_and_design/2026-10-07-splat-pairing/SPEC.md).

| Card text | Idle-loop effect |
|---|---|
| `splat-<12 hex>` (the Splat's BLE MAC, any case, no separators) | Not held: pair it. Held: unpair that Splat. |
| `unpair` | Unpair every Splat. |

Cards are acted on in the idle loop only; a running game ignores them.

- **Pairing** a Splat the wand does not hold: refused (red X, reject tone) if the wand already holds 2. Otherwise the
  wand broadcasts `{"type":"pw_who","m":<mac>}` and listens `splatpair.CLAIM_WAIT_MS` (300) for a unicast
  `{"type":"pw_held"}` from a wand holding that MAC; an answer refuses the pairing. With no answer the MAC is
  appended to `/pairing.json` and the wand resets, and the next boot connects. The first holder keeps the Splat.
- **Unpairing** (a held Splat's card, the `unpair` card, or a broadcast `{"type":"pw_release_all"}`, which also ends a
  running game on a paired wand) disconnects and clears the Splat without a reset. BLE stays active until the next
  reboot.
- **`/pairing.json`** is `{"splats": ["AB:42:00:00:7E:B6", ...]}` in tap order (local Splat 0, 1). It is session-scoped:
  a power-on reset (`machine.reset_cause() == machine.PWRON_RESET`) deletes it; soft, hard, watchdog and crash resets keep
  it. `lib/pairing.py` reads and writes it (atomic temp-file rename).
- **A Splat that is not READY** `splatpair.PAIR_CONNECT_MS` (30000) after boot is dropped from the file with error
  feedback. A Splat that drops later reconnects through `SplatLink` and stays paired.
- **Idle display of a paired wand:** each wand has an identity color, `splatpair.PALETTE[last MAC byte % 6]`, a
  `splat_api.COLOR_RGB` name (`turnred`, `turngreen`, `turnblue`, `turnpurple`, `turnyellow`, `turnwhite`). Each paired
  Splat glows dim in it (`GLOW_SCALE`), the wand shows it in matrix pixel 4, and a Splat's first connect in a boot flashes
  both and plays the success tone. The glow is restored after every game.
- **Idle timing:** a paired wand detects NFC with a 100 ms timeout and sleeps 20 ms per idle iteration (unpaired: 250 /
  200 ms), so it answers a `pw_who` inside the asker's 300 ms window.
- Splat presses at idle are not wired into the NFC action-chain engine.
- Limits: 2 Splats per wand. `unpair` is a control tag in this tree's `lib/game_tags.py` only; the other game-tag
  consumers (see `AGENTS.md`) do not list it.

### Boot order

`main()`: `pull_flag.is_pending()`, `_boot_grace()`, `enow.init()`, **`_boot_pairing()`**, then Stage 1 and the later
stages unchanged. `_boot_pairing()` reads `/pairing.json` inline (clearing it on a power-on reset). Only if a Splat is
paired does it import `ubluetooth`, call `BLE().active(True)`, and import `splatpair` (which imports `splat_hub`,
`splat_link`, `ble_splat`, `splat_api`) and build one `SplatHub` and `SplatGroup`. An unpaired wand never imports
`ubluetooth` or the Splat modules. `pairing`, `party` and `pwire` are imported inside `main()` after the radio is up, never
at module scope.

If the pairing file, `BLE().active(True)`, the imports or the hub fail, the wand boots unpaired: the file is deleted,
stage 0's data row shows amber in its third cell (ESP-NOW has the fourth), the traceback prints and
`{"type":"error","where":"pairing"}` is emitted.

Everything in `main.py` is compiled ahead of `enow.init()`, so the two boot functions and two module globals added for
pairing are allocated before the radio's block; `memprobe` figures with them are in the UNVERIFIED list.

## Party games

A game module is a **party game** if it defines module-level `SPLATS_MIN` (int >= 1: the total Splats across all joined
wands) and optionally `SPLATS_MAX` (`None` or int >= `SPLATS_MIN`). `main.py` reads them after `_load_play()` imports
the module; an invalid declaration is a load failure. A module without `SPLATS_MIN` runs as before.

### `play()` contract

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
```

`main.py` passes as many positional arguments as `play()` declares (6, 7 or 8). `net` is `None` for a game that is not a
party game. Every wand in a party game, leader and followers, calls the same `play()`; `net.is_leader` picks the role.
`play()` must return on `("end",)` and `("leader_lost",)`. A party game's `play()` that declares no `net` parameter still
goes through the lobby and then runs without it.

### Joining

Every wand taps the game's card. `party.enter()` broadcasts `pw_find` and listens `FIND_WAIT_MS` (500) for a `pw_lobby`
from a leader with an open lobby; if one answers, the wand joins it (`pw_join` / `pw_joined`), otherwise it becomes the
leader and broadcasts `pw_lobby` every second. Two leaders that hear each other: the lower MAC keeps its lobby, the other
joins it and its followers look again. The lobby shows Splats joined against `SPLATS_MIN` on the leader's matrix (green
once met) and an hourglass in the wand's identity color on followers. When the total reaches `SPLATS_MIN` the leader's
button starts the game; reaching `SPLATS_MAX` starts it at once. A `stop` card on the leader cancels the lobby for
everyone, on a follower it leaves. Wands with no Splats may join and count 0. Separate groups can play the same game at
once (different game ids).

### `net`

| Member | Meaning |
|---|---|
| `is_leader`, `me` | role, and this wand's index in `wands` |
| `wands` | `[(mac, identity color name, splat count), ...]` in join order, leader first |
| `local` | this wand's `SplatGroup`, or `None` if it holds no Splats. Direct BLE |
| `splat_count`, `owner(i)` | pool size; index in `wands` of the wand holding pool Splat `i` |
| `splat(i)` | leader only: pool Splat `i` with `color(name)`, `sound(name)`, `note(name)`, `play([names])`, `off()` (names as in `splat_api`); each returns True once done (remote: once ACKed) |
| `send(to, data)` | game message to wand index `to` (`None`: every other wand); `data` is a small dict (at most 200 bytes of JSON); True if every addressed wand ACKed |
| `poll()` | call every loop: services local Splats, runs proxied commands, sends heartbeats; returns one event or `None` |

Pool Splats are numbered by join order, each wand's contiguous in its local order; the leader's come first.

| Event | To | Meaning |
|---|---|---|
| `("press", i)`, `("release", i)` | leader: pool index. follower: local index | Splat button |
| `("msg", from_idx, data)` | addressed wand | a `net.send()` payload |
| `("splat_lost", i)`, `("splat_back", i)` | leader | a pool Splat's BLE link dropped, returned (a follower's, from its heartbeat) |
| `("wand_lost", idx)`, `("wand_back", idx)` | leader | no heartbeat for `WAND_LOST_MS` (3000), or the wand left; heard again |
| `("leader_lost",)` | followers | leader silent for `WAND_LOST_MS` |
| `("end",)` | everyone | the leader ended the game; also an ESP-NOW `stop` / `start_game` or a `pw_release_all`. Repeats once returned |

A follower's Splat presses go to the leader and are also delivered locally. Dropouts are reported, not handled: the game
decides whether to pause, continue or return. Unicast frames are retried up to `pwire.SEND_TRIES` (3) times on a missing
MAC ACK; the receiver drops a repeated per-sender sequence number `q`. Wire types are the `pw_` messages of SPEC section 8.

### Writing a party game

Pooled model: the leader's code decides and drives every Splat; followers can run a bare event loop.

```python
import time

SPLATS_MIN = 2

def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    while True:
        ev = net.poll()
        if ev in (("end",), ("leader_lost",)):
            return
        if net.is_leader and ev is not None and ev[0] == "press":
            owner = net.owner(ev[1])
            net.splat(ev[1]).color(net.wands[owner][1])   # light it in its owner's color
        time.sleep_ms(1)
```

Messages model: each wand drives its own Splats and the wands talk through `send()`.

```python
import time

SPLATS_MIN = 1

def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    while True:
        ev = net.poll()
        if ev is None:
            time.sleep_ms(1)
            continue
        if ev in (("end",), ("leader_lost",)):
            return
        if ev[0] == "press" and net.local is not None:      # follower: local index
            net.send((net.me + 1) % len(net.wands), {"go": ev[1]})
        elif ev[0] == "msg" and net.local is not None:
            net.local.unit(0).color("turngreen")
```

Rules: poll `net.poll()` every loop with a `time.sleep_ms(1)`; return on `end` and `leader_lost`; read the Splat colors
from `net.wands` and `net.owner(i)` rather than assuming them. Games in `games/`: `partytest.py` (button lights the next
pool Splat in the presser's identity color), `splattag.py` (pooled: the leader lights a random Splat, the first press
scores for its owner), `relaycolor.py` (messages: a color passes from wand to wand). `tools/deploy.py` copies
`games/` to `/games/` on the wand; each game must be on every participating wand, and its card reads its file name
(`partytest`, `splattag`, `relaycolor`).

## Tests (off-device)

From `Bag3/Code/BroadcastCode/`: `tools/devtests/compile_check.sh`, then
`python3 tools/devtests/<name>.py` for `test_wand_copies`, `test_wand_cards`, `test_wand_pairing_store`,
`boot_wand_pairing`, `boot_wand_idle`, `boot_wand_party`, `test_party`, `test_party_games`. `wandsim.py` is the shared
harness (virtual-time wand threads, fake ESP-NOW with loss / lost ACKs / duplicates, fake BLE Splats);
`wandboot.py` boots the real `main.py` under the stubs. These do not exercise hardware.

## UNVERIFIED on hardware

None of the Splat-pairing and party code has run on a board. Marked `UNVERIFIED on hardware` in the code where it lives,
and listed per step in `docs_and_design/2026-10-07-splat-pairing/PROGRESS-PartA.md`:

- `machine.reset_cause()` values on the C6 (power-on from USB or battery, `machine.reset()`, watchdog, crash).
- `idf_largest` after `main.py`'s imports, after `enow.init()`, after `BLE().active(True)`, and with 2 Splats READY, now
  that `main.py`, `nfc_reader.py` and `game_tags.py` are larger and the NFC reader, Stages 1-4 and the idle loop run.
- Real NDEF reads of a `splat-` card and the `unpair` card; Splat address types learned by discovery with pinned MACs.
- Claim-check latency against `CLAIM_WAIT_MS` with the paired idle loop (100 ms NFC timeout); the effect of the 100 ms
  timeout on card reads.
- How the identity colors, flash, tones and idle glow look and sound on the matrix and a Splat; palette distinctness.
- Whether a Splat stays connected through a non-party game, which does not poll the Splat links.
- ESP-NOW latency and the slow-send board: `pw_cmd` round trips, lobby timing (`FIND_WAIT_MS`, `JOIN_WAIT_MS`),
  `WAND_LOST_MS` against real loss, peer table with many wands.
- BLE and ESP-NOW coexistence on one C6 radio during a party game; Splat write pacing (50 ms) inside `net.poll()`.
- Lobby stop-card reads (every 8 loops, 40 ms timeout) and the games' stop-card reads (every 25 loops, 30 ms).
- `os.rename` over an existing file and `os.remove` on the C6's littlefs for `/pairing.json`.

## Deploy

Copy all `.py` files and `hubtype.txt` to the wand's flash root (same layout as
Bag3 Wand Module).
