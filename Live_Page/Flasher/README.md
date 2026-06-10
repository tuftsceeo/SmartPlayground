# Smart Playground Flasher

Browser-based MicroPython uploader for Smart Playground hardware. Fetches files from a GitHub branch per **device manifest** and uploads over **Web Serial** using the same text-write + chunked-serial strategy as WebApp2's `firmware_manager.py`.

**Supported devices (v1):** Wand, Hub (USB bridge), M5Paper Remote.

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

**Wand bundle:** everything in `Bag2/Code/lib` + everything in `Bag2/Code/Wand Module` except `.md` and `.js` (includes `hubtype.txt`, `boot.py`, `main.py`, game modules).

## Adding a version

Edit `js/devices.js` → `VERSIONS`:

```js
{ label: "Stable — July 2026", ref: "July_2026", recommended: true },
```

## Adding a device

1. Create `manifests/my_device.yml` with `sources` and exclude rules.
2. Add an entry to `DEVICES` in `js/devices.js` with `manifest: "my_device.yml"` plus `devicePathRoot`, `baudRate`, etc.

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
