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
| `assets/*.png` | 1-bit icons (gear, battery shell, charging bolt, signal bars) |
| `assets/_generate_icons.py` | Dev-only Pillow script to regenerate the PNGs |

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
- **Battery icon** (top-left): shell PNG + code-drawn fill bar from `M5.Power.getBatteryLevel()`;
  charging bolt overlay when USB is connected. Updates every ~30s without a full-screen refresh.
- **Gear icon** (top-right, PNG) opens Settings. Primitive fallbacks draw if PNGs are missing.
- **Now Playing banner** (borderless, bottom): shows `Ready`, then `Now Playing: <game>`,
  `Stopped`, or `Checking batteries`. Active game button stays inverted on the grid.
- **STOP** is the largest control (DejaVu40). **Battery** is a compact secondary button.

## Image assets

Icons live in `assets/` as 1-bit black-on-white PNGs (no alpha — gray edges dither badly on
e-ink):

| File | Size | Purpose |
|------|------|---------|
| `gear.png` | 36×36 | Settings gear |
| `battery.png` | 46×22 | Battery shell (fill bar drawn in code) |
| `bolt.png` | 12×16 | Charging overlay |
| `signal-0.png`..`signal-3.png` | 40×34 | Device-status signal bars (Poor→Strong) |

Regenerate after editing artwork: `cd assets && python3 _generate_icons.py` (requires Pillow).

On device, paths are `/flash/assets/gear.png`, etc. (`config.py` constants). Upload via the
[Live_Page Flasher](../../Live_Page/Flasher/) (M5Paper manifest includes `.png` files) or copy
manually to `/flash/assets/` on the device filesystem.

### REPL: verify `drawPng` (impl step 0)

After Flasher upload, on the M5Paper REPL:

```python
import M5
from M5 import *
M5.begin()
M5.Lcd.startWrite()
M5.Lcd.drawPng("/flash/assets/gear.png", 12, 8)
M5.Lcd.endWrite()
```

If that raises, try `Widgets.Image("/flash/assets/gear.png", 12, 8)` or `drawBmp`. The UI
`_draw_png` helper tries all three and falls back to primitive drawing on failure.

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

## Device Status screen

Tap **Status** to broadcast a status poll; responding wands appear as rows showing the
wand name, a **battery icon + percent**, and a **signal-bars icon + word** (Poor / Fair /
Good / Strong). If more wands respond than fit on one screen, **Up / Dn** pagination
buttons and a `page/total` indicator appear in the top bar; the physical **side rocker
up/down** pages the list too. Tap **Back** (or the rocker) to return.

## Sleep / wake

After **2 minutes** with no touch or side-button activity (`INACTIVITY_SLEEP_MS`), the
remote shows a full-screen **"Device Sleeping"** notice and powers down the ESP-NOW radio
(the dominant battery draw). E-ink holds the sleep image at zero power.

Wake by **pressing the side rocker (up or down) or tapping the screen** — the radio
re-initialises and the main screen repaints. (The original M5Paper has no accelerometer,
so there is no shake-to-wake.)

Battery is polled every **5 minutes** (`BATT_POLL_MS`) in both states. While asleep, if
the charge falls to/below `BATT_CRIT_SOC` (10%), the sleep screen switches once to a large
empty-battery **"Battery Low"** warning so it can be charged before dying.

`USE_LIGHTSLEEP` (config, default `False`) opts into `machine.lightsleep` between sleep
ticks for further savings; leave off until verified against the touch panel on your build.

## Flash firmware (first time)

1. Install [M5Burner](https://docs.m5stack.com/en/quick_start/m5burner).
2. Connect the M5Paper via USB.
3. Select **M5Paper** → flash the latest **UIFlow2 MicroPython** firmware.
4. Reboot the device after flashing.

## Upload project files

### Option A — Live_Page Flasher (recommended)

1. Serve [Live_Page/Flasher](../../Live_Page/Flasher/) locally or open from GitHub Pages.
2. Select version → **M5Paper Remote** → connect USB → upload.
3. Upload includes `.py` files and `assets/*.png` → `/flash/assets/` on device.
4. `settings.json` on `/flash/` is preserved across re-uploads.

### Option B — UIFlow2 web IDE (USB)

1. Open [UIFlow2](https://uiflow2.m5stack.com/) and connect the M5Paper over USB.
2. Switch to **MicroPython** / code view.
3. Upload all `.py` files plus `assets/*.png` to `/flash/` (PNGs under `/flash/assets/`).
4. Set `main.py` as the run entry (or rename/boot from `main.py` per your UIFlow workflow).
5. Run / reboot the device.

### Option C — UIFlow2 Desktop

1. Open UIFlow2 Desktop, connect the M5Paper.
2. Use the file manager to copy each `.py` file and the three PNGs to the device.
3. Execute `main.py`.

## Usage

- Tap a **game** button to broadcast `{"type":"start_game","name":"<tag>"}` twice (100 ms apart).
- Tap **STOP** to broadcast `["stop"]` twice.
- Tap **Status** to broadcast `status_poll` three times and open a transient device-status overlay.

## WiFi channel troubleshooting

Wand and hub firmware both use the default STA channel (no explicit channel set). The M5Paper
remote matches that behavior.

If wands do not respond:

1. Confirm at least one wand is powered on and idle.
2. Set `ESPNOW_CHANNEL` in `config.py` to an integer 1–11 and re-upload.
3. Use the same channel on all devices if you patch wand/hub firmware later.

Packets match the wand protocol in `../lib/espnow_manager.py` (same as the Live_Page C6 hub).

## Bench verification checklist

1. **Boot** — no title/MAC on main; battery icon top-left; gear PNG top-right; larger game
   labels (DejaVu24).
2. **drawPng** — REPL snippet above renders `gear.png`; files exist under `/flash/assets/`.
3. **Battery icon** — fill bar tracks `M5.Power.getBatteryLevel()`; bolt appears on USB charge.
4. **Asset fallback** — delete one PNG on device → primitive draws in that corner (no crash).
5. **Battery poll** — level/charge change redraws only the battery region (~30s poll); gear
   not wiped; no full-screen white-out during idle.
6. **Now Playing** — borderless banner: Ready → Now Playing → Stopped.
7. **Settings** — gear opens 14-game checklist; Save & Back reflows grid; both icons return on
   main; reboot persists.
8. **Stop / Battery button** — wand behavior unchanged; STOP is boldest element.
9. **Range** — commands work at a few meters (double-send reliability).
10. **Refresh** — boot and Settings open in ~1–2s (one flash), not ~1 minute; game taps
    blink + settle in ~1s; Settings toggles update one row near-instantly.
11. **No mid-play wipe** — rapid game taps never trigger a full-screen white-out.
12. **REPL** — no Guru Meditation from `setFont` (only real DejaVu font objects used).

## Protocol (unchanged from hub)

| Action | Packet |
|--------|--------|
| Start game | `{"type":"start_game","name":"<tag>"}` |
| Stop | `["stop"]` |
| Status | `{"type":"status_poll"}` (×3) |

Each command is sent **twice** with ~100 ms spacing.
