# Bag3 stress test, unattended bench run (2026-11-17)

Branch `stress-unattended-2026-11-18`, run by an agent with no one at the bench. Nothing here was
seen by a person. "The log shows" means a serial log or tool output the agent read. Logs are in
the agent's scratchpad (`/private/tmp/claude-505/-Users-jcross04--claude-spares-spare-rfUrC1/659b0908-0f59-48e0-987f-412fd00aeeb5/scratchpad/logs/`), which may be cleared.
No repo files were changed apart from this report, which is uncommitted.

## The wand on USB (state read first)

| | |
|---|---|
| Port | 101 (you corrected this mid-run: the wand is on 101 and the icon display on 3101) |
| `/role.txt` | exists, contains `wand` (read at its REPL during Part 2) |
| Firmware before the flash | old: the log shows `# booting -- Ctrl-C within 30s to stay at the REPL` |
| Firmware after the flash | the log shows `# booting -- Ctrl-C within 2s to stay at the REPL` and `Boot complete — all systems OK (1395 ms)` |
| Part 4 decision | role is `wand`, so Part 4 would apply; it was skipped for a different reason (below) |

Ports: Dial 1101, wand 101, icon display 3101.

## Results

| Part | Result | Evidence |
|---|---|---|
| 0 Node tests | 3 of 11 fail, 1 not run | `check_tags`, `splat_game_check_test` (13), `prompt_eval --self-test-sim` (3) fail; `chat_ui_smoke` needs playwright |
| 0 Sync checks | pass | `sync_icons --check` OK (290 icons), `sync_splat_actions --check` OK (29), `build_wand_bundle --check` up to date |
| 0 Live_Page diff | listed below | 10 / 7 / 2 differing entries |
| 1 Dial files | match | all 20 top-level `BDialFirmware/` files identical to `/flash/` by sha256 |
| 1 Icon display files | not checked | port 3101 gives no USB output and no raw REPL; the display does answer over the radio |
| 1 Wand flash | pass | 54 of 54 manifest files copied, 0 size mismatches, 121 s; reboot shows "Ctrl-C within 2s" and "Boot complete" |
| 2.1 Awake Ctrl-C | pass | "Exiting." 0.024 s after one Ctrl-C, 300 bytes sent just before |
| 2.2 Asleep Ctrl-C | pass | "NFC sleeping" + 30 s, then 300 bytes; "Exiting." 0.022 s after one Ctrl-C |
| 2.3 Full buffer during boot | pass | 300 bytes at the countdown line; "Exiting." 0.024 s after one Ctrl-C 3 s after "Boot complete" |
| 2.4 `wand_breakin.py --exec` | pass, countdown path | "countdown seen (6.9 s)", "REPL after 6.9 s", `print(1)` -> `1` |
| 3 Reply speed | pass, 90/90 replied | asleep median 3.003 s, worst 3.111 s (87); awake median 4.360 s, worst 4.778 s (3); no attempt missed |
| 4 Wait for host | skipped | the Dial's JSON command table has no `start_game` |
| 5 Show/dance | half done | the wand sent all 4 broadcasts (each returned True); the display's USB log was empty, so nothing to report from it; no "Flash free" line |

## Part 0. Software

Node tests, run from `Bag3/Code/ChatBroadcast/`:

| Test | Result |
|---|---|
| chat_request_test | pass (20 checks) |
| check_tags | **1 fail**: `nfc_sound` extracts `note_c_high` as well as `note_c`..`note_b`; the test expects the 7 notes without it |
| distribute_test | pass |
| hardware_pills_test | pass |
| json_upload_test | pass |
| nfc_station_link_test | pass |
| pull_event_test | pass |
| splat_game_check_test | **13 fail** (list below) |
| prompt_eval `--self-test` | pass |
| prompt_eval `--self-test-sim` | **3 fail**: `host_relaycolor passes`, `a raise is an exception`, `ignoring end is unhandled`; each reports "the peers never got into the wand's lobby" / "the wand did not join the leader's lobby (1 of 2 wands)" |
| prompt_eval `--dry-run` | pass (builds every request, no API calls) |
| chat_ui_smoke | not run: `Cannot find module 'playwright'`; its header also marks it STALE (2026-11-12) |

`prompt_eval.mjs` was not run against the real model (no API calls were made).

`splat_game_check_test` failures: no declaration: net used with the parameter is refused;
PLAYERS_MIN outside a host game is refused; lobby game with net: no problems; lobby game:
SPLATS_MAX = None is allowed; lobby game without net is refused; lobby game: net.splat() is not
available; lobby game: must not call enow.poll(); lobby game: SPLATS_MIN = 0 is refused; lobby
game: SPLATS_MIN = '2' is refused; lobby game: SPLATS_MAX below SPLATS_MIN is refused; lobby game:
SPLATS_MAX not a number is refused; lobby game: SPLATS_MAX without SPLATS_MIN is refused; a comment
after a declared value is ignored. The output shows the checker now returns "SPLATS_MIN /
SPLATS_MAX need SPLAT_HOST = True ..." for lobby games the tests expect to pass, and different
wording from what the tests match. The checker and its tests disagree; which one is right was not
investigated.

