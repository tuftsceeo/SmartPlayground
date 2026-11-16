---
title: Dial JSON-link upload can replace a game file while a wand is pulling it
date: 2026-11-14
status: open (low priority; check in pre-classroom tests, not the stress test)
devices: [BroadcastDial]
components: [BDialFirmware/game_upload.py, BDialFirmware/code_sender.py]
code:
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/game_upload.py
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/code_sender.py
open:
  - Behaviour when file.end renames over a file an open pull session is reading
keywords: [upload, file.end, rename, pull, code_get, session, sha, game_upload, S5]
---

# Dial: upload over a game a wand is pulling, 2026-11-14

From code reading while writing S5 step 4 (`0b40a90f`); not seen on hardware.

`game_upload.Upload.end()` removes `/flash/games/<slug>.py` and renames the new file into place.
If a wand is mid-pull of that slug, its `code_sender` session may still read the old file (or
fail), and the sha it was offered describes the old file. `games.rescan` clears the sender's
cached digest, but does not touch open sessions.

The user judged this very unlikely in real use (a teacher re-sending a game while a wand is
pulling the same game) and not needed for the stress-test plan. Check it in pre-classroom tests:
start a pull of a large game, re-send the same game from ChatBroadcast, and see whether the wand
retries cleanly.

## 2026-11-16: re-send clears `<slug>_icons/` (commit ed11e36)
`game_upload.begin` on a top-level `/flash/games/<slug>.py` removes `<slug>_icons/` before the
new files arrive (the app always sends the main file first). Same exposure as above: a wand
mid-pull of an icon file can lose it. A failed upload leaves the game with no icons.
Host-tested only.
