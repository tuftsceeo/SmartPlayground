# Known issues — Broadcast WiFi pull, 2026-09-30

Scope: `code_server.py` (Dial, Box), `code_puller.py` (MockWand, IconDisplay, SplatCompanion), `serve_guard.py`, and ChatBroadcast's send path.

Sources:

- **pull-speed:** `2026-09-30-pull-speed-results.md`
- **test-records:** `2026-09-23-test-records/`
- **handoff:** `2026-09-23-pull-failure-handoff.md`

## Open

### 1. Game size is limited by the wand's `compile()` check
- **Behavior.** `_compiles()` reads the whole file and compiles it, which needs a free block about the file's size (41216 B for a 40960 B file).
- **Measured.** 20480 B passed 5/5. 40960 B passed 1/5; the other runs failed with `MemoryError` after a complete transfer. Sizes between 20 and 40 KB are untested (pull-speed).
- **Launch.** A pulled game is compiled again when it is launched on a normal boot. That boot is not measured.
- **No limit at send time.** ChatBroadcast has no file size check.

### 2. A compile rejection is reported as a transfer failure
- **Behavior.** `pull()` returns `False` for a body failure, a hash mismatch and a compile rejection alike. `main.py` then prints `pull failed mid-transfer -- resetting to retry` and resets.
- **With retry off** (`MAX_ATTEMPTS = 1`), the next boot prints `attempt budget spent` and boots normally. The extra reboot adds ~7 s.

### 3. Most of the pull time is spent before the transfer
- **Measured.** ~7 s from pull-mode entry to join on every pull, independent of size: `code_puller` import ~1.1 s, radio reset and scan ~2.5 s, connect ~1.7 s.
- **For comparison.** The body transfers at 10.8 KB/s (pull-speed).

### 4. The Dial's largest free IDF block drops during serving
- **Measured.** `idf_largest` went from 20480 at arm to 16384 after the first pull, stayed there idle, and fell to 11264 during transfers. Total `idf_free` returned to within ~1 KB of its armed value (pull-speed).
- **Guard coverage.** `serve_guard` monitors total `idf_free` only, and only while idle.

### 5. Dial stopped running with four wands pulling at once
- **Observed** by the user, once. No log was captured, and the cause is not established.
- **Configuration.** `MAX_CLIENTS = 4`: up to four transfers run at once, and `serve_guard` does not sample while clients are connected.

### 6. Arm-time `WiFi Out of Memory` on a fresh Dial boot
- **Seen** once, during the forced-guard test. It may coincide with a ChatBroadcast write session on the same Dial; that is not confirmed (test-records, `forced_guard_dial2_verify`).

### 7. Ungated diagnostic print in the Dial's `code_server.py`
- **Behavior.** `poll()` prints `# DEBUG client state=...` every 2 s while clients exist, regardless of `DEBUG_SERVE`.
- **Memory order.** Its format string is allocated at import, ahead of `prewarm_ap()`.
- **PEER.** The Box copy does not have it.

### 8. Wand heap probes run before the radio claims memory
- **Behavior.** `lib/memprobe.py` has `ENABLED = True`. `pull()` calls `memprobe.probe()` and `memprobe.frag()` (a full `micropython.mem_info(1)` dump) before `sta.active(True)`.
- **Import.** `code_puller.py` prints its revision at import.

### 9. The Dial detects a client's close only when its deadline expires
- **Behavior.** Clients in `hdr`/`body`/`icount` are on `select()`'s write list only, and the exception list is empty. A closed peer stays until `SOCK_REPLY_TIMEOUT_S` (8 s) after its last progress.

### 10. `serve_guard` floor measured on the Dial only
- **Floor.** `MIN_IDF_FREE = 22000` comes from Dial readings (failing 12–17 KB, passing ~28 KB).
- **Box.** The Box's idle level is unmeasured, and the Box guard (`b8bbc90`) is untested on hardware.

### 11. Untested on hardware
- **Icon Display** pull path after `328e1ce`, and its per-icon 8 s ack wait.
- **Splat Companion** antenna state (external is assumed).
- **Box** with `SOCK_REPLY_TIMEOUT_S = 8`.

### 12. `stats.log` counts are windowed
- **Timestamps.** Lines are stamped with per-boot `ticks_ms()`.
- **Window.** The file keeps the newest 200 lines, shared with tag writes. `aggregate()` counts only `ok` lines inside that window.

## Resolved in this period

| Issue | Change |
|---|---|
| Retry landed while the host still held the stalled client | `5781335`: host reply timeout 8 s, wand recv timeout 12 s, automatic retry off |
| Low Dial IDF heap coincided with join failures and mid-body stalls | `fc2637d`: `serve_guard` reboots into SERVE below the floor. Its reboot sequence was confirmed in the forced-guard test; it has not been seen triggering naturally |
| Icon Display `pull()` had no `host_id` parameter; every pull raised `TypeError` | `328e1ce` |
