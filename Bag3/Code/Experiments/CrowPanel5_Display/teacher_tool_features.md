# Teacher tool features: current tools

What each existing tool does today, by teacher task, taken from the code. Input for the CrowPanel5
Display teacher tool, which combines them.

Tools compared:

- **M5Paper Remote:** `Bag3/Code/TeacherTools/M5Paper Remote/`. Never tested on hardware.
- **Broadcast Dial:** `Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/`, the M5 Dial firmware.
- **WebApp2:** `Live_Page/WebApp2/`, the browser app and its `hubCode2/` C6 hub.
- **ChatBroadcast:** `Bag3/Code/BroadcastCode/ChatBroadcast/`, the browser app that drives a Dial over
  USB.

The NFC Station (`TeacherTools/NFC Station/`) has the same NFC screens as the Dial, but no radio and no
code serving. Where it differs, the table notes it.

## Kinds of send

| Kind | Meaning | Where it exists |
|---|---|---|
| Broadcast | Sent to FF:FF:FF:FF:FF:FF; every device acts on it | M5Paper Remote, WebApp2 hub |
| Broadcast + MAC | Broadcast carrying a `mac` field; only that device acts | `find_device`: Remote, hub and Dial (`fleet.find`) |
| Single device | Sent to one MAC as a temporary peer, with a MAC-layer ack | Dial `code_push` |
| Several devices | One addressed send per MAC in a list, staggered | Dial `fleet.distribute`, `code_push` only |

**Needed:** a selection between one device and everyone, as a list of MACs. It should carry every
action: start game, stop, send code and find. Today only `fleet.distribute` sends to a list, and only
for code.

## Features by teacher task

`—` = not present.

| Teacher task | M5Paper Remote | Broadcast Dial | WebApp2 (+ hub) | ChatBroadcast |
|---|---|---|---|---|
| **Make a new game** | — | — | — | Chat to code; makes `<slug>.py` and `<slug>.tags.json` |
| **Load a game onto the hub device** | — | Gets games over the USB REPL, then soft-resets; the boot scan adds them to `index.json` | — | Writes the game files to the Dial (`boxFirmwareInstaller.js`) |
| **See and manage stored games** | — | `games.list/select/delete/clear`; one active game; pull and write counts | — | Library overlay: list, pull count, delete, Distribute |
| **Choose which games show** | Settings checklist of 14 hard-coded games (`settings.json`) | Every stored game | `commands.json`, 19 games; Beta toggle changes nothing | — |
| **Send game code to every device** | — | Serves the active game to any wand that taps a `getcode:<slug>@HOSTID` card (pull) | — | — |
| **Send game code to chosen devices** | — | `fleet.distribute {slug, macs[]}`: one addressed `code_push` per MAC, staggered, at most 3 in flight; reports progress | — | Distribute overlay: pick rows, progress bar, per-row result, cancel (`fleet.cancel`) |
| **Start a game on every device** | Tap a game button: `start_game`, sent twice | — | Game tile: `start_game` sent through the hub, twice | — |
| **Start a game on one device** | — | — (`code_push` path could carry it) | — | — |
| **Start a game on several devices** | — | — | — | — |
| **Stop every device** | STOP button: `["stop"]`, sent twice | — (the `stop` card can be written) | Stop tile: `["stop"]`, sent twice | — |
| **Stop one or several devices** | — | — | — | — |
| **Find nearby devices** | Status button: `status_poll` sent 3 times; 6 s window | `fleet.scan`: same poll; results go to the host only, not shown on the Dial | Poll tile: same poll through the hub | Distribute overlay runs `fleet.scan` |
| **See device details** | Name W-/D-/?- plus last 4 MAC digits, battery %, signal bars and word; paged | Sends `status_report {mac, kind, battery, rssi}` to the host | Name W-xxxx, battery, signal icon, time; type is always "module" | Row: name, type, battery, signal bars (dBm on hover) |
| **See what each device is running** | Local highlight of the last game sent; not confirmed by any device | — | — | — |
| **Name a device** | — | — | — | Nickname per browser (localStorage, keyed by MAC) |
| **Make one device identify itself** | Tap its Status row: `find_device`, broadcast + MAC, 3 times | `fleet.find {mac}`, broadcast + MAC | Tap its device card: `find_device` | Find button on each row |
| **Confirm that a device acted** | — | MAC-layer ack on `code_push`; `code_done {ok, why}` after a pull | Hub acks "sent" only | Shows Getting code / Updated / Failed (why) |
| **Write game cards** | — | Tags: All, Code (`getcode`), Play, then the game's tags; Utility: `stop`, `battery`. NFC Station: built-in catalog | — | Written-tag checklist per game |
| **Write a custom card** | — | Text: rim keyboard, word bank, 54-byte limit | — | — |
| **Read or copy a card** | — | Read shows the text; click copies it to the next card | — | — |
| **Check battery of the hub device** | Battery %; Battery Low sleep screen | — | — | — |
| **Connect the hub device** | Standalone | Standalone, or USB to ChatBroadcast | Web Serial to the hub; hub setup uploads firmware | Web Serial to the Dial |

## Limits that hold across tools

- Status replies carry `kind`, `battery` and `rssi` only, not the current game or firmware version.
- Signal strength is the wand's reading of the sender, sent back in its reply.
- Device lists exist only for a 6 s window after a poll. Nothing tracks devices continuously.
- On the Dial, the radio serves only on HOME, GAMES and TAGS; the NFC field and the radio are never
  on together.
- Card text is limited to 54 bytes, because the wand reads 64 bytes.
- Not tested on hardware: the Dial's scan and distribute, and the M5Paper Remote
  (`Bag3/Code/known_issues/2026-10-23-distribute-code.md`).
