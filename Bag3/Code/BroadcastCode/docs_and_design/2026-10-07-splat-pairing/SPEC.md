# Splat-paired wands — spec

A wand can pair with one or two specific Splats, identified by BLE MAC. A paired wand drives
those Splats over its own BLE radio (button in, color and sound out) alongside its own
inputs and outputs. Wands form ad hoc party games over ESP-NOW; a game declares how many
Splats it needs in total, and wands join it by tapping its game card.

Scope: `Bag3/Code/BroadcastCode/MockWand/` only. `Bag3/Code/Wand Module/` is not changed;
porting it is a separate, deliberate step. Splat Companions are not changed (see Known
issues).

## Terms

| Term | Meaning |
|---|---|
| Splat card | NFC card stuck to a Splat, text `splat-<12 hex>` |
| Paired wand | A wand holding BLE links to 1 or 2 Splats |
| Party game | A wand game whose module declares `SPLATS_MIN` |
| Leader | The wand that started a party game; runs its roster and logic |
| Follower | A wand that joined a leader's party game |
| Pool | Every Splat held by every wand in the game, indexed `0..N-1` by the leader |

## 1. Splat card

- Text: `splat-` followed by the Splat's BLE MAC as 12 hex digits, no separators, e.g.
  `splat-AB4200007EB6`. Parsing is case-insensitive; the stored form is uppercase with
  colons (`AB:42:00:00:7E:B6`), matching `SplatHub(macs=...)`.
- Plain NDEF text, same as every other wand card. Not a game tag and not a
  `<prefix>:<slug>` card; `nfc_reader` gets a separate `splat-` match.
- The card carries no address type. The wand learns it from the first scan that sees the
  MAC (`SplatHub` discovery with pinned `macs`), as the Splat Companion does today.

## 2. Pairing state

- Stored on flash at `/pairing.json`: `{"splats": ["AB:42:...", ...]}`, in tap order, at
  most 2 entries. Tap order is local Splat order (`unit(0)`, `unit(1)`).
- **Session-scoped:** at boot, if `machine.reset_cause() == machine.PWRON_RESET`, the file is
  deleted. Soft resets, hard resets, watchdog and crash resets keep it. Switching the wand off
  ends every pairing.
- The file is read after `enow.init()` (see §4), never at module scope.

## 3. Pairing and unpairing (idle loop only)

Splat cards are handled only in `main.py`'s idle loop. A Splat card tapped during a game is
ignored.

**Tap a Splat card this wand does not hold:**

1. If the wand already holds 2 Splats: error feedback (`SHAPE_X`, red, low tone); nothing
   changes.
2. Claim check: broadcast `{"type":"pw_who","m":<mac>}`, then listen `CLAIM_WAIT_MS`
   (300). Any wand holding that MAC answers by unicast `{"type":"pw_held","m":<mac>}`.
   If an answer arrives: error feedback, nothing changes.
3. Otherwise append the MAC to `/pairing.json` and `machine.reset()`. The next boot brings
   BLE up (§4) and connects.

**First holder keeps the Splat.** There is no stealing. A holder that is out of range or off
doesn't answer the claim check; the new wand then fails to connect after reset (§4) and
drops the entry itself.

**Unpair**, any of:

| Trigger | Effect |
|---|---|
| Tap a Splat card this wand holds | That link disconnects, the MAC is removed from the file. No reset. |
| `unpair` card | Every link disconnects, the file is deleted. No reset. |
| Power off | §2 |
| ESP-NOW `{"type":"pw_release_all"}` | Same as the `unpair` card, on every wand that hears it. Handled in the idle loop and as a game exit. |

After an unpair, BLE stays active until the next reboot (turning it off and back on mid-session
risks the memory failure in §4). Adding a pairing always resets, even when BLE is
already up: rebuilding `SplatHub` with a different count is avoided.

## 4. Boot order

`AGENTS.md`: nothing may allocate before the radio claims its memory. The new order in
`main()`:

1. `pull_flag.is_pending()` (unchanged, first).
2. `_boot_grace()`, `enow.init()` (unchanged).
3. Read `/pairing.json`, clearing it on power-on reset (§2). Inline file read; the
   `pairing` module is not imported yet.
