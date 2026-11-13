# Smart Playground Flasher

Browser-based MicroPython uploader for Smart Playground hardware. Fetches files from a GitHub branch per **device manifest** and uploads over **Web Serial** using the same text-write + chunked-serial strategy as WebApp2's `firmware_manager.py`.

**Supported devices:** Wand (Bag2), Bag3 Wand, Hub (USB bridge), M5Paper Remote, Broadcast Box,
Broadcast Dial, Icon Display, CrowPanel (bench).

## Requirements

- **Chrome or Edge** (Web Serial API)
- Page served over **HTTPS** or **http://localhost** — ES modules will not load from `file://`
- Device already running **MicroPython** firmware (this tool uploads source files, not chip firmware binaries)

## Local development

```bash
cd Live_Page
python3 -m http.server 8000
```

Open [http://localhost:8000/Flasher/](http://localhost:8000/Flasher/) in Chrome.

## How it works

1. Pick a **version** (curated branch names) or type any branch/tag under Advanced.
2. Pick a **device** — file list comes from `manifests/<device>.yml`.
3. **Connect** via USB — reads `hubType.txt` when present; hub devices detect board type for antenna/display config.
4. **Upload** — fetches manifest files from GitHub, overwrites each file on-device (`open(path,'w')`), reboots.

## Device manifests (`manifests/*.yml`)

**This is the maintainer-facing file list.** Each device points to a manifest in `js/devices.js` via the `manifest` field.

Example — [manifests/wand.yml](manifests/wand.yml):

```yaml
exclude_ext:
  - .md
  - .js

sources:
  - repo: Bag2/Code/lib
    prefix: lib
  - repo: Bag2/Code/Wand Module
    prefix: ""
```

| Field | Meaning |
|-------|---------|
| `repo` | Branch-relative folder in the GitHub repo |
| `prefix` | Destination folder on device (`""` = root, `lib` → `/lib/`) |
| `exclude_ext` | Skip these extensions (manifest-wide or per-source) |
| `include_ext` | Whitelist only these extensions (e.g. hub `.py` only) |
| `exclude_dirs` | Skip these folders, relative to each source root (manifest-wide) |
| `exclude_files` | Skip these exact file names in any folder (manifest-wide) |

Manifest-wide lists (`exclude_ext`, `exclude_dirs`, `exclude_files`) go above `sources:`.

**Wand bundle:** everything in `Bag2/Code/lib` + everything in `Bag2/Code/Wand Module` except `.md` and `.js` (includes `hubtype.txt`, `boot.py`, `main.py`, game modules).

## Bag3 Wand (pre-built bundle)

The Bag3 wand's `main.py` must be precompiled to `wand_main.mpy` (compiling it on the
board fragments the memory the radio needs), so it can't use a `.yml` folder list.
Instead `devices.js` points `repoManifest` at a JSON file list committed in the repo:

- `Bag3/Code/Wand Module/flash_bundle/` — `wand_main.mpy`, stub `main.py`, `flash_manifest.json`
- Built by `python3 Bag3/Code/tools/build_wand_bundle.py` (needs `mpy-cross==1.28.0.post2`);
  `--check` reports a stale bundle. **Rebuild and commit after any Wand Module change.**
- Upload order is the JSON's order (boot.py, wand_main.mpy, then main.py); `/boot_ok` is
  removed first so the next boot is a debug boot.

To test uncommitted changes, serve the **repo root** and open
`http://localhost:8000/Live_Page/Flasher/?source=local` — files then come from disk, not GitHub.

## Broadcast Box and Dial (firmware `manifest.js`)

`devices.js` points `jsManifest` at the firmware's own `manifest.js`
(`Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/manifest.js`,
`.../BroadcastDial/BDialFirmware/manifest.js`), the list ChatBroadcast's installer also uses.
Flasher reads it as text at the selected ref and takes every
`{ path: '…', remotePath: '/flash/…' }` entry, in order (`main.py` last). Files not listed there
(`boot.py`, `tools/`, the Dial's bench `games/`) are not uploaded. Both boards are UIFlow2, root
`/flash/`; the USB port drops on the reboot after upload.

## Icon Display

`manifests/icon_display.yml` uploads `Bag3/Code/Stations/IconDisplay` except `drafts/` and `.md`.
`lib/hubtype.py` sets `led_pin` per unit (0 for the bench unit); a unit wired to D5 needs it changed
after flashing.

## CrowPanel (bench)

`manifests/crowpanel.yml` uploads the app files from `Bag3/Code/Experiments/CrowPanel5_Display`:
the `.a8` icons, not the PNGs, and no `firmware/` or bench tools. The board needs the
`CROWPANEL_S3_5` lvgl_micropython firmware first (`firmware/BUILD.md` there). After upload the
device entry's `reset: "rts"` pulses RTS for an EN reset instead of Ctrl-D: a soft reset re-runs
`main.py` over a live display, and only an EN reset frees the touch bus
(`Bag3/Code/known_issues/2026-10-28-crowpanel5-display.md`). Press RST if the screen or touch
does not come back.

## Adding a version

Edit `js/devices.js` → `VERSIONS`:

```js
{ label: "Stable — July 2026", ref: "July_2026", recommended: true },
```

## Adding a device

1. Create `manifests/my_device.yml` with `sources` and exclude rules.
2. Add an entry to `DEVICES` in `js/devices.js` with `manifest: "my_device.yml"` plus `devicePathRoot`, `baudRate`, etc.
   Use `jsManifest` (a firmware `manifest.js`) or `repoManifest` (a JSON list) instead of
   `manifest` when the firmware already keeps a file list. `reset: "rts"` replaces the Ctrl-D
   soft reset with an RTS pulse; `afterUploadNote` is appended to the success message.

## Hub board variants

On connect, hub devices run `os.uname()` to detect the chip:

- **C6** — antenna checkbox shown before upload
- **C3** — display I2C pins substituted automatically
- **S3 / S2 / other ESP32** — uploads with C6 defaults

## M5Paper notes

Filesystem root is `/flash/`. `settings.json` is preserved across re-flashes.

## Related tools

- [Code_Upload](../Code_Upload/index.html) — legacy Bag2 uploader
- [WebApp2](../WebApp2/index.html) — Wand teacher app with in-app hub setup modal
