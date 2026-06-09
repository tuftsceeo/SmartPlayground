# M5Paper Wand Remote

Self-contained teacher remote for Bag2 wands. An M5Paper (original, ESP32-D0WDQ6) running
UIFlow2 MicroPython broadcasts ESP-NOW commands directly to wands — no laptop or C6 hub dongle.

## Files

| File | Role |
|------|------|
| `main.py` | Boot entry: M5 init, ESP-NOW, touch poll loop |
| `ui.py` | E-ink UI, DejaVu fonts, Now Playing banner, Settings screen |
| `config.py` | Game catalog, layout constants, settings persistence |
| `espnow_manager.py` | Bundled copy of `../lib/espnow_manager.py` (keep in sync) |
| `game_tags.py` | Bundled copy of `../lib/game_tags.py` (keep in sync) |

## E-ink refresh (batched draws)

All multi-primitive frames use `M5.Lcd.startWrite()` / `endWrite()` so the panel
physically refreshes **once** per screen update (not once per `fillRect`). Settings
checkbox toggles redraw **only that row** (fast partial update). There is no periodic
mid-play full-screen wipe — full quality repaints happen only on boot, entering Settings,
and Save & Back.

If batched content does not appear after upload, set `LCD_SHOW_AFTER_END_WRITE = True` in
`config.py` (on-device REPL confirmed `endWrite()` alone is sufficient for this firmware).

## Main screen

- **No title or MAC line** on the home grid — maximum space for game buttons.
- **Gear icon** (top-right) opens Settings.
- **Now Playing banner** (borderless, bottom): shows `Ready`, then `Now Playing: <game>`,
  `Stopped`, or `Checking batteries`. Active game button stays inverted on the grid.
- **STOP** is the largest control (DejaVu40). **Battery** is a compact secondary button.

## Settings screen

Tap the **gear** to open a checklist of all 14 wand games. Tap rows to enable/disable;
at least one game must stay enabled. Tap **Save & Back** to return — choices are saved to
`/flash/settings.json` and survive reboot.

Device MAC appears only at the bottom of the Settings screen (`Device: XX:XX:…`) for
field troubleshooting.

### Default enabled games (10)

| Tag | Label |
|-----|-------|
| `jumpin` | Jump In |
| `gestures` | Gestures |
| `freezedance` | Freeze Dance |
| `cooking` | Cooking |
| `melody` | Melody |
| `simpleicecream` | Ice Cream |
| `rainbow` | Rainbow |
| `sound` | Bell Choir |
| `colorquest` | Color Quest |
| `shake` | Shake Fill |

Additional catalog entries (enable via Settings): `shakerainbow`, `jump`, `nfcsound`,
`multiicecream`.

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

## WiFi channel troubleshooting

Wand and hub firmware both use the default STA channel (no explicit channel set). The M5Paper
remote matches that behavior.

If wands do not respond:

1. Confirm at least one wand is powered on and idle.
2. Set `ESPNOW_CHANNEL` in `config.py` to an integer 1–11 and re-upload.
3. Use the same channel on all devices if you patch wand/hub firmware later.

Packets match the wand protocol in `../lib/espnow_manager.py` (same as the Live_Page C6 hub).

## Bench verification checklist

1. **Boot** — no title/MAC on main; gear top-right; larger game labels (DejaVu24).
2. **Now Playing** — borderless banner: Ready → Now Playing → Stopped.
3. **Settings** — gear opens 14-game checklist; Save & Back reflows grid; reboot persists.
4. **Stop / Battery** — wand behavior unchanged; STOP is boldest element.
5. **Range** — commands work at a few meters (double-send reliability).
6. **Refresh** — boot and Settings open in ~1–2s (one flash), not ~1 minute; game taps
   blink + settle in ~1s; Settings toggles update one row near-instantly.
7. **No mid-play wipe** — rapid game taps never trigger a full-screen white-out.
8. **REPL** — no Guru Meditation from `setFont` (only real DejaVu font objects used).

## Protocol (unchanged from hub)

| Action | Packet |
|--------|--------|
| Start game | `{"type":"start_game","name":"<tag>"}` |
| Stop | `["stop"]` |
| Battery | `["battery"]` |

Each command is sent **twice** with ~100 ms spacing.