4. If any Splats are paired: `import ubluetooth; ubluetooth.BLE().active(True)`, then
   import `splat_hub` / `splat_link` / `ble_splat` / `splat_api` and build
   `SplatHub(macs=<file>)` and one `SplatGroup`. This happens before Stage 1 (OPT3002)
   and every later boot stage.
5. Remaining boot stages, unchanged.

An unpaired wand never imports `ubluetooth` or the Splat modules.

Failure handling:
- `BLE().active(True)` raises: the wand boots unpaired (file deleted), shows amber in stage
  0's data row, and logs the error. ESP-NOW is unaffected.
- A Splat that is not READY within `PAIR_CONNECT_MS` (30000) of boot is dropped from the
  file, with error feedback. A Splat that drops later reconnects through `SplatLink`'s
  existing retry; it stays paired.

Measured on a MockWand with `main.py`'s module-scope imports and hardware objects loaded
ahead of the radio ([RESULTS-M1.md](RESULTS-M1.md), one run): `idf_largest` 208896 after
imports, 172032 after `enow.init()`, 143360 after `BLE().active(True)`, 143360 after the Splat
modules, 135168 with 2 Splats READY. Not covered: the NFC reader, Stages 1-4 and the idle
loop running.

## 5. Idle behavior of a paired wand

- **Identity color:** each wand has a color from its own MAC (`mac[-1] % len(PALETTE)`, a
  6-8 entry palette of colors distinct on both the wand matrix and a Splat).
- Each paired Splat glows dim in that color while idle; refreshed after reconnect and after
  every game.
- The wand shows the same color in one corner pixel while paired, so wand and Splat can be
  matched by eye.
- Pair success: wand and Splat flash the identity color and the wand plays a rising tone.
- `SplatGroup.poll()` runs every idle-loop iteration (keepalives, reconnects). Splat presses
  are not wired into the NFC action-chain engine.
- The idle loop answers `pw_who` for held MACs, and answers `pw_find` (§6) only when the
  slug names a party game it has been tapped into.

## 6. Party games

### Declaring

A game module is a party game if it defines module-level constants:

```python
SPLATS_MIN = 2      # total Splats across all joined wands
SPLATS_MAX = 6      # optional; None = no cap
```

`main.py` reads them after `_load_play()` imports the module. A module without
`SPLATS_MIN` is an ordinary game and runs exactly as today.

### Starting and joining

Every wand taps the game card. On tap of a party game:

1. Broadcast `{"type":"pw_find","g":<slug>}` and listen `FIND_WAIT_MS` (500) for a
   `{"type":"pw_lobby","g":<slug>,"id":<game id>,"n":<splats so far>}` from a leader whose
   lobby is open.
2. **Answer received:** join it. Unicast `{"type":"pw_join","id":...,"splats":<count>}`;
   the leader replies `pw_joined` with this wand's Splat pool indexes. If several leaders
   answer, the first answer wins.
3. **No answer:** become leader. Game id is the leader's MAC last 2 bytes plus a 1-byte
   counter. Broadcast `pw_lobby` every 1 s while the lobby is open.
4. Two wands that tap within the same window both become leaders. A leader that hears another
   leader's `pw_lobby` for the same slug with a lower MAC closes its lobby and joins that one.

Wands that did not tap are not affected; separate groups can run the same game at once
(different game ids).

### Lobby

- The leader's matrix shows Splats joined vs `SPLATS_MIN` (filled pixels); followers show a
  waiting icon in their identity color.
- When the total reaches `SPLATS_MIN`, the leader's button starts the game. Reaching
  `SPLATS_MAX` starts it automatically.
- A `stop` card on the leader cancels it for everyone (`pw_end`). On a follower it leaves the
  lobby (`pw_leave`).
- Plain (unpaired) wands may join and count as 0 Splats.

