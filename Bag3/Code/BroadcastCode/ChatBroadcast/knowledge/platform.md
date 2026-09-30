# Platform rules shared by every device

Every SmartPlayground device runs MicroPython on an ESP32 board. Each device type has its own game
file format, documented in its own device section. The rules here apply to all of them.

## Output markers

The app reads these marker lines out of your reply and hides them from the teacher.

- **`[DEVICE: <role>]`** on its own line directly before **every** code block. `<role>` is the
  device key given in the device section (`wand`, `icon`, `splat`). An unmarked block is treated as
  wand code.
- **`[GAME_NAME: Short Pretty Name]`** exactly once after the code blocks. Two to four plain words,
  no file extension. The app turns it into the game's stored name (its *slug*): lowercase, with
  runs of anything that is not a letter or digit replaced by one underscore. "Jumping Frogs" →
  `jumping_frogs`.
- **`[NFC_CARDS: "value1", "value2"]`** exactly once if any game file reads NFC cards, listing every
  card value the game reacts to. Leave it out only when no file reads a card. The app uses it to
  tell the teacher which cards to write.
- **`[CHOICES: "option one", "option two", "option three"]`** optionally, as the very last line.
  Two to four short follow-up changes the teacher can tap instead of typing. Write each as the
  request the teacher would send ("Make it slower", "Add a winning song").

## One file per device

A game that uses several device types is one file per device, each in its own fenced block with
its own `[DEVICE:]` marker. They are separate programs that talk over ESP-NOW. Never write one file
with a mode switch, and never import one device's game file from another's.

Send only the files that changed. A reply that changes only the wand game contains only the wand
block; the other devices keep their current code.

## MicroPython rules

- **No f-strings.** They crash on this MicroPython build. Use `%` formatting:
  `print("score %d" % score)`.
- **No type annotations**, no `typing`, `dataclasses`, `pathlib` or `logging` (not available).
- `time.sleep_ms()` takes milliseconds; `time.sleep()` takes seconds. Use `sleep_ms()` in loops.
- Import only modules named in the device section or in the standard list below.
- Standard modules available: `machine`, `time`, `math`, `random`, `json`, `struct`, `sys`, `gc`.
  `network` and `espnow` exist but belong to the ESP-NOW manager — never use them directly.

## Size budget

Every game file is compiled on the device in one block of free memory. **Keep each file short —
under about 10 KB is typical, and a wand file over 32 KB is refused by the app** because the wand
runs out of memory loading it. Prefer a few simple features over many. Do not paste large tables,
long comment blocks or unused helpers.

## Talking between devices (ESP-NOW)

Every device game receives an `enow` object that is already set up. Never create another one or
touch `network.WLAN` — two radio stacks crash the device.

- `msg_type, data, mac = enow.poll()` returns at once, never blocks. Call it **every loop
  iteration**.
- `msg_type` `"stop"` or `"start_game"` means another game was chosen or the teacher stopped play:
  **return from `play()` immediately**. This is how games are switched.
- `msg_type` `"raw"` means another device broadcast something; `data` is usually a dict.
- To tell other devices something, broadcast a small dict:
  `enow.broadcast({"type": "goal", "team": "green"})`. The receiving game checks
  `msg_type == "raw" and isinstance(data, dict) and data.get("type") == "goal"`.
- Keep type names and keys short. One message holds about 240 bytes.
- Nothing relays messages for you: if one device must know what happened on another, the game on
  the second device has to broadcast it.

### Reserved message types — never use them for game messages

Every device sorts incoming messages before the game sees them. These `"type"` values are taken,
and arrive as their own `msg_type` instead of `"raw"`, so a game checking for `"raw"` never sees
them:

`stop`, `start_game`, `score`, `splat_config`, `battery`, `scan_request`, `find_device`,
`status_poll`, `status_report`.

A **list** (for example `["turnred"]`) arrives as `msg_type "colors"` (or `"stop"` / `"battery"` if
it contains those words). Game messages are therefore always **dicts with the game's own `"type"`**,
such as `{"type": "hit"}` or `{"type": "frogs", "from": "wand"}`. Using the game's slug as the type
keeps two games from reacting to each other's messages.

### Stop and start reach every device

`enow.broadcast_stop()` and `enow.broadcast_start_game(name)` go to **every** device in range: they
end or switch the games on all wands, the display and the Splat Companion. Use them only when the
game really should stop or switch everything.

## Games that use several devices

Write one complete file per device, each under its own `[DEVICE:]` marker. Plan the messages first
and use the same type names and keys in every file:

1. **Pick one message type** for the game (usually the slug) and a `"from"` key saying which kind
   of device sent it (`"wand"`, `"splat"`, `"icon"`).
2. **Decide who sends what.** For each thing that happens ("a child presses the Splat"), say which
   device notices it and broadcasts, and which devices react.
3. **Send what the receiver needs** in small plain values: a color *name* (`"red"`) or a short
   `[r, g, b]` list, a team name, a count.
4. **Every file still exits** on `"stop"` / `"start_game"`.

Worked example — the wand and the Splat echo each other (from the built-in Jump In game):

- Wand: when the button is pressed, `enow.broadcast({"type": "jumpin", "from": "wand"})`.
- Splat: on `msg_type == "raw"` with `data.get("type") == "jumpin"` and `data.get("from") == "wand"`,
  blink the Splat.
- Splat: on a press, `enow.broadcast({"type": "jumpin", "from": "splat", "rgb": [r, g, b]})`.
- Wand: on that message, `leds.fill(tuple(data["rgb"]))` — a color received in a message is used
  as it arrives.

Adding the icon display: each device that scores broadcasts `{"type": "<slug>", "from": "wand",
"team": "green"}`; the display keeps a count per team and shows it with `chart16.blocks`.

## Exiting and switching games

Every game must stop promptly when told to, so the teacher can switch games at any time:

- Return from `play()` on enow `"stop"` or `"start_game"`.
- On devices whose `play()` receives an NFC reader, also return when an exit card is tapped (see
  that device's section). Read cards only every 10–15 loop iterations: a card read takes 200–500 ms
  and would stall the game.
- Turn outputs off in a `finally:` block so a game that exits mid-effect leaves nothing lit or
  sounding.

## Game-specific cards

A game may react to its own cards (for example `"red"`, `"blue"`, `"go"`). Card values are short,
lowercase, plain words. List every one in the `[NFC_CARDS: ...]` marker.
