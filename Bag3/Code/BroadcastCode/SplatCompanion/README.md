# Splat Companion

Bag3 broadcast station that runs games on a stock, unmodified Splat toy
over BLE. ChatBroadcast can generate games for it and a Broadcast Box or
Dial can serve them, per
`Bag3/Code/BroadcastCode/docs_and_design/DEVICE_ONBOARDING_SURFACES.md`.

```
SPLAT <-[BLE]-> companion (XIAO C6) <-[UART]-> modem board <-[ESP-NOW]-> playground
```

It is a games-only station, like the icon display: between games it keeps
the Splat connected and waits for a game card or an ESP-NOW `start_game`.
Nothing plays on a Splat press while idle, and no other device drives the
Splat directly.

Status: passes the CPython simulation (`test_splat_companion.py`) and a
stubbed boot smoke test (`../tools/devtests/boot_splat.py`).
**Not yet run on hardware.** See `HARDWARE_TEST.md`.

## Hardware

- **Host:** Seeed XIAO ESP32-C6. `hubtype.txt`: `splat_companion`.
  - BLE to one Splat (default) or up to 4, on its own radio -- see
    "Multiple Splats".
  - ESP-NOW to the rest of the playground, over UART1 to a paired modem board (`../EspnowModem/`)
    running `modem/main.py` -- never on this board's own radio, so BLE and
    ESP-NOW run at the same time without the coexistence problems the Bag2
    companion has (see "How this differs" below).
  - PN532 card reader, same I2C wiring as the wand (0x24).
  - MAX17048 battery gauge, same bus.
  - 3-pixel NeoPixel status strip.
- **Modem:** an M5StickS3 or a second XIAO ESP32-C6 (`../EspnowModem/README.md`,
  "Modem on an ESP32-C6" -- UNVERIFIED on hardware either way).

## Wiring (XIAO ESP32-C6 host ↔ modem)

| Host | Modem (S3) | Modem (C6) |
|---|---|---|
| GPIO0 (D0, TX) | GPIO44 (RX) | GPIO1 (D1, RX) |
| GPIO1 (D1, RX) | GPIO43 (TX) | GPIO0 (D0, TX) |
| GND | GND | GND |

- **Why GPIO0/1 on the host:** GPIO20 drives the status LEDs, GPIO22/23 are
  I2C (PN532 + MAX17048), and GPIO16/17 (D6/D7) carry the boot log over the
  C6's default UART0. GPIO0/1 are free and not strapping pins. UNVERIFIED
  on a real board.
- **Pins are constants**, not hubtype-driven: `MODEM_UART_TX` /
  `MODEM_UART_RX`, set on `espnow_manager` before `mgr.init()` in `main.py`
  (see "Memory order and boot" below) -- `lib/espnow_manager.py` itself
  stays a byte copy of `../EspnowModem/host/lib/espnow_manager.py`.
- **Power:** the modem needs its own supply; see `../EspnowModem/README.md`.

## Layout

