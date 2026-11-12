---
title: Simple mode design — large changes not built
date: 2026-11-11
status: open
devices: [wand, icon_display, splat]
components: [ChatBroadcast, Simulator]
code:
  - Bag3/Code/BroadcastCode/ChatBroadcast/js/prompt/buildRequest.js
  - Bag3/Code/BroadcastCode/ChatBroadcast/knowledge/policy.md
  - Bag3/Code/BroadcastCode/ChatBroadcast/knowledge/platform.md
  - Bag3/Code/BroadcastCode/ChatBroadcast/js/chat.js
  - Bag3/Code/BroadcastCode/ChatBroadcast/js/hardware.js
  - Bag3/Code/BroadcastCode/ChatBroadcast/js/library.js
  - Bag3/Code/Simulator/sim-room.js
  - Bag3/Code/Simulator/js/panels/wands.js
  - Bag3/Code/Simulator/js/panels/splats.js
  - Bag3/Code/Simulator/js/lobby_game.js
  - Bag3/Code/Simulator/js/splats.js
  - Bag3/Code/Simulator/js/panels/splatController.js
  - Bag3/Code/Simulator/README.md
open:
  - Agent does not state minimum devices or a fixed vs open-ended flag
  - Simulator does not open with the minimum number of wands
  - Splats belong to a wand, not to a shared group or a dedicated Splat companion wand
  - Splat zones (inside/outside, left/right) are not drawn as fills
  - Simulator device art is hand-drawn, not the design-system icons
  - Structured game card (parseable reply format and renderer) does not exist
  - Saved games do not store versions, so no "N versions" label
keywords: [simple mode, design corrections, minimum devices, fixed, open-ended, Splat group, Splat zones, device art, game card, versions, teacher hub, Splat companion, Splat controller]
aliases: []
---

# Simple mode design: large changes not built

The design canvas is https://claude.ai/artifact/WjCoDBJYxUKwinww3s8y2E. The corrections it answers
are in `BroadcastCode/docs_and_design/2026-11-11-simple-mode-design-corrections.md`; the sorting
into quick, medium and large is in `2026-11-11-simple-mode-implementation-scope.md` (same folder).
Quick and medium changes are on branch `simple-mode-corrections`. These are the large ones, each
cross-cutting enough to need a decision first. They record future design intent, not defects. Line numbers are as of branch `Chat_to_Tap_Doggle`
and drift.

## 1. Device minimums from the agent

The agent states the minimum devices for a playable game (wands, icon displays, NFC tags, Splats)
and whether the count is fixed or open-ended. `[GAME_SETTINGS:]` carries only `wands` (1–4) and
`wand_splats` today. Needs changes to `js/prompt/buildRequest.js`, the knowledge files, the
`chat.js` parser (~200–230), `hardware.js` and `library.js`, and reaches advanced and dev views.
The requirement pills currently derive displays from the icon role's code and Splats from
`wands × wand_splats`.

## 2. Simulator opens with the minimum

Fixed-count games start every wand and hide the add tiles; open-ended games start with the minimum
and show them. Needs item 1's flag, plus `Simulator/sim-room.js` (:36–39, :132, :472, :483–485),
`js/panels/wands.js` (:117–118, :179–189) and `Simulator/README.md` (:83–122).

## 3. Splats as a shared group, or a Splat companion wand

Splats are owned by a wand (`lobbyGame.wandSplats`, attached to `room.wand`). Showing them as one
group not tied to a wand changes `sim-room.js` (:375–455), `js/lobby_game.js` and `js/splats.js`.

Direction under consideration (2026-11-12): a dedicated **Splat companion** wand, in the spirit of
the historical Splat Companion. It is not a game wand. It is assigned its role during send, or by
tapping a card that puts it into Splat pairing mode. From then on its only jobs are reading Splat
NFC tags, pairing with 1 to 4 Splats (maximum not decided), and running the Splat side of the game.

In the all-wands dialog it would be a full-size Splat controller card (a wand card's size) with:

- a 5x5 display showing the companion's own state;
- a button for resets, or another role the game assigns;
- an NFC reader;
- four quarter-size Splat cards in a 2x2 grid as pairing slots, each filled by clicking it
  (standing in for pairing).

A mock-up of that card is in `Simulator/js/panels/splatController.js`, added by the dialog's
"+ Add a Splat controller". It is layout and interaction only: it runs no Python, is not on the
radio bus and reaches no game. Pairing a slot lights that corner of the 5x5 display; the button
flashes the display. Splat cards for game wands stay independent of their wand when cards are
reordered.

Not decided or built: the firmware companion mode, how send or a card assigns the role, the
pairing protocol, the slot maximum, and how the chat agent writes games for a companion.

## 4. Splat zone rendering

Inside vs outside is modeled per LED (`js/panels/splats.js` :76–78, :131–132, :179–191), so two
fills are the smaller part. Left vs right needs new LED addressing, kept in step with
`SplatCompanion/Companion/splat_api.py` and the generated `splatActions.js`
(`tools/sync_splat_actions.py --check`). Each zone is a solid color with a gradient only where two
zones meet, or into gray when one is off.

## 5. Simulator device art

The wand, icon display and Splat drawings (`renderer.js`, `wand-sim.js`, `panels/display.js`,
`panels/splats.js`) are hand-drawn. Replacing them with the design-system icons is separate from
the ChatBroadcast `js/icons.js` swap, which is done.

## 6. Structured game card

A parseable reply format: title, summary, device list, exactly four "How to play" steps with icon
keys, an optional legend ("What the clues mean"), and at most two follow-ups with no trailing
question. Needs a card renderer and prompt changes in `knowledge/policy.md` (:52–71),
`knowledge/platform.md` and `js/prompt/buildRequest.js`. The prompt is shared by both modes, so the
format is either conditional on `advancedMode` (`buildRequest.js` :124) or accepted in both. Reply
markers are parsed at `js/chat.js` (:138–265).

## 7. Version count on saved games

"N versions" needs versions stored with the game; `js/library.js` (:28) saves only the current
code.

## 8. "Teacher hub" naming outside simple mode

Built: every mode says "teacher hub" for a Box or Dial (`js/device/bboxDeviceLink.js`
`deviceShortName()` / `deviceProductName()`).
