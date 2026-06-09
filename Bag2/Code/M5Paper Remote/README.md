# M5Paper Wand Remote

Self-contained teacher remote for Bag2 wands. An M5Paper (original, ESP32-D0WDQ6) running
UIFlow2 MicroPython broadcasts ESP-NOW commands directly to wands — no laptop or C6 hub dongle.

## Files

| File | Role |
|------|------|
| `main.py` | Boot entry: M5 init, ESP-NOW, touch poll loop |
| `ui.py` | E-ink button grid, touch hit-testing, partial refresh feedback |
| `config.py` | Curated game list, layout constants, optional WiFi channel |
| `espnow_manager.py` | Bundled copy of `../lib/espnow_manager.py` (keep in sync) |
| `game_tags.py` | Bundled copy of `../lib/game_tags.py` (keep in sync) |

## Flash firmware (first time)

1. Install [M5Burner](https://docs.m5stack.com/en/quick_start/m5burner).
2. Connect the M5Paper via USB.
3. Select **M5Paper** → flash the latest **UIFlow2 MicroPython** firmware.
4. Reboot the device after flashing.

## Upload project files

### Option A — UIFlow2 web IDE (USB)

1. Open [UIFlow2](https://uiflow2.m5stack.com/) and connect the M5Paper over USB.
2. Switch to **MicroPython** / code view.
3. Upload all files in this folder to the device filesystem (root or project folder).
4. Set `main.py` as the run entry (or rename/boot from `main.py` per your UIFlow workflow).
5. Run / reboot the device.

### Option B — UIFlow2 Desktop

1. Open UIFlow2 Desktop, connect the M5Paper.
2. Use the file manager to copy each `.py` file to the device.
3. Execute `main.py`.

## Usage

- Tap a **game** button to broadcast `{"type":"start_game","name":"<tag>"}` twice (100 ms apart).
- Tap **STOP** to broadcast `["stop"]` twice.
- Tap **Battery** to broadcast `["battery"]` twice.
- Status line shows `NOW Ready` and the device MAC.

## Customizing games

Edit `COMMANDS` in `config.py`. Each `id` must exist in `game_tags.GAME_TAGS`. One line per game.

## WiFi channel troubleshooting

Wand and hub firmware both use the default STA channel (no explicit channel set). The M5Paper
remote matches that behavior.

If wands do not respond:

1. Confirm at least one wand is powered on and idle.
2. Set `ESPNOW_CHANNEL` in `config.py` to an integer 1–11 and re-upload.
3. Use the same channel on all devices if you patch wand/hub firmware later.

Packets match the wand protocol in `../lib/espnow_manager.py` (same as the Live_Page C6 hub).

## Bench verification checklist

1. **Boot** — UI paints; status shows `NOW Ready` + MAC.
2. **Start game** — tap each curated game; wand enters that game.
3. **Stop** — wand returns to idle.
4. **Battery** — wand reports battery (per wand firmware behavior).
5. **Range** — commands work at a few meters (double-send reliability).
6. **Refresh** — rapid taps stay legible; every 12 taps triggers a full e-ink refresh.

## Protocol (unchanged from hub)

| Action | Packet |
|--------|--------|
| Start game | `{"type":"start_game","name":"<tag>"}` |
| Stop | `["stop"]` |
| Battery | `["battery"]` |

Each command is sent **twice** with ~100 ms spacing.
