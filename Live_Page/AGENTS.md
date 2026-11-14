# Live_Page/AGENTS.md

Static web tools, served as-is by GitHub Pages. No build step, no bundler, no `package.json`; native
ES modules; Tailwind and Lucide load from unpinned CDNs.

**"hub" here means the USB hub** — the teacher-facing ESP32 that bridges USB serial to ESP-NOW.

## Deploy

`.github/workflows/static.yml` publishes to Pages only on push to `September_2026` (check `branches:` in the workflow; it moves). Changes on any other
branch are not live regardless of correctness — serve the directory locally to test them.

## Canonical vs. dead

`WebApp2/` (hub controller) and `Flasher/` (code uploader) are canonical. `ChatBroadcast/` is the
Bag3 Wand & Station Coder (chat → MicroPython → Box/Dial); it needs the sibling `Simulator/`
tree for the wand preview and example games. Both are verbatim copies of
`Bag3/Code/ChatBroadcast` and `Bag3/Code/Simulator`, which are
siblings there as here, so relative paths between them resolve the same in both places. Edit
the Bag3 trees for day-to-day work, then re-copy into Live_Page when promoting a build to Pages;
don't edit the copies. Paths from ChatBroadcast to other Bag3 folders (the firmware installer in
`js/device/boxFirmwareInstaller.js`, the `tools/sync_*` scripts) don't resolve here; nothing on
the page calls that installer, and Flasher flashes the Box and Dial.

`WebApp/` is the Bag1 legacy controller, `Code_Upload/` is Flasher's dead predecessor pinned to a
stale branch, `If_Splats/` is an unrelated Web Bluetooth demo, and `wand_icons.html` is a static
reference, not an app. Don't pattern-match off those four.

Flasher uploads chunked base64, so it can send binary files; WebApp2 uploads triple-quoted text and
is text-only. A new flashable device needs a `manifests/<device>.yml` plus a `js/devices.js` entry.

Sub-app specifics live alongside the app — see [WebApp2/AGENTS.md](WebApp2/AGENTS.md).
