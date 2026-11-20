---
title: Stress test debrief, 2026-11-18 — 8 teacher controllers, 15+ wands and stations
date: 2026-11-18
status: notes and ideas (no code changed)
related:
  - Bag3/Code/known_issues/2026-11-18-stress-test-find-and-scan.md
  - Bag3/Code/known_issues/2026-10-23-distribute-code.md
  - Bag3/Code/known_issues/2026-11-14-splat-host-wand-count.md
  - Bag3/Code/known_issues/2026-11-14-hold-interactions-ux.md
  - Bag3/Code/known_issues/2026-11-17-splat-host-push-dropped.md
---

# Stress test debrief, 2026-11-18

**Setup (reported):** 8 teacher controllers in one room, more than 15 wands and stations.
Reported as "chaos". The card-tap code pull (NFC) worked when the device list did not.

For each issue below:
- **Reported** is what the team saw in the room.
- **From the code** is read from source, not seen on hardware.

ChatBroadcast paths point to `Live_Page/ChatBroadcast/`, promoted today in `640a9c2b`.
`Bag3/Code/ChatBroadcast/` has its own copy. Firmware paths point to `Bag3/Code/`.

---

## 1. Can't tell which wand is which

**Reported.** To choose which wand gets a game, the only tools were "Find Me" and "Status".

**From the code**
- **Card name.** A card is named `deviceLabel(mac, kind)`, a kind prefix plus a MAC tail.
  Nothing printed on the hardware matches that name.
- **Nicknames are per browser.** They are stored in `localStorage` by MAC
  (`js/distribute.js:64`). With 8 controllers, each teacher's names are invisible to the
  other 7.
- **Installed games are known but not shown.** The status reply already carries `role` and
  `g`, the installed game slots (`Wand Module/main.py:1076`, `lib/game_slots.py:104`). The
  app uses `g` to decide fit, but the card does not show it.
- **Running game is not reported.** No field says which game is running now.

**Ideas**
- **Physical label.** Put a sticker with the same short ID the app shows (e.g. `W-3F2A`) on
  every wand and station. This needs no code and would have helped today.
- **Running game in status.** Add the running game to `status_report`, and show the running
  and installed games on each card, as text or the game icon.
- **Shared names.**
  - Store the nickname on the device, so every controller sees the same name.
  - Or let a name tag set it: tap a "Blue Team 1" tag and the wand keeps that name.
- **Identify by tap.** Tap the wand on the controller, or tap a controller tag with the wand.
  Its card highlights or jumps to the top. See idea A below.

## 2. Find Me ends a running game

**Reported.** Someone looking for their wand pressed Find Me, and a child's game stopped.

**From the code (confirmed).**
- **Find Me launches a game.** `espnow_manager` rewrites `find_device` into the
  `start_game finddevice` force-switch (`Wand Module/lib/espnow_manager.py:451-460`).
  That replaces whatever is running.
- **Why it was built that way.** Wands without the update ignore it.
- **Known issue.** Recorded in `known_issues/2026-11-18-stress-test-find-and-scan.md`.

**Ideas**
- **Blink without stopping the game.** Handle `find_device` as a side effect inside `poll()`:
  flash the LEDs or beep a few times, then hand control back to the game.
  - A game that never polls would not blink. That is the same limit `code_push` has.
- **Confirm first.** If the target is mid-game, the app asks "This wand is running *X*. Find
  it anyway?" The app cannot do this today, because it does not know what is running (see 1).
- **Prefer tap-to-identify.** Use it over radio Find Me in a busy room. Find Me reaches every
  device on the channel. A tap reaches only the device in your hand.

**Constraints on any firmware fix**
- **Radio memory rule.** Nothing new may be imported or allocated ahead of the radio
  (`2026-09-23-ap-memory-order.md`).
- **Per-tree copies.** `espnow_manager.py` is copied per tree, so a fix lands in one copy
  only (Wand Module, IconDisplay, …).

## 3. Device list roulette (12, then 2, then 5)

**Reported.** Refreshing the device list gave 12, 2 or 5 devices. The card-tap pull worked
throughout.

**Bench test, same day.** Point 1 is now **measured**, and points 2 and 3 are mostly ruled out
as main causes. See "Bench results" at the end of this note.

**From the code.** These were the hypotheses before the bench test.

