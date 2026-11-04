---
title: Live_Page ChatBroadcast and Simulator copies point at nonexistent Bag3 paths
date: 2026-10-29
status: open
devices: [ChatBroadcast (Live_Page copy), Simulator (Live_Page copy)]
components: [sync scripts, firmware installer, vendored sources]
code:
  - Live_Page/ChatBroadcast/tools/sync_icons.py
  - Live_Page/ChatBroadcast/tools/check_tags.mjs
  - Live_Page/ChatBroadcast/js/device/boxFirmwareInstaller.js
  - Live_Page/ChatBroadcast/js/ledicons/defaultIcons.js
  - Live_Page/ChatBroadcast/iconmaker/README.md
  - Live_Page/Simulator/tools/sync_sources.py
  - Live_Page/Simulator/README.md
  - Live_Page/Simulator/index.html
  - Live_Page/Simulator/vendor/MANIFEST.json
open:
  - Point these copies at the current Bag3 paths, or record that they are not meant to sync
keywords: [Live_Page, ChatBroadcast, Simulator, paths, sync_icons, sync_sources, check_tags, MockWand, BroadcastBox, IconDisplay, stale, copy]
---

# Live_Page ChatBroadcast and Simulator stale paths

`Live_Page/ChatBroadcast/` and `Live_Page/Simulator/` are copies of the Bag3 ChatBroadcast and
Simulator. Their scripts and docs refer to Bag3 folders that do not exist, such as
`Bag3/Code/BroadcastBox/MockWand` and `BroadcastCode/BroadcastBox/IconDisplay`. These paths
were already wrong before the 2026-10-29 reorganization of `Bag3/Code/BroadcastCode/` and were
left unchanged by it.

Current Bag3 locations:

| Was referenced as | Now at |
|---|---|
| MockWand | `Bag3/Code/Wand Module/` |
| IconDisplay | `Bag3/Code/Stations/IconDisplay/` |
| BroadcastBox, BroadcastDial | `Bag3/Code/TeacherTools/BroadcastBox/`, `Bag3/Code/TeacherTools/BroadcastDial/` |

Effects: the Live_Page `sync_icons.py`, `check_tags.mjs` and Simulator `sync_sources.py` cannot
find their sources, and the Live_Page firmware installer's Dial manifest import resolves to a
missing folder. The working copies are under `Bag3/Code/BroadcastCode/ChatBroadcast/` and
`Bag3/Code/Simulator/`.