### Calling the game

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
```

`net` is passed only to a game whose `play()` accepts it (existing arity detection in
`_start_play()`, extended to 8 parameters). Every wand in the game, leader and followers,
calls the same `play()`; `net.is_leader` selects the role. `net` is `None` for non-party
games.

## 7. The `net` object (`lib/party.py`)

| Member | Meaning |
|---|---|
| `is_leader` | bool |
| `me` | this wand's index in `wands` |
| `wands` | list of `(mac_str, identity_color, splat_count)`, in join order, leader first |
| `local` | this wand's `SplatGroup`, or `None` if unpaired. Direct BLE, no ESP-NOW |
| `splat_count` | pool size |
| `splat(i)` | pool Splat `i` (leader only): `color(name)`, `sound(name)`, `note(name)`, `play([names])`, `off()`, same names as `splat_api` |
| `owner(i)` | wand index holding pool Splat `i` |
| `send(to, data)` | game message to wand index `to` (`None` = every other wand). `data` is a small dict |
| `poll()` | call every loop. Services local Splats, executes proxied Splat commands, heartbeats. Returns one event or `None` |

Events from `poll()`:

| Event | Delivered to | Meaning |
|---|---|---|
| `("press", i)` / `("release", i)` | leader: pool index; follower: local index | Splat button |
| `("msg", from_idx, data)` | addressed wand | `net.send()` payload |
| `("splat_lost", i)` / `("splat_back", i)` | leader | a pool Splat's BLE link dropped / returned |
| `("wand_lost", idx)` / `("wand_back", idx)` | leader | follower heartbeat missed for `WAND_LOST_MS` (3000) / resumed |
| `("leader_lost",)` | followers | leader heartbeat missed for `WAND_LOST_MS` |
| `("end",)` | followers | the leader ended the game |

**Dropouts are the game's decision.** `party.py` only reports them. The game chooses to pause,
continue or return.

Both models are available:
- **Pooled:** leader code drives any Splat by pool index; followers' `poll()` executes the
  commands. A follower's `play()` can be a bare `while net.poll() != ("end",): ...` loop.
- **Messages:** each wand drives its own `local` Splats and exchanges game-specific
  messages with `send()`.

A follower's Splat presses go to the leader as pool events, and are also delivered locally on
the follower as `("press", local_i)`.

## 8. Wire protocol

JSON over ESP-NOW through `espnow_manager` (arrives as `"raw"` in existing loops, so
non-party games and old firmware ignore it). Every message carries `"type"` with prefix
`pw_`, and in-game messages carry `"id"` (game id).

| type | Direction | Transport | Fields |
|---|---|---|---|
| `pw_who` | any → all | broadcast | `m` |
| `pw_held` | holder → asker | unicast | `m` |
| `pw_release_all` | teacher/hub → all | broadcast | — |
| `pw_find` | tapper → all | broadcast | `g` |
| `pw_lobby` | leader → all | broadcast, 1 s | `g`, `id`, `n`, `min`, `max` |
| `pw_join` / `pw_joined` / `pw_leave` | follower ↔ leader | unicast | `id`, `splats` / `first`, `wands` |
| `pw_start` | leader → followers | unicast | `id`, `wands`, `pool` |
| `pw_cmd` | leader → owner | unicast | `id`, `q`, `s` (local idx), `op`, `v` |
| `pw_evt` | owner → leader | unicast | `id`, `q`, `s` (pool idx), `e` (1 press / 0 release) |
| `pw_msg` | wand → wand | unicast | `id`, `q`, `d` |
| `pw_hb` | every wand | broadcast, 1 s | `id`, `l` (local Splats READY bitmask) |
| `pw_end` | leader → all | unicast to each follower | `id` |

- Unicast is synchronous `ESPNow.send()` (MAC-layer ACK) with up to `SEND_TRIES` (3)
  attempts. `q` is a per-sender sequence number; a receiver drops a `q` it has already seen
  from that sender (a lost ACK causes a resend).
- Every party member is added as an ESP-NOW peer at join and removed at game end.
- Heartbeats are broadcasts so a slow unicast path doesn't cause false `wand_lost` events.

## 9. Limits

- 2 Splats per wand (pairing refuses a third). `SplatHub` allows 4; 2 is the tested C6 count.
- Pool size has no hard cap beyond the roster. ESP-NOW peer table: 20 unencrypted peers by
  default.
- Splat write pacing: `ble_splat._WRITE_PACE_MS` = 50 ms per Splat. A pooled command
  costs one ESP-NOW unicast plus one paced BLE write.

## 10. Known issues

- **Leader is a single point of failure.** If the leader drops, the game ends (followers get
  `leader_lost`). The target design is symmetric peers (shared state by broadcast, no host);
  the leader model is a first step.
- **Slow ACKed unicast on one board, cause not found.** In [RESULTS-M1.md](RESULTS-M1.md),
  synchronous send time follows the sending board: MockWand `usbmodem1101` takes 6.7-28.5 ms
  p50 (bulk 5-9 KB/s), `usbmodem3101` takes 1.6-1.7 ms (bulk 49-50 KB/s). BLE, Splat links,
  connection interval, send gap and power save don't change it. Not yet compared: the boards'
  hardware, their `/lib` copies, USB power. A wand like 1101 adds tens of ms to every pooled
  command and remote press. The 169-3333 ms round trips in `2026-10-07-coex-benchc6` were
  mostly the bench not draining replies between sends.
- **Single-chip coexistence on the wand.** The Splat Companion uses a separate modem board for
  ESP-NOW; the wand runs BLE and ESP-NOW on one C6 radio. Measured only with the bench
  scripts, not with `main.py`'s import load, the NFC reader or the LED matrix running.
- **Splat Companions are unaware of pairings.** A companion without `splat_macs` takes the
  first Splats it finds by name, which may be a Splat a wand is about to pair with. Rooms
  should pin companion MACs or not mix the two.
- **Offline holders.** First-holder-keeps relies on the holder answering `pw_who`. A holder
  out of range is detected only by the new wand's 30 s connect failure.
- **`unpair` is a new control tag** in `MockWand/lib/game_tags.py` only. The other tag
  consumers (`hubCode2/game_tags.py`, `commands.json`, `wand_icons.html`, each Bag's
  `lib/game_tags.py`) are not updated.
- **New PEER copies.** `splat_hub.py`, `splat_link.py`, `splat_api.py` and `ble_splat.py` go
  into `MockWand/lib/` as copies of `SplatCompanion/Companion/`'s. `splat_api.py` remains the
  source of truth for action names (`sync_splat_actions.py` reads the companion copy).
- **Splat battery** with an idle glow on for a whole session is unmeasured.
- **`pw_release_all` has no sender yet.** Live_Page and the Box do not send it.

## 11. ChatBroadcast (next phase, not implemented here)

What generating party games will need:

- **Prompt:** the wand system prompt gains the 8-parameter `play()`, `SPLATS_MIN` /
  `SPLATS_MAX`, the `net` table (§7), the event list, and the rule that one `play()`
  serves both roles via `net.is_leader`. Splat action names reuse the generated
  `js/splat/splatActions.js` list, already built from `splat_api.py`.
- **Send-time validation:** refuse a wand game that uses `net` without accepting it in
  `play()`'s signature, or that declares `SPLATS_MIN` without using `net`; refuse
  Splat action names outside `splatActions.js` (same rule as Splat games); check that
  `SPLATS_MIN` is an int ≥ 1 and `SPLATS_MAX` ≥ `SPLATS_MIN` or `None`.
- **Card printing:** the game's card is an ordinary wand game card; every participant taps the
  same card. ChatBroadcast should say so in the game's instructions.
- **Direct-USB install** (`wandGameInstaller.js`) installs to one wand. A party game has to be
  on every participating wand; the leader does not distribute code. Pulls via Box/Dial
  already work per wand.
- **Known issues for generation:**
  - Two-role code in one function is harder for the model to get right than single-wand
    games. Prompt with one worked example of each model (pooled, messages).
  - Dropout handling is left to the game, so generated games will often ignore
    `splat_lost`/`wand_lost`. The prompt should require handling `leader_lost` and `end`
    (return from `play()`).
  - Pooled Splat latency (Known issues) makes fast reaction games unreliable; the prompt
    should steer toward turn-based or local-reaction designs.
  - No simulator support: `Simulator/` and the boot stubs have no `net` or BLE fake yet.
  - The identity palette and pool indexing are runtime facts; a generated game cannot assume a
    Splat's color or owner and must read `net.wands` / `net.owner(i)`.