1. **Polls from other controllers push replies back (likely the main cause).**
   - Each `status_poll` resets the device's single pending reply
     (`lib/espnow_manager.py:267-273`, `_schedule_status_reply`).
   - The reply is due at 400 ms + (last MAC byte % 16) × 180 ms, so up to about 3.1 s.
   - If another controller polls before that, the timer restarts. A pending second copy is
     also cancelled.
   - With 8 controllers each sending 3 polls per scan, a device in a late slot can keep being
     pushed back, and it misses every 6 s window (`fleet.py:25`).
   - Devices in early slots get through, so the count jumps around with who else just scanned.
2. **Replies collide in the 16 slots.**
   - With 15+ devices in 16 slots, several pairs share a slot.
   - Each device sends twice, 120 ms apart. A pair that shares a slot hears the same poll and
     sends both copies at the same moments, so the second copy rarely helps.
3. **The controller drops replies.** This is already recorded in
   `known_issues/2026-10-23-distribute-code.md` (BroadcastDial section):
   - 1024 B rxbuf
   - one radio message per loop pass
   - replies after the 6 s window are dropped
   - wands in a game that does not poll, or mid-pull, answer late or not at all
4. **Replies are broadcast, and every controller lists them.**
   - `fleet.on_msg` accepts any `status_report` during its window (`fleet.py:104`), including
     replies to other controllers' polls.
   - So each controller's list is "whatever in the room it happened to hear", never "my
     devices". This is why filtering by group needs a group ID somewhere.
5. **Airtime.** Code pulls from 8 controllers share the same default channel. No channel is
   set anywhere in the Wand, Dial or `code_link` code.

**Why the card tap worked.** A card carries the controller's `HOST_ID`, and the wand sends
its `getcode` to that one host. No broadcast scan is involved, and nothing races 7 other
controllers.

**Ideas**
- **Tap-to-join roster.** See idea A.
- **Merge, don't replace.** The list keeps devices seen in the last N minutes (greyed when
  stale) and does not reset on every Rescan. A slow device then appears on the next scan.
- **Remember the poller.** The device keeps one reply per poller, or a pending poll does not
  reset an earlier one. This removes the push-back in 1.
- **Wider spread.** Use more slots, or add random jitter on top of the MAC slot, so that
  pairs sharing a slot separate between scans.
- **Show partial results.** "Heard 5 so far…" and "Some devices may be busy in a game"
  instead of a list that looks final.

## 4. A map of all devices and Splats

**Reported.** Users wanted a mental model of what is in the room: devices, Splats, what's
available.

**Ideas**
- **One "Room" view.** Group by type: wands, Splat host wands with their 4 Splats nested
  under them, IconDisplays, controllers. Each shows its sticker ID, name, battery, and
  installed and running games.
- **Mine vs. room.** With a roster (idea A), show "My devices" and "Others nearby" as two
  sections.
- **Splats in status.** A Splat host could report its Splats (count, connected or not) in
  `status_report`, so the map can draw them. Today the app learns of them only from game
  settings.

## 5. The Splat host is confusing

**Reported.**
- "One device = four devices but actually 5."
- How to use it is not clear, and the app does not explain it.

**Existing notes, not restated:**
- `known_issues/2026-11-14-splat-host-wand-count.md`: the device line leaves out the host
  wand.
- `2026-11-14-hold-interactions-ux.md`: holding to start or end is unclear.
- `2026-11-17-splat-host-push-dropped.md`.

**Ideas**
- **Device line.** Say it plainly: "1 Splat host wand + 4 Splats (5 devices), plus N
  players' wands."
- **Setup steps.** Add a short checklist card or overlay the first time a Splat host game is
  chosen: make this wand the host → turn on 4 Splats → wait for 4 lights → hold to start.
- **Show it in the room map.** Draw the host as one item with 4 children.
- **Language.** Settle on one term: "Splat host", "helper wand" or "teacher wand". The
  interview brief and the device line currently use different ones.

## 6. USB serial picker shows every port

**Reported.** The Web Serial picker lists every port. Users want only wands and
controllers, ideally named or filtered.

**From the code.** `navigator.serial.requestPort()` is called with no filters
(`js/device/serialAdapter.js:114`).

**Ideas and limits**
- **Filter by USB vendor and product ID.** This removes Bluetooth, debug and other non-board
  ports.
  - It likely **cannot** tell a wand, a Splat-host wand and an IconDisplay apart if they all
    use the same native USB on an ESP32-C6, since those report the same IDs.
  - **To check:** the VID/PID of each board (XIAO C6, M5Dial, Box, CrowPanel, M5Paper), read
    from `port.getInfo()`, not assumed.
