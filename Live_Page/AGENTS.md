# Live_Page/AGENTS.md

Static web tools, served as-is by GitHub Pages. No build step, no bundler, no `package.json`; native
ES modules; Tailwind and Lucide load from unpinned CDNs.

**"hub" here means the USB hub** — the teacher-facing ESP32 that bridges USB serial to ESP-NOW.

## Deploy

`.github/workflows/static.yml` publishes to Pages only on push to `May_2026`. Changes on any other
branch are not live regardless of correctness — serve the directory locally to test them.

## Canonical vs. dead

`WebApp2/` (hub controller) and `Flasher/` (code uploader) are canonical. `WebApp/` is the Bag1
legacy controller, `Code_Upload/` is Flasher's dead predecessor pinned to a stale branch,
`If_Splats/` is an unrelated Web Bluetooth demo, and `wand_icons.html` is a static reference, not an
app. Don't pattern-match off those four.

Flasher uploads chunked base64, so it can send binary files; WebApp2 uploads triple-quoted text and
is text-only. A new flashable device needs a `manifests/<device>.yml` plus a `js/devices.js` entry.

Sub-app specifics live alongside the app — see [WebApp2/AGENTS.md](WebApp2/AGENTS.md).