| Path | Purpose |
|---|---|
| `main.py` | Entry point: pull check, boot, dispatch, idle loop |
| `companion.py` | Idle station: keeps the BLE link up, handles `start_game`/`stop`, status LEDs |
| `splat_link.py` | `SplatLink(OpenSplat)`: non-blocking BLE connect/reconnect, IRQ-safe button debounce |
| `splat_hub.py` | `SplatHub`: one or more `SplatLink`s on the one BLE radio; routes IRQ events per link, one scan at a time |
| `splat_api.py` | `SplatAPI` (one Splat) and `SplatGroup` (the `splat` object games receive); the single source of the action names |
| `status_leds.py` | The 3-pixel strip: `fill()`, `off()` |
| `companion_probe.py` | Diagnostics, imported only when `DEBUG_PROBE = True` |
| `splatwhack.py` | Built-in game |
| `code_puller.py`, `pull_flag.py`, `pull_probe.py` | PEER copies of MockWand's (unchanged wire behaviour; `code_puller.py`'s docstring/PEER comment adapted, and it alone owns the antenna select -- see below) |
| `boot.py` | Docstring only, IconDisplay-style: outputs are built in `main.py`, after BLE |
| `lib/game_store.py`, `lib/memprobe.py`, `lib/nfc_reader.py`, `lib/pn532.py`, `lib/max17048.py` | PEER copies of MockWand's / `Bag3/Code/lib`'s, unchanged |
| `lib/hubtype.py` | This tree's own `splat_companion` entry -- **diverges from the other four copies**, see "Drift" |
| `lib/splat_tags.py` | `GAME_TAGS = {"splatwhack"}`, `CONTROL_TAGS = {"stop", "getcode"}`, `EXIT_TAGS`, `exit_tags_excluding()` |
| `lib/espnow_manager.py`, `lib/eum_proto.py` | Byte copies of `../EspnowModem/host/lib/` |
| `lib/ble_splat.py` | Byte copy of `Bag3/Code/lib/ble_splat.py` |
| `test_splat_companion.py` | CPython simulation (reuses `../EspnowModem/tests/test_sim.py`'s modem/host harness plus a fake BLE Splat) |

`../tools/devtests/boot_splat.py` boots `main.py` under stubs (dispatch
check, game load/unload, the arity fallback, a force-switch chain, loud
failure, and the pull-mode boot order and outcomes).

## Memory order and boot

`main.py`'s `pull_flag.is_pending()` check is the first thing that can
touch pull state; **nothing above it may import `ubluetooth`,
`espnow_manager`, or any other radio-claiming module** (AGENTS.md rule 1;
`pull_flag.py`'s docstring has the underlying measurement). Only on a
normal (non-pending) boot does BLE come up, and it comes up before
anything else *activates a radio* -- `import ubluetooth;
ubluetooth.BLE().active(True)` runs before ESP-NOW (over UART, via the
modem) or the PN532/MAX17048 are touched. `memprobe.probe()` calls
bracket each stage; the module-level imports ahead of BLE (game tables,
the NFC/PN532 driver classes, the 3-pixel strip) mirror what MockWand's
own `main.py` allocates ahead of `enow.init()` -- UNVERIFIED at this size
combination on this device; the bench run checks it.

**Boot order:**
1. `pull_flag.is_pending()` -> `_run_pull_mode()` if set (WiFi join to a
   Box/Dial, `code_puller.pull(hubtype="splat_companion")`, then reset).
2. BLE up, `SplatHub` (one `SplatLink` per configured Splat) and the one
   `SplatGroup` created (shared by the idle loop and every game).
3. ESP-NOW via the modem (`mgr.init()`), then the battery gauge and PN532
   (each optional -- a missing one costs only that capability).
4. Identity emitted, `take_last_pulled()` auto-launches a just-pulled game.
5. `run_event_loop()`: `Companion.step()` runs when idle, and a game tag
   -- tapped, or arriving as ESP-NOW `start_game` -- launches a game; the
   idle loop resumes when it returns.

## The `play()` contract

```python
def play(splat, leds, enow, batt=None):
    ...
```

- **`splat`** (`splat_api.SplatGroup`): `connected`, `poll()` (call every
  loop -- services the BLE links and returns `"press"`/`"release"`/`None`),
  `color(name)`, `sound(name)`, `note(name)`, `play([names])`, `off()` --
  each acting on every connected Splat -- plus `count`, `connected_count`,
  `last_index` (which Splat the last event came from) and `unit(i)` (one
  Splat's own `SplatAPI`). With the default one Splat it behaves as that
  Splat's `SplatAPI`.
  Action names are the tables in `splat_api.py` (`COLOR_RGB`,
  `NOTE_VALUES`, `ANIMAL_SOUNDS`): the wand's action-card names. After
  editing any of them, run `python3 ChatBroadcast/tools/sync_splat_actions.py`
  (from `BroadcastCode/`): ChatBroadcast puts the generated list in its
  system prompt and refuses to send a Splat game that names anything else.
- **`leds`**: this device's 3-pixel strip, `fill(color)` / `off()` -- not
  a wand's 25-pixel matrix.
- **`enow`**: an already-initialised `ESPNowManager` (the EUM drop-in).
  Poll every loop; return on `"stop"` or a `start_game` naming another
  game.
- **`batt`**: a `MAX17048`, or `None` if the gauge failed at boot.

No NFC parameter: a game cannot read cards itself. While it runs,
`main.py`'s `_GameEnow` wrapper checks the reader (at most every
`NFC_GAME_POLL_MS` = 150 ms, `NFC_GAME_TIMEOUT_MS` = 30 ms per check) and
delivers a tapped card through `enow`:

| Card tapped mid-game | Arrives as |
|---|---|
| `stop` | `("stop", {}, None)` |
| another game on this station | `("start_game", {"name": ...}, None)` -- chained without returning to idle |
| `getcode:<slug>` | not delivered: the pull is queued and the station resets |
| the game's own card | ignored, as is the launching card until it leaves the reader |

So a game that returns on `"stop"`/`"start_game"` exits on cards too.
UNVERIFIED on hardware: each check can hold the game for up to 30 ms.

## Deploying (plain MicroPython: `/` and `/lib/`)

```bash
cd Bag3/Code/BroadcastCode/SplatCompanion
python3 -m mpremote connect $COMP_PORT resume \
  fs cp main.py companion.py splat_link.py splat_hub.py splat_api.py status_leds.py \
        companion_probe.py splatwhack.py code_puller.py pull_flag.py \
        pull_probe.py boot.py hubtype.txt : + \
  fs mkdir :lib + \
  fs cp lib/*.py :lib/
python3 -m mpremote connect $COMP_PORT reset
```

`fs mkdir` fails if `/lib` already exists; drop that step then. The modem
runs the unchanged `../EspnowModem/modem/` firmware -- no new ESP-NOW
message codes were added, so it needs no reflash for this device.

## Multiple Splats

One companion can hold BLE connections to several Splats at once. It is
off by default; set it in `lib/hubtype.py`'s `splat_companion` entry:

| Key | Default | Meaning |
|---|---|---|
| `max_splats` | `1` | Splats to connect, 1 to `splat_hub.BLE_MAX_CONNECTIONS` (4) |
| `splat_macs` | `None` | `None`: the first `max_splats` Splats found by name. A list of MAC strings pins specific Splats and their order (`unit(0)`, `unit(1)`, ...); its length is the count |

- **Limit:** 4, the stock MicroPython ESP32 build's
  `CONFIG_BT_NIMBLE_MAX_CONNECTIONS` (`ports/esp32/boards/sdkconfig.ble`).
  The companion is BLE central only, so all 4 can be Splats. A value above
  4 prints `[ERR]` at boot and runs with 4. A custom firmware build could
  raise the limit (`BLE_MAX_CONNECTIONS` in `splat_hub.py`), at a NimBLE
  heap cost per connection on a board with no PSRAM.
- **Why a hub:** `ubluetooth.BLE()` has one IRQ handler, and
  `lib/ble_splat.py`'s `OpenSplat` (an unmodified byte copy) registers its
  own per instance without filtering by connection. `SplatHub` takes the
  IRQ over and routes each event to its link; only one link scans at a
  time; a link locks onto the first Splat it picks for the length of an
  attempt, and never onto one another link owns.
- **Write cost:** each BLE write waits up to 20 ms (`_WRITE_PACE_MS` in
  `ble_splat.py`) per Splat, so `splat.color()` on 4 Splats can hold the
  loop for about 80 ms. Keepalives are per Splat too.
- **Status LEDs:** with 2 or 3 Splats, pixel *i* shows Splat *i* (blue
  waiting, cyan ready). With 4, the whole strip is blue until every Splat
  is ready.
- **Games:** a game must still work with `splat.count == 1` -- the count
  is set per device, and a generated game cannot know it.
- **UNVERIFIED on hardware** for more than one Splat. Bench 2 before 4
  (`HARDWARE_TEST.md`, step 9).

## Messages while idle (`companion.py`)

| Message in | Effect |
|---|---|
| `{"type": "start_game", "name": "..."}` | Bubbles to `main.py`, which launches the game if it's one this station has; any other name is printed and ignored |
| `{"type": "stop"}` / `["stop"]` | `splat.off()` |
| anything else | Counted as ignored |

The station sends nothing and adds no ESP-NOW peers while idle. A game
that wants other devices to know about a press broadcasts its own message.
The Bag2 companion's `splat_config`/`splat_cmd`/`splat_event` messages are
not handled here.

## Status LEDs (idle)

| Color | Meaning |
|---|---|
| Red, solid | Modem link down, or no modem found at boot |
| Blue, solid | BLE not ready (scanning/connecting) -- any Splat, when several |
| Cyan, breathing | Ready, waiting for a game |
| One pixel per Splat, blue/cyan | 2 or 3 Splats configured: that Splat waiting/ready |

A game gets the same 3-pixel strip via `leds.fill()`/`leds.off()` and may
use it however it likes; the idle loop repaints its own state once the
game returns.

## Drift and findings (flagged, not reconciled)

- **`lib/hubtype.py` diverges from its four peers.** This tree's
  `"splat_companion"` entry has `has_nfc: True`, `nfc_addr: 0x24` and
  `i2c_freq: 100_000` (shared with the PN532); `MockWand/lib/`,
  `Bag3/Code/lib/` and `Bag2/Code/lib/` still carry the earlier bridge-only
  entry (`has_nfc: False`, `i2c_freq: 400_000`). See `docs/KNOWN_ISSUES.md`.
- **Note names:** cards and Bag2's `lib/actions.py` use `note_a` … `note_c_high`;
  the Bag2 companion uses `notea` … `noteb` and drops card names silently.
  This device accepts card names only.
- **Note values, release command, switch polling, and note-triggering
  quirks** inherited from the Bag2/Jan-2026 companions -- see the git
  history of this file (`companion.py`'s introduction, commit `50fe511`)
  for the fuller writeup; unresolved on hardware either way.
- **`ble_splat.py` debounce and scan race:** `OpenSplat._handle_button`
  drops a release under 80 ms after the press (fixed by `SplatLink`'s
  override, not by the shared driver); a late `SCAN_DONE` can make the
  next `gap_scan()` raise `EALREADY` (`SplatLink` retries instead of
  failing). Not fixed in `Bag2/Code/lib/` or `Bag3/Code/lib/`.
- **`Bag2/Code/Splat Companion/ble_splat.py`** actually holds the wand-side
  controller, not the `OpenSplat` driver its own `main.py` imports.

## Not done

- Hardware bench run of any kind (modem link, BLE, NFC, pull, a game).
- Several Splats per companion on hardware (simulated only; see
  "Multiple Splats").
- Wand-side code that sends `start_game` naming a Splat game.
- The EUM's acknowledged-fetch fix (`../EspnowModem/README.md`) -- a
  timed-out `FETCH` still loses up to 4 messages.