Live_Page copies vs `Bag3/Code` (file list only; nothing promoted):

- `Live_Page/ChatBroadcast` vs `Bag3/Code/ChatBroadcast`: differ — `css/app.css`, `index.html`,
  `js/app.js`, `js/ledicons/defaultIcons.js`, `knowledge/devices/icon_display.md`,
  `knowledge/troubleshooting.md`; only in Bag3 — `REPLY_HANDLING.md`, `bak/`,
  `assets/wand/SmartPlayground.code-workspace`, `js/ledicons/iconCategories.js`.
- `Live_Page/Simulator` vs `Bag3/Code/Simulator`: differ — `tools/sync_sources.py`,
  `vendor/MANIFEST.json`, `vendor/display/games/goalrace.py`, `.pytest_cache/v/cache/nodeids`;
  only in Live_Page — `vendor/display/games/goalrace_icons/ready.py`; only in Bag3 —
  `vendor/display/games/goalrace_icons/ready_green_check.py`, `.pytest_cache/v/cache/lastfailed`.
- `Live_Page/IconEditor/webapp` vs `Bag3/Code/IconEditor/webapp`: differ — `css/app.css`,
  `index.html`.

## Part 1. Firmware check

**Dial (1101).** All 20 top-level files in `TeacherTools/BroadcastDial/BDialFirmware/` match
`/flash/` by sha256. `/flash/games/` was not compared. The device also holds UIFlow's own files
(`res/`, `libs/`, `apps/`) and its logs (`stats.log`, `bench_trace.txt`, `active.txt`,
`stats_since.txt`).

**Icon display (3101): not compared.** Opening the port gave no output for 45 s and then for 40 s
of listening. `mpremote ... resume run` failed twice with `could not enter raw repl`. The
JSON `{"cmd":"info"}` and `{"cmd":"repl"}` commands got no reply. The display is running: it
answered every Dial `fleet.scan` over ESP-NOW (`"kind": "icon_display"`). So its USB side is
silent or wedged while its radio works. It was not reflashed or power-cycled.

**Wand (101).** Flashed with `wand_breakin.py --manifest "Wand Module/flash_bundle/flash_manifest.json"`.
Break-in used the old 30 s countdown and reached the REPL in 5.5 s. The log shows `/boot_ok`
removed, `copied 54 files in 121 s, 0 size mismatches`, then a plain reset. On the next boot the
log shows "Ctrl-C within 2s" and "Boot complete — all systems OK (1395 ms)".

## Part 2. Wand Ctrl-C fix (commits 0530700a, cddfcd32)

One port session, one Ctrl-C per test (`part2.log`). "300 bytes" is plain English text, no
newline.

| Test | Sequence | Time from Ctrl-C to "Exiting." |
|---|---|---|
| 1 Awake | "Boot complete", 3 s, 300 bytes, 0.2 s, Ctrl-C | 0.024 s |
| 2 Asleep | Ctrl-D; "NFC sleeping" 41 s after the Ctrl-D; 30 s; 300 bytes; Ctrl-C | 0.022 s |
| 3 Full buffer during boot | port reopened (reset); 300 bytes at the countdown line; nothing until "Boot complete"; 3 s; Ctrl-C | 0.024 s |
| 4 `wand_breakin.py --exec "print(1)" --no-reset` | countdown path: "countdown seen (6.9 s)", "REPL after 6.9 s" | — |

