---
title: CrowPanel Teacher Tool firmware vs revised screen designs
date: 2026-11-10
status: open (firmware predates the 2026-11-10 design revisions)
devices: [CrowPanel5_Display (Elecrow CrowPanel HMI 5.0in V3, ESP32-S3)]
components: [LVGL screens, ESP-NOW fleet, NFC writer, USB host link]
code:
  - Bag3/Code/Experiments/CrowPanel5_Display/home.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_recipients.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_games.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_send.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_tags_home.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_cards.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_device.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_link_prompt.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_linked.py
  - Bag3/Code/Experiments/CrowPanel5_Display/scr_linked_card.py
  - Bag3/Code/Experiments/CrowPanel5_Display/panel.py
  - Bag3/Code/Experiments/CrowPanel5_Display/host.py
open:
  - Screens 1, 1B, 3, 3b, 4, 5 and 5.1-5.14 do not match the revised designs
  - Toasts still used (about 20 toast calls)
  - Screen 1B (group chat) and the full-screen chat view are not built
  - Screen 7.3 (could not link, version mismatch) missing; 7.1 and 7.2 are one screen
  - 4.4 refusal wording differs from the design
  - Design still open: 4.x sub-screens on the old list model; overflow on 5.13 not checked
keywords: [crowpanel, teacher tool, design, canvas, screens, toast, nfc, roll call, send code, scr_cards, home]
---

# CrowPanel Teacher Tool: firmware vs revised screen designs

