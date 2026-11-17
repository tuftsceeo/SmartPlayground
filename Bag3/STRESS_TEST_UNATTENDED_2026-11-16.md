# Bag3 stress test: unattended run, 2026-11-16/17

Run from `Chat_to_Tap_Doggle` at `a08dc240` by an agent, with nobody at the bench. Every result
here comes from serial logs ("the log shows"). Nobody looked at a screen or LED, and no cards,
buttons or Splats were used.

## Devices and ports

| Port | Device | How it was identified |
|---|---|---|
| `/dev/cu.usbserial-10` | CrowPanel | Its `identify` reply: `"device": "crowpanel"`, `host_id dfc8` |
| `/dev/cu.usbmodem3101` | Wand, MAC `A0:F2:62:85:CB:FC` | Its boot banner (`ESP-ROM:esp32c6`) and identity line `"device": "wand"` |
| `/dev/cu.usbmodem1101` | Broadcast Box, `host_id 51c0` | Silent at first. `os.uname()` gave `M5STACK StickS3`. `/flash` held EspnowModem bench code (`main.py` = `test_link.py`, `libs/eum_proto.py`), not Box firmware. The user confirmed it is the Box, with a PN532 fitted. |

The Box's previous files are backed up off-device (the agent's scratchpad, `box_backup/`): `main.py`,
`xfer_src.py`, `libs/*`, `games/{bigtest,edgetest,gesttest,jumptest}.py`.

Test games were staged on the Box (all six) and the CrowPanel (`stressa`, `stressb`) in
`/flash/games/`:
- `stressa` to `stresse`: 4 KB plain games whose `play()` returns at once, built with
  `tools/devtests/make_speed_games.py`.
- `stresshost`: a copy of `host_relaycolor`.

They are needed because the wand's built-in games never take a slot (`game_slots.BUILTIN`), so
distributing them cannot test slots.

## Results

| # | Test | Result |
|---|---|---|
| 1 | Flash and boot | Pass, all three |
| 2 | Box serves without arming | Pass |
| 3 | Box scan ×10 | Pass, 10 of 10 |
| 4 | Box distribute | Push and pull pass; the wand did not launch the game (it is a Splat host) |
| 5 | Slots | Pass |
| 6 | Wait for host | Not testable (the wand is a host, not a player); found a bug |
| 7 | CrowPanel scan and distribute | Pass |
| 8 | Soak, 60 min | No Box reset. Scans 59/60, distributes 58/60 |

### 1. Flash and boot

**Box.** Copied the 15 files in `manifest.js` plus the games in one `resume` call (28 s), then a
plain `reset`.
- The boot lines went out before USB re-enumerated, so the capture missed them.
- First heartbeat at 52 s uptime: `"mem": 8170688`.
- No reset-reason line was captured. `resetlog.txt` did not exist before the flash, and it was not
  read afterwards: reading it means `mpremote`, which stops the program.

**Wand.** Copied the 53 files in `flash_bundle/flash_manifest.json` (43 s), removed `boot_ok`, then
a plain reset. The log shows:
```
rst:0x15 (USB_UART_HPSYS)
MEM tag=after-imports gcf=162528 idf=155188 idfmax=143360
MEM tag=post-enow    gcf=150816 idf=155140 idfmax=143360
  Splat pairing: 4 Splat(s) [...]
MEM tag=post-ble     gcf=82304  idf=24072  idfmax=10240
  Boot complete — all systems OK (5827 ms)
MEM tag=boot-complete gcf=72016 idf=24072 idfmax=10240
  Splat host: up to 4 Splats; tap 'player' to leave this role
```
- `rst:0x15` appears every time the port is opened: **opening the wand's port resets it.**
- The wand's `/lib` still holds older `.mpy` files beside the new `.py` files. MicroPython looks for
  `.py` before `.mpy`, so the new code loads, but the stale files take up flash.

**CrowPanel.** Copied its 39 runtime `.py` files. Excluded: `m0_*`, `perf_probe`, `make_icons`,
`shot*` and the icons. Reset by an RTS pulse, not `mpremote reset` (see the CrowPanel known issue).
- The log shows `rst:0x1 (POWERON)`, then GT911 touch found (`Product id: 911`).
- First heartbeat `"mem": 6430384`.

### 2. Box serves without arming: pass

```
{"device": "broadcast_box", "nfc": false, "fleet": 1, "host_id": "51c0", "type": "identity"}
{"mem": 8169712, "radio": true, "payload_ready": true, "type": "info"}      <- no arm sent
{"ssid": null, "armed": true, "cmd": "arm", "type": "ok"}
{"cmd": "disarm", "type": "ok"}
{"mem": 8169616, "radio": true, "type": "info"}                            <- unchanged
```
- `nfc: false` is expected: the Box firmware drives a WS1850S at 0x28, and this Box has a PN532.
- The Box README still says `arm`/`disarm` return `unknown_cmd`. The code (and this log) accept
  them as no-ops; the README is out of date.
- The Box picked `edgetest`, a leftover bench game, as active, not one of the games new at this
  boot. Probably equal mtimes; not investigated.

### 3. Box scan ×10: pass, 10 of 10

Each scan gave one `status_report` from the wand, then `{"n": 1, "type": "status_done"}`, e.g.
```
{"role": "splat_host", "mac": "A0:F2:62:85:CB:FC", "g": [["memory", "h"]], "kind": "wand", "rssi": -34, "type": "status_report"}
```