- **The picker label is the browser's.** It shows the USB product string, which the native
  USB-serial peripheral fixes, so the page cannot rename it.
- **Identify after opening.** Once connected, the app reads identity and says "This is a
  wand, not a controller. Pick again?"
- **Remember granted ports.** Use `getPorts()` to show already-granted ports with the
  identity learned last time ("Dial D-91C4 (yours)"). Users then rarely see the raw picker.

## 7. Interview vs. form

**Reported.**
- Some loved the interview.
- Others wanted a menu or form: see every question at once, check several answers or write
  their own, send, and save the form to change and regenerate something similar.

**Related:**
- `knowledge/interview.md`
- `2026-11-11-simple-mode-*` design docs
- `2026-11-11-game-sharing-ideas.md`, for "save and remix"

**Ideas**
- **Both from one source.** The form and the interview come from the same question list. The
  interview asks one at a time; the form shows all of them.
  - Answers from either produce the same brief, so the model prompt does not fork.
- **A saved form is a recipe.** Store it with the game. "Make another like this" reopens the
  form filled in, for one change and resend.
- **Hybrid.** The interview fills the form as it goes, and the user can switch to the form
  view at any point.

---

## Cross-cutting idea A: tap-to-join roster (controller tag)

This idea came from the room: "an NFC tag on every controller". It may address 1, 2, 3 and
"channels" in one mechanism.

**Parts that already exist.**
- Cards carry the controller's `HOST_ID`.
- The wand reads it and sends a *unicast* `getcode` to that controller.

**Sketch.**
- Each controller has a "join" tag, or a card with a host and no game.
- Tapping a wand on it sends a unicast "hello" to that controller.
- The controller adds the wand to its **roster**, kept on the controller, so it survives an
  app reload.
- Find Me, Status and Send then go to roster members only, by unicast or a filtered scan.
- The list becomes "wands that joined me", which is fixed and independent of radio luck.
  Other devices can still show under "Others nearby".

**Effect on each issue.**

| Issue | Effect |
|---|---|
| 3, list roulette | Roster members are known even when a scan misses them. Status can be polled one device at a time. |
| Channels / groups | The roster *is* the group. No radio channel change is needed. |
| 1, which wand | The order in which wands were tapped is the identity. A tap could also set a name. |
| 2, Find Me | Fewer accidental Finds, because a teacher sees only their own devices. |

**Open.**
- Can a wand belong to two rosters?
- How does a wand leave one?
- Does a game-card tap also join the wand to that controller's roster?

## Cross-cutting idea B: channels

The room asked for channels to make grouping easier. There are two kinds.

- **Logical groups.**
  - A group ID in messages; devices ignore other groups.
  - Cheap, and keeps one radio channel.
  - Does not reduce airtime contention.
  - Idea A is one way to assign the group.
- **RF channels.** Separate ESP-NOW channels per group.
  - Removes the cross-controller traffic.
  - The serving controller must be on the same channel.
  - A wand on the wrong channel becomes **invisible**, which is worse than roulette.
  - Needs a reliable way to set and show a wand's channel: an NFC tap, and an LED colour per
    channel.
  - Splat BLE links are unaffected.

Today no channel is set anywhere, so every device shares the default.

---

## Bench results, 2026-11-18 afternoon (one Dial, 17 devices answering)

**Setup.**
- One Broadcast Dial (`host_id` 5094) on USB, driven with `fleet.scan` / `fleet.find` JSON
  commands from a host script.
- The other devices were 16 wands and 1 IconDisplay, left on around the room. You reported
  18 devices present, but only 17 ever answered.
- Two wands were also on USB with serial logs: `A0:F2:62:85:F0:6C` and
  `A0:F2:62:86:DF:E4`.
- Raw logs and scripts are in `2026-11-18-multi-controller-bench/`.
- Everything below is what the log shows.

**Results.**