Checked from the code on 2026-11-10; the README, IMPLEMENTATION_PLAN and REVIEW docs in the
firmware folder are older than the code. The designs are on the CrowPanel Teacher Tool canvas
(https://claude.ai/artifact/LiR5xAGC7LecrJh7BFb3iQ): Main Screens, NFC Sub-Screens, Send Code
Sub-Screens and Connected Mode Sub-Screens. Nothing here was run on hardware.

**What works:** the plumbing is real. ESP-NOW broadcast, unicast, roll call, find and code push
(`fleet.py`, `code_link.py`, `code_sender.py`), NFC read and write (WS1850S or PN532 via
`nfc.py` and `card_writer.py`), the USB link to ChatBroadcast (`host.py`, `json_link.py`) and the
beep tones (`beep.py`). No screen uses fake data. The gaps are almost all on-screen layout and
wording, from design changes the firmware hasn't caught up with.

## Design rules (all screens)

| Rule | Firmware |
|---|---|
| No extra text: no subtitles or helper lines; descriptions go in canvas notes | Not followed: e.g. "Nothing sent yet. Try Roll call." and "Roll call - listening..." (`home.py:194`, `:300`) |
| No toasts; big, clear states only | Not followed: about 20 `toast(` calls, e.g. "Busy - try again in a moment" (`panel.py:282`, `:394`) |
| Touch targets at least 44px, 52–56px for important buttons | Not audited |

## Screens

Status: **OK** = matches the design · **Gap** = built, but differs from the revised design · **Missing** = not built.

| Screen | Firmware | Status | What has to change |
|---|---|---|---|
| 1 · Home chat (Everyone) | `home.py` | Gap | Replace the "Playground" title with a Messages / Tags toggle. Remove the "ChatBroadcast linked" pill, "Radio on/paused" and the panel battery (`home.py:50`, `:63`, `:70`, `:315`). Remove the header's NFC Tags, Find and Roll call buttons (`home.py:79-81`); Roll call becomes a 44px icon in the left column with wand and station counts under it, and no low-battery count. Everyone is a blind broadcast: remove the roll-call summary bubble and the "didn't answer" / Try again row. Add an expand button as the rightmost heading item. Show a wand icon instead of the MAC address on device rows. Remove subtitles. |
| 1C · Roll call running | `feed.py`, `panel.roll_call`, `ui_kit.busy`/`dim` | Built, not on hardware | "Roll call" (white) in the feed, then an incoming bubble with the wand count and three dots that step every 400 ms. The Roll call button turns teal and its icon turns; Start a game and Send code are dimmed; Stop stays live. The column's Roll call opens Everyone and runs there. |
| 1D · Roll call answered | `feed.py`, `panel.emit` (status_done) | Built, not on hardware | The dots bubble becomes "N Wands / M Stations" with an expand icon, kept in the chat; the 1B header count and age update. Tapping it does nothing yet: the roll-call list isn't drawn (Designs required). |
| 1B · Group chat | `scr_group.py` | Partly built | Pencil (opens 2B) and Roll call in the header; expand left out. Opening a group runs a roll call. The header shows the last roll-call counts and age ("wands 4 · 1m") under the group name, with only buttons on the right. Same left column as 1. |
| Full-screen chat (from expand) | none | Missing | Opened by the expand button on 1 and 1B. |
| Find | `home.py:80` (header button) | Gap | Not a button. Tapping a device in a roll-call list sends Find to it; a group roll call sends Find to every device in the group. |
| 2 · New group | `scr_recipients.py`, `roster.section` | Built, not on hardware | Canvas v378. Header "New group" with "Tap the circle to add - tap the name to find" and a 44px Roll call icon. Wands, Stations and Unknown / Other sections with open/close headers (Unknown / Other starts closed; empty sections are left out). Each 60px tile has two tap zones and no long press: the 44px avatar circle adds or removes the device (pink circle with a check, pink ring), the rest of the tile sends Find (purple outline and "Blinking" for 5 s, the wand's Find length). Wand, station or "?" avatar at 45% when not heard. Under the name: 3 signal bars (red X when not heard) and battery icon with %, colored by level (critical under 10, low under 20, medium under 60: thresholds assumed). Footer: "N picked" and Save group (asks for a name; disabled with nothing picked). Chat with N and the "Who gets it?" mode are gone; `ui_kit.on_tile` is deleted. Sections: `wand` or no kind = Wands; `icon_display`, `splat_companion`, `programming_station`, `score_board`, `broadcast_box`, `broadcast_dial` = Stations; anything else = Unknown / Other. The Splat Companion sends no kind, so it lands in Wands (see [2026-10-23-distribute-code.md](2026-10-23-distribute-code.md)). |
| 2B · Edit group | `scr_recipients.py` (edit mode), `panel.edit_group` / `update_group` / `delete_group` | Built, not on hardware | Opened by the pencil in 1B or Edit in 1H: screen 2 titled with the group's name and its devices picked. Footer: "N picked", Delete group (red outline, trash icon) and Save. Save keeps the name and chat with the new devices and goes back to where 2B came from. Delete group deletes at once (no confirm) and goes to Everyone, or back to 1H; Undo is in 1G. |
| 1E · Group deleted | `panel.delete_group` | Built, not on hardware | Everyone's chat is unchanged after a delete (no line, no Undo there); the group's row leaves the column and its chat log is dropped. Chat logs are kept in memory only and are cleared on reboot, by intent. |
| 1F · Menu (hamburger) | `side.py` (hamburger), `menu.py`, `panel.shutdown` | Built, not on hardware | The hamburger replaces the column's Roll call. The menu sits on the top layer over a dark scrim, with a close button where the hamburger was: Roll call (Everyone's), Manage groups (1H), History / Undo (1G), and Shutdown set apart in red. Shutdown turns the radio and backlight off and deep-sleeps; the reset button wakes the panel. |
| 1G · History / Undo | `scr_history.py`, `panel.history` / `undo` | Built, not on hardware | The last 5 changes since boot, newest first: group deleted, group changed ("3 wands > 5 wands"), device renamed. Undo puts the group or the old name back; the row stays, greyed, marked Undone. Memory only: cleared by shutdown or reset. |
| 1H · Manage groups | `scr_groups.py` | Built, not on hardware | Saved groups with letter, name, wand and station counts, Edit (opens 2B) and a red Delete (at once, stays here). New group in the header opens screen 2. |
| 3 · Start a game | `scr_games.py` | Gap | Replace the On wands / New / All filter with Custom and Examples sections, each with a header that opens and closes it. Add a 52px scroll rail with up and down arrows. Tapping a game starts it. Remove "Not yet" (`scr_games.py:28`); add Cancel. Stop showing per-wand "On N of M" counts (they're kept only in memory and aren't reliable). |
| 3b · Send code | `scr_games.py` (code mode) | Gap | Becomes its own screen showing Custom games only. Tapping a game sends it; no Send button; Cancel instead of "Not yet"; no footer text. |
| 4 · Sending code | `scr_send.py`, `panel.py` | Built, not on hardware | List of "Receiving" / "Has it" wands, "7 have it · 2 receiving", no total. No Start button: each wand is sent `start_game` (unicast) as soon as it has the code (`panel.emit`, dist_progress ok). The footer has only Stop sending (Retry after a failure; Back to chat and "Send to the other N" after Stop). |
| 4.1 Sending | `scr_send._mode` | Gap | Same as 4. |
| 4.2 Paused | same | Gap | Uses "x of total"; the design isn't settled (4.x still on the old list). |
| 4.3 One wand didn't answer | same | Gap | The no-answer state conflicts with the new list model; the design isn't settled. |
| 4.4 Wands refused | same | Gap | Firmware shortens reasons to "Busy", "Too big", "Won't run" or "Didn't finish"; the design shows "Needs update" and "Battery low". |
| 4.5 All wands have it | `panel._send_check` | Built, not on hardware | No screen of its own: when nothing is waiting, receiving or failed, the panel goes back to the chat. Everyone has no total, so it also waits until no wand has answered for 10 s. The purple "Send code: X" bubble stays in the feed with a wand icon, how many have it, and its age. |
| 4.6 Stopped partway | same | Gap | Uses "x of total". |
| 5 · NFC Tags | `scr_tags_home.py`, `scr_cards.py` | Gap | Use the chat layout: the left column with Tags selected in the toggle, and tag lists where the chats are. Remove the separate Tags home and its Back button (`scr_tags_home.py:22`). Tag rows look like chat rows: no outline, pink for the selected row, a 40px status circle, 15px bold names, no section labels. Rename "Done" to "Exit" (`scr_cards.py:393-403`). |
| 5.1 Games · ready for tag | `scr_cards._words` | Gap | Remove the "All" row (`scr_cards.py:109`). Tap any row to write that tag; the order is only a suggestion. Skip moves to the next tag. |
| 5.2 Games · writing | same | Gap | Row styling and Exit, as in 5. |
| 5.3 Games · written, next tag | same | Gap | Tapping the same row again writes another copy (firmware: tapping a row is a one-off rewrite). |
| 5.4 Games · write failed | same | Gap | Row styling. |
| 5.5 Games · rewrite one tag | same | Gap | Becomes ordinary tap-a-row; drop "REWRITE ONE TAG" and "Back to the set". |
| 5.6 Games · whole set written | same | Gap | Row styling and Exit. |
| 5.7 Games · pick a game | `scr_cards._set_hint` | Gap | The hint still starts with "All", as if it were a tag (`scr_cards.py:330`, `:333`). It should read "Code, Play, then its 4 game tags". |
| 5.8 Write · type it | `kbd.py`, `scr_cards._type` | Built, not checked on screen | A sheet on the top layer below the 64px header, so Back and the Games / Write / Read toggle stay live (leaving the screen or changing tab closes it). Text field and "Use this text"; keys on a white pad in 4 rows: QWERTY, shift and backspace, then 123 / - / wide _ / : / .  Fonts are 16px (20px isn't built in). No Cancel, as on the artboard. The same sheet is used for Rename (6) and Save group (2). |
| 5.9 Write · tap a tag | same | OK, layout | Built; new layout. |
| 5.10 Write · writing | same | OK, layout | Built; new layout. |
| 5.11 Write · another? | same | OK, layout | Built ("Same again" / "New text"); new layout. |
| 5.12 Read · waiting | `scr_cards._words` | Gap | The left column lists recently read tags (firmware keeps only the last one). |
| 5.13 Read · tag result | same | Gap | Highlight the tag just read in the recent list. The design hasn't been checked for text overflow. |
| 5.14 Read · blank tag | same | Gap | Recent list, as in 5.12. |
| NFC tap target | `nfc_target.py` | OK | One shared component for screens 5 and 9. Its X/Y position against the design (528, 150) isn't checked. |
| 6 · One device | `scr_device.py` | Gap | Reached from Home only (screen 2 no longer opens it); add the roll-call-list tap. A device you've chatted with should stay as a row in the left column. Recheck against the no-text rule. |
| 7 · Plugged in | `scr_link_prompt.py`, `host.py` | Gap | One screen with an extra "Just charge" button that isn't in the design. |
| 7.1 Waiting for computer | same | Gap | Same screen as 7.2. |
| 7.2 Connecting | same | Gap | Same screen as 7.1. |
| 7.3 Could not link (version) | none | Missing | The panel reports `VERSION` "0.1.0" (`panel.py:21`) but nothing checks for a mismatch. |
| 8 · Connected | `scr_linked.py` | OK | |
| 8.1 Nothing running | same | OK | Shows "Waiting". |
| 8.2 Computer sending code | same | OK | |
| 8.3 Game playing | same | OK | |
| 8.4 Stop all pressed | same | OK | |
| 8.5 Disconnected | same | OK | Yellow header when the heartbeat times out. |
| 9 · Computer asks for a tag | `scr_linked_card.py`, `host.py` | OK | |
| 9.1 Ready | same | OK | |
| 9.2 Writing | same | OK | Text is "Keep holding…". |
| 9.3 Written · next | same | OK | |
| 9.4 Write failed | same | OK | |
| 9.5 Cancelled on computer | same | OK | Goes straight back to 8, as the canvas note asks; the 9.5 artboard can go. |
| 9.6 Set done | same | OK | |

## Designs required

States the code needs that no artboard draws. Each keeps today's behaviour until the canvas has
it; don't invent a layout for any of them.

| Need | Where in code | Now |
|---|---|---|
| 4.2 Paused, 4.3 one wand didn't answer, 4.6 stopped partway: still on the old list model | `scr_send._mode` | Old layout, without "of total" |
| 4.4 refusal reasons ("Needs update", "Battery low"): the firmware doesn't receive them | `scr_send`, `fleet` | Current reasons |
| Send code / Start when the radio is busy (other than a roll call, which dims the buttons) | `panel.py` | Toast stays |
| 1D roll-call list: tapping the reply bubble opens it, and tapping a device sends Find ("isn't drawn yet" in the canvas note) | `feed.py` | Expand icon drawn; tap does nothing |
| Send code to Everyone when no wand answers the scan | `panel._send_check` | Screen 4 stays at "0 have it" until Back |
| Send code with no Custom games on the panel | `scr_games` 3b | Empty sheet |
| "Blinking" on a station: IconDisplay has no `finddevice` (see 2026-10-23-distribute-code.md), so a station shows Blinking for 5 s but doesn't blink | `scr_recipients._find` | Same Blinking state as a wand |
| Group or single target with no devices | `panel.send_code` | Toast stays |
| Shutdown: no confirm and no "turning off" screen; a stray tap turns the panel off | `menu.py`, `panel.shutdown` | Turns off at once |
| 1G with more than 5 changes, and with none | `scr_history.py` | Oldest dropped past 5; "Nothing to undo yet." text |
| 1H with more than 5 groups, and with none | `scr_groups.py` | First 5 only; "No groups yet." text |
| Undo of a deleted group: the canvas doesn't say whether its chat comes back | `panel.undo` | The group comes back with its devices, chat empty |
| New group / Edit group with nothing picked | `scr_recipients.py` | Save group / Save disabled (no toast) |
| New group with more devices than fit: the artboard scrolls and draws no rail | `scr_recipients.py` | Paging rail, as on screen 3 |
| New group with no devices yet | `scr_recipients.py` | "No devices yet. Tap Roll call." text |
| Keyboard messages (too long, letters only) | `kbd.py` | Toast stays |
| 5.8 keyboard's 123 page (the artboard shows only the letters) | `kbd._rows` | Digits row, then `!?'/()&@#` and `+=*%,;"` |
| Rename (6) and Save group (2) typing: no artboard; they reuse the 5.8 sheet under their own header | `scr_device._rename`, `scr_recipients._save` | 5.8 sheet |
| 1B roll-call list (tap a row to Find and open screen 6): GroupChat draws no list | `scr_group.py` | Not built; Find on open, side-column rows open screen 6 |
| Full-screen chat: Main and GroupChat draw an expand button but no artboard draws the view | `scr_chat_full.py` | Not built; expand button left out |
| Send code during a roll call (e.g. right after opening a group) | `panel.send_code` | Everyone joins the running scan; a group or device pushes alongside it |
| 5.3 "x2" copy count; writing one tag out of order | `scr_cards.py` | Plain row status |
| Overflow on long tag lists and 5.13's large text | `scr_cards.py`, `kbd.py` | Paging rail; check on device |
| Swipe to page on the rail | `ui_kit.rail` | Arrows only |
| Missing icons: grid/list, chevron (wand, update and expand are now in `icons/`; expand drawn from the canvas SVG path) | `icons/` | LVGL symbols (`lv.SYMBOL.*`) or text glyphs stand in |
| Find / roll call / start messages that used to toast ("Finding Sunny", "Saved Red table", "No wand has it yet") | `panel.py` | Removed with no replacement; the feed bubble shows the send |
| "Something went wrong" after an action raises | `panel.step` | Toast stays (an `except` path) |
| NFC reader not ready when a tags screen opens (`reader.error`) | `panel.py` NFC enter | Toast stays until a reader-error state is drawn |

## Code serving

Send code is always a unicast push, the Broadcast Dial's `fleet.scan` / `fleet.distribute` path
(`fleet.py`): at most 3 in flight, a new push every 2.5 s, 30 s timeout each. To Everyone there
is no standing roll call: Send code starts a scan (or joins one already running) and each wand
that answers is queued as it answers (`panel._scan_push`). Which wands are on and in range
changes minute to minute, so two sends 5 minutes apart can reach different wands. No change to
the wand firmware. A class of 30 takes about 75 s at the stagger.

## Other open items

- Sounds: success and fail tones only, no separate "set done" sound; `beep.py` volume
  (`AMP = 6000`) is a placeholder.
- Display pixel noise: see `Experiments/CrowPanel5_Display/HANDOFF_pixel_noise.md`.
- Design side, still open: the 4.2, 4.3, 4.4 and 4.6 artboards (SendFlow) still show "x of 12" and
  "Start anyway"; the firmware drops Start anyway and keeps the rest; a "×2" copy count on
  5.3 and a write-one-tag-out-of-order screen were suggested but not drawn; overflow on long tag
  lists and 5.13's large text hasn't been checked.
