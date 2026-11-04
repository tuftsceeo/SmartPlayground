---
status: historical
note: >-
  Old development note, kept as a record. Not current guidance: rules, paths and plans
  here may be out of date. Check AGENTS.md and the code for current behavior.
---
# ChatBroadcast request context: open follow-ups

Current request layout (`ChatBroadcast/js/prompt/buildRequest.js`):

1. Knowledge base (cached).
2. `advanced.md` (cached, Advanced mode only).
3. `simulator.md` (cached, from the chat's first simulator problem).
4. Session block: icon names, Splat actions and editor code, not cached.
5. Chat history.
   - Window: all messages up to `HISTORY_MAX` (30). Past that it drops back to `HISTORY_MIN` (15)
     and grows again.
   - Old code is replaced by `[code: N lines, sent to editor]`.
   - A note on the first message says how many earlier messages are left out.

## Not done

- **Cache the history.** The session block changes every turn and sits before the messages, so
  nothing after it can be cached. One way to do it:
  1. Move the editor code into the latest user message.
  2. Put a `cache_control` breakpoint on the last history message.

  The stepped window already keeps the start of the history fixed between drops, which caching
  needs.
- **Log usage.** Show each reply's `usage` in the Developer mode footer: `input_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens` and `output_tokens`. This measures what
  a request really costs.
- **Simulator: helpers called from a `lambda` or generator expression.** `transform.py` makes
  every plain `def` async. A call from a `lambda` or a generator expression is not awaited, so it
  returns a coroutine.
  - `sorted(x, key=lambda v: score(v))` raises `TypeError` in the simulator.
  - `any(f(i) for i in r)` is always true in the simulator.
  - Both work on a wand (confirmed 2026-10-21).
  - A fix would make only functions that reach a sleep, the radio or another async call async.
  - `knowledge/simulator.md` records the gap.