| Test | Result |
|---|---|
| One quiet controller, 60 scans (10 s and 6.5 s apart) | 17/17 in 57 scans, 16 in 3. Under 1% of reply copies lost. **One Dial alone does not cause roulette.** |
| Poll every 3 s / 2.5 s / 2 s / 1.5 s / 1 s / 0.5 s, 15 s each, twice | Devices answering *while polling continued*: 17 / 16–17 / 14–16 / 9 / 3–4 / 2–3. All answered within seconds once polling stopped. |
| Random scan times, mean gap 2.1 s (88 scans) | Devices listed per 6 s window: min 9, median 16, max 17 |
| Random scan times, mean gap 1.3 s (136 scans) | Devices listed per 6 s window: **min 3, median 12, max 17**. This reproduces the room's 12 / 2 / 5. |
| Find Me to the two USB wands, 3 times each | Reached the wand 6/6. Each Find **started `finddevice` three times**: the Dial sends 3 copies, and each copy interrupts the previous one after 0.2 s. The real 5 s identify started about 2 s after the press. |

**What it shows.**
- **Push-back.** A device answers only if its reply wait (0.4 s + slot × 0.18 s) is shorter
  than the gap between polls. At a 1.5 s gap, the 2.56 s devices answered 0/5 and the 1.84 s
  devices 1/4, while the 0.4 s and 1.12 s devices all answered.
  - The cause is `_schedule_status_reply` resetting the pending reply on every poll
    (`Wand Module/lib/espnow_manager.py:267-273`).
  - Several controllers each scanning or pressing Rescan produce exactly these gaps.
- **Only 4 slots in use.** All 17 MACs seen end in a byte that is a multiple of 4
  (measured). The likely reason: Espressif assigns each chip a block of 4 MACs, so the base
  MAC is a multiple of 4 (not checked). So `last byte % 16` gives only slots 0, 4, 8 and 12, with 3–5
  devices in each.
  - The late slots (8 and 12) are the ones that disappear.
- **Feedback loop.** The app scans when Distribute opens after a Send (`distribute.js:364`)
  and on Rescan (`distribute.js:323`). A short list invites Rescan, which shortens the next
  list.
- **Signal strength (RSSI).** On the bench it read -27 to -64 dBm, varying 10–20 dB per
  device without anything moving. It is unlikely to work as a "near me" filter.
- **USB identity (for issue 6).**

  | Board | USB ID | Product string | Serial number |
  |---|---|---|---|
  | Dial | `303a:81dd` | "Dial(UiFlow2)" | — |
  | XIAO C6 wand | `303a:1001` | "USB JTAG/serial debug unit" | the MAC (as read by pyserial) |

  The port picker *can* separate Dials from wands by product ID. Not yet checked: what
  Chrome's picker shows, and the Box's IDs.

### T1: three real controllers, 2026-11-18 15:06–15:20

**Setup.**
- Dial A (`host_id` 5094), Dial B (004c) and the Box (cd64, an M5 StickS3, `303a:832b`
  "StickS3(UiFlow2)").
- All on USB to one host script, with 17 devices answering.

| Pattern | Devices per list (each controller) |
|---|---|
| Take turns, 10 s apart (18 scans) | 17/17 every scan |
| Random, each controller about every 20 s (16 scans) | 17 in all but one (16) |
| **Random, each controller about every 8 s (92 scans)** | **8–17, median 17.** Dial B ran 17, 8, 8, 17, … Devices in slot 12 listed 71–83% of the time, slot 8 89–96%, slots 0/4 100%. |
| All three scan within the same 0.5 s, 10 times | 17/17 every scan |

**What it shows.**
- **Spread-out polls do the damage, not simultaneous ones.** Replies are broadcast, so
  overlapping scans share replies, and scans all at once are harmless.
- **Each poll adds to the room's total.** Three controllers each about every 8 s add up to a
  poll every ~2.7 s, which already causes dropouts. By arithmetic, not measured: eight
  controllers at that rate reach a poll about every second. On the single Dial, that rate gave lists of 3–17.
- **It matches the room.** Teachers opening Distribute after a Send and pressing Rescan
  produce exactly this.

### T2: sends, scans and Find Me at once, 2026-11-18 15:20–15:28

**Setup.** Same three controllers.
- **Dial A** sent `follow_the_leade` to 4 wands that already held it, so nothing was
  evicted.
- **The Box** sent `unicorn_detector` to 2 wands that already held it.
- **Dial B** scanned.
- In the Find phases, every controller also sent Find Me to a random device about every 6 s.
  That is ~0.45 Finds/s room-wide, all 17 devices hit about 3 times each.

