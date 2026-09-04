# Wand Coder + Broadcast Box — Flow Logic

If/when/then rules for the numbered screens in `Wand Coder + Broadcast Box Prototype.dc.html`.

## App (screens 1–9, 21)

| If the user... | When on screen # | Then show... |
|---|---|---|
| Opens the app for the first time | 1 (Splash) | Splash, with "Start from scratch" and "Browse examples" |
| Taps "Browse examples" | 1 | 2 (Example gallery) |
| Taps "Start from scratch" | 1 | 4 (Workspace), empty chat thread |
| Searches or taps a category chip | 2 | 2, filtered list |
| Taps an example card (e.g. Melody) | 2 | 3 (Example detail) |
| Taps "Remix this in chat" | 3 | 4 (Workspace), thread pre-loaded with that game + starter message |
| Taps "Use as-is → send" | 3 | 6 (NFC tags needed), skipping chat entirely |
| Types a request and taps Send | 4 | 4, new chat bubble + updated preview animation; code (hidden) updates too |
| Taps "◄ / ►" version arrows | 4 | 4, preview + chat scroll to that version; code drawer (if open) updates |
| Taps "</> Show code" | 4 | 5 (Code drawer), slid over the preview panel |
| Taps ✕ on the code drawer | 5 | 4 |
| Switches thread (Wands ↔ Stations) | 4 | 4, chat history + preview swap to that role's thread |
| Taps "Send to Broadcast Box" | 4 | 7 if not yet connected, else 8 |
| Only 1 tag is needed (e.g. simple station code) | 4 → send | 8 directly, skip 6 |
| Game needs multiple tags (e.g. Melody, 8 notes) | 4 → send | 6 (NFC tags needed list) |
| Taps "Continue on Broadcast Box →" | 6 | 7 if not yet connected, else 8 |
| Taps "Connect via USB" | 7 | Browser port picker → 8 on success; on failure, error toast on 7 ("Couldn't find a Broadcast Box — check the cable") |
| Taps "Send" (confirm modal) | 8 | 9 (Sent banner), code + tag list transmitted to Box |
| Taps "Not yet" | 8 | 4 |
| Wants to check who has picked up the new game | any, via a menu/nav item | 21 (Pickup tracker) — nice-to-have, not blocking |

## Broadcast Box (screens 10–20) — one button, short press (⏺) / long press (⏺⏺)

| If the user... | When on screen # | Then show... |
|---|---|---|
| Plugs the Box into the laptop | 10 (Idle) | 10, status dot → "linked to laptop" |
| App sends code | 10 | 11 (Receiving) |
| Transfer finishes and only one role was sent | 11 | 13 (Armed for tag 1) directly, skip 12 |
| Transfer finishes and both roles were sent | 11 | 12 (Pick role) |
| Presses ⏺ on 12 | 12 | 12, selection toggles Wands ↔ Stations |
| Presses ⏺⏺ on 12 | 12 | 13, tag 1 of that role's set |
| Presses ⏺ on 13 (skip tag) | 13 | 13, advances to next tag in the set without writing |
| Holds a blank/unused card near the reader | 13 | 15 (Writing) directly |
| Holds a card that already has data near the reader | 13 | 14 (Overwrite check) |
| Presses ⏺ on 14 (cancel) | 14 | 13, same tag still armed |
| Presses ⏺⏺ on 14 (overwrite) | 14 | 15 |
| Write completes successfully | 15 | 16 (Done, auto-advance) |
| Write fails (card pulled away, bad tag) | 15 | 13 again, same tag, with an error line ("try again — hold steady") |
| 2 seconds pass after 16, more tags remain | 16 | 13, next tag armed (e.g. tag 4/8) |
| 2 seconds pass after 16, that was the last tag | 16 | 17 (Role set complete) |
| Presses ⏺ on 17 (do other role next) | 17 | 12 (Pick role), other role pre-selected |
| Presses ⏺⏺ on 17 (menu) | 17 | 10, ready for the next teacher action |
| Walks the Box up to a station's onboard tag (any screen, once linked) | 10/17 | 18 (Station found → uploading) |
| Station upload completes | 18 | 19 (Station done) |
| Taps the next station | 19 | 18 again, for that station |
| Presses ⏺⏺ on 19 (menu) | 19 | 10 |
| Presses ⏺⏺ (long press) from Idle | 10 | 20 (Pickup log) — nice-to-have menu item |
| Presses ⏺ on 20 (scroll) | 20 | 20, next row highlighted |
| Presses ⏺⏺ on 20 (back) | 20 | 10 |
| Box loses connection to laptop mid-transfer | 11 | 10, status dot → grey, with "connection lost" note |