### 4. Box distribute: transfer passes, launch refused by the wand's role

`fleet.distribute stressa`:
```
Box:  dist_progress why "pushed"
Box:  [ENX] DONE /flash/games/stressa.py -> A0:F2:62:85:CB:FC: 4099 B in 1887 ms
Box:  {"slug": "stressa", "ok": true, "type": "pull"}  ...  {"ok": 1, "type": "dist_done"}
Wand: # getcode (slug='stressa' host='51c0') via espnow
Wand: [ENX] OK stressa.py: 4099 B total 2239 ms
Wand:   Splat host: stressa is not a Splat host game
```
- The next scan's `g` was `[["memory","h"],["stressa","o"]]`, so the wand recorded the slot.
- It did not launch the game because this wand is in the Splat host role, which runs only host
  games. A player wand is needed to see the launch.

### 5. Slots: pass

| Step | `g` after (from scan) | Expected |
|---|---|---|
| + `stressb` | `memory h, stressa o, stressb o` | same |
| + `stressc`, no replace | `stressa, stressb, stressc` (oldest `memory` dropped) | same |
| + `stressd`, `replace: "stressb"` | `stressa, stressc, stressd` | same |

### 6. Wait for host: not testable; bug found

The wand is a Splat host, so the "player looks for a host lobby" path could not run.

- `stresshost` pulled and started (`MEMSPAN tag=import:stresshost`).
- 40 s later, `fleet.distribute stresse`. The wand logged `MEM tag=post-game:stresshost` one second
  after the push (the game ended), and then **no `# getcode`**.
- The Box reported `"ok": false, "why": "timeout"` after 30 s. The wand kept answering scans, with
  `stresshost` still in `g`.

New note: `Code/known_issues/2026-11-17-splat-host-push-dropped.md`. The cause, from the code: a
push during a game is queued in `main._pending_push`, which `splat_host._loop` never reads.

### 7. CrowPanel: pass

- `fleet.scan` ×5: the wand answered 5 of 5 (rssi -20).
- `fleet.distribute` `stressa`, then `stressb`: both `dist_done ok 1`. The wand logged
  `getcode ... host='dfc8'`, pulls of 1517 and 1735 ms.
- `g` after: `stresshost h, stressa o, stressb o`, as expected.
- The wand printed `not a Splat host game` twice per CrowPanel pull, against once per Box pull.
  Not investigated.

### 8. Soak: no Box reset

00:02 to 01:02, alternating a Box scan and a Box distribute (`stressc` to `stressb` in turn) every
30 s.

| | Attempts | OK | Failed |
|---|---|---|---|
| Scan | 60 | 59 | 1 (`00:33:07`, `status_done n 0`) |
| Distribute | 60 | 58 | 2 (`00:18:31` stressd, `00:27:31` stressc, both `why "no_ack"`; no `getcode` in the wand log, so the push never reached it) |

- **No Box reset.** The longest heartbeat gap was 7 s. The Box kept running after the soak until the
  capture closed at 03:12 (`"up": 11993870`, about 3.3 h).
- Box free memory (`info.mem`) every 5 minutes: 8167328, 8164768, 8166528, 8165120, 8165376,
  8165408, 8164992, 8166496, 8165216, 8166304, 8165312, 8166432. Flat.
- The wand takes no serial commands, so its memory comes from the `MEM tag=pre-import` line at each
  launch (58 in the hour). `gcf` ranged 82032–85536, with no trend (84880 at 00:02, 85184 at 00:54);
  `idf` stayed at 20784, largest block 10240.

## What failed

1. A Splat-host wand drops a `code_push` that arrives mid-game (new known issue).
2. 3 of 120 soak attempts missed the wand: 1 scan, and 2 distributes with `no_ack`. All at
   arm's length, on USB.
3. Docs: the Box README says arm and disarm are removed, but they are accepted no-ops.

## What was skipped, and why

- The launch in test 4 and all of test 6: the bench wand is in the Splat host role. A `player`
  card (or `/role.txt` removed) is needed.
- Box boot lines and reset reason: lost to USB re-enumeration; reading `resetlog.txt` needs
  `mpremote`, which stops the program.
- Range, battery, card pulls and writes, Splat pairing, anything judged by eye: not possible
  unattended.

## After the run (user requests, 2026-11-17)

- The user asked for a rule that a host wand goes back to player after two restarts without a
  Splat. It is written in `Wand Module/lib/splat_host.py` and is **not on the wand**:
  - The count is kept in `/host_nosplat`.
  - A Splat connecting, a Splat card tap, or any role change clears it.
  - Both copy attempts failed while the wand was in its 30 s boot countdown, so its
    `/lib/splat_host.py` may be partly written. Check or re-copy it before using that wand.
- The user unplugged the CrowPanel to charge the laptop.
- Requested follow-up, not done: the Box and the CrowPanel should detect which reader is fitted
  (WS1850S at 0x28, PN532 at 0x24). The readers move between them.

## What you need to do by hand

1. Before use, check the wand's `/lib/splat_host.py`: it should be 11992 bytes, or copy it again.
2. Make the bench wand a player: a `player` card, or the new rule. Then repeat test 4's launch and
   test 6.
3. Re-pair Splats to a host wand for block 1 (a player wand forgets its pairing on its next boot).
4. Decide on reader detection for the Box and the CrowPanel.
5. Range and battery tests for the Box (block 3).