| Phase | Sends | Lists (devices per scan) |
|---|---|---|
| Dial A sends, nothing else | **1 of 4 OK; 3 `timeout`.** The log shows all three *opened* a pull session with Dial A; each stalled and was dropped after 15 s idle (`pull` event, `why: "idle"`). Those were the three running at once. The 4th, pushed alone 30 s later, pulled in 1.6 s. The same 4 wands then succeeded every time. Cause not known; no wand log. | — |
| Dial A sends while the others scan (each about every 8 s) | 4/4, finished in 11 s | 16–17 |
| Dial A and the Box send at once, Dial B scans | 6/6, 7–11 s | 16 |
| Finds + scans, no sends (2 min, 58 Finds) | — | **6–17, median ~12** |
| Everything: two sends + Finds + scans (3 min, 82 Finds) | **6/6, 11–17 s** | **10–17, median ~12** |

**What it shows.**
- **Directed transfers survive the chaos.** Every push or pull to a named device worked
  (12/12) while scans and Finds ran. This fits why card-tap pulls worked in the room.
  - The first quiet send failing on 3 of 4 (stalled sessions) is the one exception.
  - Worth a re-test with a wand on a USB log: if the first Send of a lesson stalls, a
    classroom will notice.
- **Lists were worse alongside Find traffic.** This is *not isolated*: the Find phases ran
  later than T1-busy, and right after 6 wands had launched pulled games.
  - At the same scan rate, with no Finds (T1 busy), the 0.4 s-wait devices were listed 100%
    of the time. In the Find phases they were listed 68–91%. The slowest slot fell to
    44–84%.
  - Devices found recently were missing about as often as the rest (27–31% vs 25–27%).
    Effects on the targeted wand alone, such as the 3× restart, therefore can't explain it.
  - Whether the device never sent or the controller dropped the reply is **not
    established**. No scan window was fully covered by another controller's, so there is no
    fair comparison.
  - A control run (scans only / Finds to a MAC nobody has / real Finds, back to back) is
    below.

### Find control, 2026-11-18 15:31–15:38

**Setup.**
- Three parts of 2 min each, back to back, in the same room state.
- All three controllers scanned at random, each about every 8 s.
- **The Box dropped off USB 51 s into part 3.** Its port came back, but it has been silent
  since: no heartbeat, no reply to `identify`. Counts below use the two Dials only.

| Part | Finds | Devices per list (Dials) | Listed rate, slots 0 / 4 / 8 / 12 |
|---|---|---|---|
| Scans only | 0 | median 17, mean 14.8 | 100 / 100 / 95 / 60% |
| + Finds to a MAC no device has | 55 | median 17, mean 16.4 | 100 / 100 / 99 / 88% |
| + real Finds to random devices | 58 | median 14, mean 14.3 | **86 / 83 / 90 / 80%** |

**What it shows.**
- **Find broadcasts are harmless; a Find *landing* on a device is not.**
  - Finds to nobody changed nothing; it was slightly better than scans alone, within noise.
  - Real Finds made devices drop out in *every* slot, including the ones that never drop
    from push-back.
- **The effect comes after the identify.**
  - A device found 8–20 s before a scan was missing 31% of the time; other devices 11%.
  - Found in the 8 s before the scan: 16% vs 15%.
  - So the 5 s identify itself is not the gap. Something after it, back in the idle loop,
    keeps the wand quiet. Cause not known.
- **For design.**
  - Changing Find so it doesn't launch a game (blink inside `poll()`, one identify per
    press) should help the lists as well as stop ending games.
  - De-duplicating or unicasting the broadcast alone would not.
- **In the room** there were 8 controllers, people pressing Find on whatever looked like
  theirs, and Rescan. That is this phase with more of everything.

**Not yet tested.**
- Pulls competing with scans.
- Wands mid-game.

The plan for these is `2026-11-18-multi-controller-test-plan.md`.

## Questions for the team

1. **Controllers.** Which teacher controllers were in use: Dials, Boxes, CrowPanels, M5Paper
   Remotes, or a mix?
2. **Refresh.** Was "refresh" the app's Rescan, the on-device scan, or a page reload?
3. **Overlap.** Were several people scanning at about the same moment? A yes supports
   hypothesis 3.1.
4. **Logs.** Did anyone capture serial logs or browser console output?
5. **Find Me.** Which device was the stopped game on: a wand, or a Splat host?
6. **Priority.** Which direction first? Candidates:
   - stickers and showing games on the cards (no firmware)
   - non-destructive Find Me
   - roster or tap-to-join
   - the list-reliability fixes
   - form mode
