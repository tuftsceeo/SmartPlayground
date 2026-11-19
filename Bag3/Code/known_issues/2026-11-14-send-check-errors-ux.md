---
title: Send-time game check errors are technical, late, and have no fix path
date: 2026-11-14
status: fixed in code 2026-11-16 (S10), deployed 2026-11-18; not checked by a person
devices: [Splat host wand, Wand (Mock Wand)]
components: [ChatBroadcast send checks, toasts, Simulator error panel, Simple mode]
code:
  - Bag3/Code/ChatBroadcast/js/splat/splatGameCheck.js
  - Bag3/Code/ChatBroadcast/js/upload.js
  - Bag3/Code/ChatBroadcast/knowledge/splat_host_games.md
open:
  - Send-time check errors show as a toast in code terms (net.poll, splat_lost) a teacher cannot act on.
  - The check runs only at send time, after the Simulator has accepted the game.
  - No "ask the chat to fix this" path from the toast, unlike the Simulator's "Can't simulate" error.
  - Simple mode should send these errors to the chat for a fix automatically.
keywords: [toast, send check, splatGameProblems, splat_lost, wand_lost, net.poll, Can't simulate, auto fix, Simple mode, error handling, UX, knowledge]
related:
  - Bag3/Code/known_issues/2026-11-14-splat-host-wand-count.md (same test game)
---

# Send-time game check errors, 2026-11-14

Found testing ChatBroadcast (stress-test prep) with a generated Splat host game (Memory). On Send to
device a toast said:

> A Splat host game must handle the ("splat_lost", ...) event from net.poll(): pause, skip or carry
> on, but not ignore it.

## Two problems
1. **Knowledge.** The model wrote a host game without `splat_lost` handling, although
   `knowledge/splat_host_games.md` requires it.
2. **UX (the user's main concern).**
   - The message is in code terms. A non-technical user does not know what `net.poll` or
     `splat_lost` is and cannot fix it.
   - It appears late: the game had already passed the Simulator. `splatGameProblems()`
     (`js/splat/splatGameCheck.js`) is called only from `js/upload.js` at send time.
   - There is no way to hand it to the chat. The Simulator's "Can't simulate" error offers its error
     text for the chat to fix; this toast does not.

## Need (user, 2026-11-14)
- Run these checks before Send, with the simulation check, as soon as a game is made.
- Treat a failure like "Can't simulate": offer a path that asks the chat to fix it.
- **Simple mode: send the error to the chat automatically.** A Simple mode user can never resolve a
  simulation error or a check like `splat_lost` themselves, so they should not be asked to.

## 2026-11-19: outcome

Fixed in ChatBroadcast on 2026-11-16 (stress-test plan S10, commits `27d1f716` and `1077fd13`) and deployed with the hosted app on 2026-11-18. No person-checked result is recorded.