This covers the open items in `known_issues/2026-11-17-wand-ctrlc-stdin-full.md` for awake, asleep,
and leftover bytes across a port-reopen reset, in the plain wand role. Not covered: the Splat host
role (this wand's role is `wand`) and running games.

The wand was then left running: Part 5's break-in left it at a REPL, and opening the port for Part 3
reset it (rst by port open, not `machine.reset()`); nothing was sent to it after that.

## Part 3. Wand reply speed while idle and asleep (45 min)

`fleet.scan` was used, not `fleet.find`: the Dial answers `fleet.find` with an immediate `ok` and
reports nothing from the wand (`fleet.py` only forwards `status_report` during a scan), so find has
no reply time to measure. The Dial (1101) sent `{"cmd":"fleet.scan"}` every 30 s, 90 times,
13:28:35 to 14:13:06. Port holders logged both the Dial and the wand on 101 with millisecond
timestamps; nothing was sent to the wand. Reply time = Dial send line to the first wand
`status_report` line from the Dial (window 6.5 s). "Asleep" = the wand's last state line before the
send was "NFC sleeping".

| | Attempts | Replies | Median | Worst |
|---|---|---|---|---|
| Asleep | 87 | 87 | 3.003 s | 3.111 s |
| Awake | 3 | 3 | 4.360 s | 4.778 s |

Over 3 s: 51 of 90, but 48 of those are between 3.001 and 3.111 s. A wand delays its status
reply by a fixed slot, `400 + (last MAC byte % 16) * 180` ms (`Wand Module/lib/espnow_manager.py`,
`_schedule_status_reply`); for this wand that is 2.56 s before any other delay, so about 3.0 s is its
normal reply time and the 3 s line is mostly slot, not sleep. The three replies above 3.2 s were all
awake:

- 13:28:35, 4.778 s: 10 s after "Boot complete".
- 13:29:35, 4.360 s: 8 s after "Movement detected — waking NFC" (13:29:27).
- 13:33:35, 3.918 s: 25 s after "Movement detected — waking NFC" (13:33:10).

The wand log shows "NFC sleeping" at 13:28:57, 13:29:58 and 13:33:41, and two "Movement detected"
wakes, although no one was at the bench (the agent cannot say what moved it). From 13:33:41 to the end
it stayed asleep.

Answer for this run: a sleeping wand was not slow to answer; it answered every scan in about 3.0 s.
The slower replies came while awake, after boot or a wake. With only 3 awake samples, that is a
pattern to check, not a result.

## Part 4. Wait for host — skipped

The Dial's JSON link cannot send `start_game`: the command table in `bdial_server.py` has no such
command (it has fleet.scan/find/distribute/cancel, games.*, file.*, etc.), and `grep start_game`
over `BDialFirmware/*.py` finds nothing. No firmware was changed. The wand's role is `wand`, so the
role was not the reason.

## Part 5. Icon display, show and dance messages

The wand was broken into (`--no-reset`), `ESPNowManager().init()` run at the REPL (log: "ESPNow:
active"), and four broadcasts sent 4–6 s apart; `broadcast()` returned True for each:

1. `{"type":"show","icon":"apple"}` (`apple.py` is in `Stations/IconDisplay/icons/`)
2. `{"type":"show","text":"12"}`
3. `{"type":"show","px":[[0,0,[255,0,0]]]}`
4. `{"type":"dance","s":["jump","spin"]}`

A monitor on the display's port (3101) during the sends logged nothing, but this is **not evidence**:
`lsof` later showed Thonny had opened 3101 at 13:26:04 (still holding it at 14:14), a minute before
the sends, so two processes shared the port. The agent did not stop Thonny. The "Flash free" line could not be read: the display could not be reset
over USB (see Part 1). Whether the panel showed anything only a person can say.

## Earlier today, from other agents (not re-run)

- Dial: JSON upload of 10 games with no reset; distribute to 3 wands at about 4 s each; slot
  replace passed; the distribute stall (D3) was not seen.
- Icon display: 924 KB free of 2048 KB; slot eviction passed.
- Wand Ctrl-C diagnosis: see `known_issues/2026-11-17-wand-ctrlc-stdin-full.md`.
- Two other wands reported no role, so they are on old firmware.

## Summary

**Passed:** sync checks and bundle check; 8 of 11 node checks; Dial firmware matches the repo; wand
flash; all four Part 2 Ctrl-C tests. Part 3: the wand answered all 90 scans; asleep it was not slower.

**Failed:** node tests `check_tags` (1), `splat_game_check_test` (13), `prompt_eval
--self-test-sim` (3). Icon display on 3101 silent over USB (no log, no REPL, no JSON replies)
while answering on the radio.

**Skipped:** Part 4 (Dial has no `start_game` command); display file comparison and display-side
Part 5 results and "Flash free" (display USB silent); `chat_ui_smoke` (playwright missing, test
marked stale).

**Notes on how the run went:**

- The brief named only the wand's port, and its MAC. Early on the agent assumed 101 was the display
  and 3101 the wand (by elimination), ran `wand_breakin.py` against 3101 (it saw no countdown, so
  sent no Ctrl-C and wrote nothing), ran `mpremote resume run` (a read-only hash script) and a plain
  `reset` on 101, which turned out to be the wand. You then corrected the ports.
- The wand on 101 has a different MAC from the one in the brief; per your correction, it was tested
  as "the wand on USB".
- An earlier agent's `sess.py` was holding the Dial port; it was stopped, as you allowed.

**What you need to do by hand:**

1. Thonny has had the display's port 3101 open since 13:26. Close it when you are done. Then unplug and replug the icon display on port 3101, then check whether its USB log comes back
   (boot should print "Flash free"). If it does, the Part 1 file comparison and the display half of
   Part 5 can be re-run.
2. Look at the icon display during a re-run of Part 5: only a person can say whether the apple, "12",
   the red pixel and the dance appeared.
3. Decide whether the `splat_game_check_test` / `check_tags` expectations or the checkers are stale.
