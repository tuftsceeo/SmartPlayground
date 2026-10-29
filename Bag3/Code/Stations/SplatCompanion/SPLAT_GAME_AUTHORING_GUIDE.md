# Splat game authoring guide

Rules for games that run on the Splat Companion hub (`Companion/`), alone or with Bag3 MockWands.

- The `play()` contract and the `SplatGroup` API are in [Companion/README.md](Companion/README.md).
- Evidence is in [docs_and_design/2026-09-30-splatecho-freeze-results.md](../docs_and_design/2026-09-30-splatecho-freeze-results.md) and its logs folder.
- `<example>` blocks come from Splat Echo (`Companion/splatecho.py` with `MockWand/splatecho.py`). They show one way to apply a rule and are not requirements for other games.

Each rule is tagged with how it was established:
- **[measured]**: shown on hardware with a bench script or logs.
- **[play-tested]**: reported by a player in play sessions.
- **[design]**: a convention, not measured.

## Using the Splats

1. **Call `splat.poll()` on every loop iteration.** It services the BLE links, keepalives, switch reads and button debounce. It returns `"press"`, `"release"` or `None`, and `splat.last_index` names the Splat. [design]
2. **Unit `i` is Splat `i % splat.count`; `max_splats` defaults to 4.** A unit whose Splat never connected cannot be pressed. [measured]
3. **Before the first prompt that uses the Splats, wait until `splat.connected_count == splat.count`,** with a timeout; log a warning if you start short. [measured]
   <example>`SPLAT_WAIT_MS = 20000`, checked in the lobby.</example>
4. **When a Splat's link becomes ready mid-game, repaint its current pattern.** A late or reconnected Splat otherwise stays dark. [measured]
   <example>`_check_links()`, called from every `poll()`.</example>
5. **Each Splat has 14 LEDs: even numbers (0, 2, … 12) are the inside ring and odd numbers (1, 3, … 13) are the outside points.**
   - `link.setLEDs(mask, r, g, b)` changes only the LEDs in `mask`.
   - `setLEDsON` sets all 14, and `allLEDsOff` clears them.
   - Positions within a ring do not follow the Splat's shape, so address the inside and outside groups, not single LEDs.

   [measured]
6. **Space commands to one Splat at least 50 ms apart.** `splat_link.py` enforces this with `ble_splat._WRITE_PACE_MS = 50`, and the limit covers switch reads and keepalives too. Commands 20–30 ms apart were occasionally dropped. [measured]
7. **The pacing is per Splat and blocks.** When several Splats change together, send the first command to every Splat, then the second to every Splat, so the waits overlap. [design]
8. **A new sound replaces the one playing.** Splat sounds last 0.5–1 s. LED commands sent while a sound plays are applied. [measured]
9. **Splats never confirm a command.** Give every game state a resting Splat pattern, and repaint it on each state change and after each temporary effect, so a lost command lasts one state at most. [design]
10. **Never `machine.reset()` the hub while Splats are connected;** exit through `close_all()` (main.py does this on Ctrl-C and exceptions). A stranded Splat, or one left unconnected for a few minutes, stops advertising until its button is pressed or it is power-cycled. [measured]
11. **The hub has no external antenna.** `boot.py` selects the onboard antenna before BLE starts, and BLE signal strength depends on it. See the C6 antenna rule in the root `AGENTS.md`. [measured]

## Using the Splats with wands

1. **Send hub → wand game messages by unicast** (`enow.send_to(mac, msg)`) to each player, and check `enow.last_acked`; retry a few times. Broadcasts are not ACKed or retried, and lost ones deadlocked a game. [measured]
2. **Send wand → hub messages with `enow.enow.send(hub_mac, json.dumps(msg), True)`,** which returns the ACK. The wand's `send_to()` returns `True` without checking. [measured]
3. **Never wait for one message without a resend.**
   - Give each request an id that does not repeat within a game.
   - Resend the request until a reply carrying that id arrives, and ignore replies with any other id.
   - Do not key on game state that can repeat (scores, lengths, rounds).

   [measured]
   <example>`echo_add_now` carries `"add"`, a counter started from the clock, and is resent every 1 s. A length-keyed version answered a new request with an old step.</example>
4. **Number every hub → wand message.** A wand drops a message whose number equals the last one it received, which covers a delivery whose ACK was lost. [design]
   <example>`"q"` on every message to players.</example>
5. **The hub decides every state change and tells every wand.** A wand leaves a state on the hub's message, whichever device took the input. [design]
   <example>`echo_added` ends add mode on the wand, whether the step came from the wand or a Splat.</example>
6. **When the Splats and a wand can both express an action, accept either.** One player can then cover several roles. [play-tested]
   <example>A step is added by a Splat press or by wand tilt plus button.</example>
7. **Wands join by broadcasting a hello until the hub replies by unicast.** The modem can hold stale hellos from before a hub restart. Restart the wands before the hub, and restart both together. A wand cannot rejoin a running game. [measured]
8. **A wand may block for a short animation or tune while hub messages arrive.** ACKed unicast and the receive buffer hold them. [measured]
   <example>Up to about 3 s for a result.</example>

## Prompts and state outputs

1. **Give each game state a distinct output on every device the player looks at:** a wand icon, a Splat pattern and, at state changes, a sound. Players could not tell states apart that shared an output. [play-tested]
2. **Only the device whose turn it is shows the action prompt.** Every other device shows one waiting output, the same one in every state. [play-tested]
   <example>The other wand shows a dim `SHAPE_HOURGLASS` throughout.</example>
3. **Answer every input,** including one the current state does not accept. A silent press read as a broken Splat. [play-tested]
   <example>The Splat's outside LEDs blink red for 200 ms, with a low buzz on the hub.</example>
4. **A selector shows only selectable values.** There is no neutral or "nothing chosen" state that looks like an option. [play-tested]
   <example>The add plus always shows a Splat color, and holding the wand flat keeps the last pick.</example>
5. **Reserve colors.** A color that stands for a Splat must not also mean a player or a prompt. Keep neutral icons and indicators white. [play-tested]
   <example>Splat colors mean Splats, green means "press now", green or red is a result, and everything else is white. Player colors cyan and orange were dropped because they read as Splat options.</example>
6. **Use the hub buzzer (GPIO19, `hubtype` `has_buzzer`) for state changes everyone shares, and a wand's buzzer for that player's own events.** [design]
   <example>The hub plays `"start"` and `"question"`; the wand plays its turn chirp, the correct-press beep, and `celebrate()` or `error()` for its result.</example>

## Timing

1. **At least 50 ms between commands to one Splat** (see "Using the Splats", rules 6–7). [measured]
2. **Make each state change visible:** a short neutral gap, or a distinct cue, before the next state's output. [play-tested]
   <example>A 400 ms all-dark gap (`PHASE_GAP_MS`) between phases.</example>
3. **After a player's input, leave its confirmation on screen briefly before the next prompt.** [play-tested]
   <example>The added step is shown for 450 ms, then a 1200 ms pause (`ADD_PAUSE_MS`).</example>
4. **Resend unanswered requests on a fixed interval of about a second;** do not wait indefinitely. [measured]
5. **Keep any single blocking call on the hub under about 1 s.** Buzzer tunes and `time.sleep_ms` stop polling of the Splats and ESP-NOW. [design]
6. **Discard Splat presses that queued during a gap or animation before reading input for a new state:** poll through the gap and ignore what arrives. [design]

<example>

Splat Echo timing:

| What | Value |
|---|---|
| Playback step on / gap | 450 / 250 ms |
| Time allowed per press when repeating (`STEP_MS`) | 4 s |
| Lobby wait for Splats / for a second wand before solo | 20 s / 8 s |

</example>

## Icons on wands and LED patterns on Splats

1. **Use the 5×5 `SHAPE_*` glyphs in `MockWand/lib/leds.py` for wand states, one glyph per state.** Draw them by writing `leds.np` directly (icon pixels in the color, the rest off, then `np.write()`). [design]
2. **Use a dim version of a glyph for "waiting / not your turn",** and the full-brightness version for "act now". [play-tested]
3. **Encode Splat states with the inside and outside groups and with how many LEDs are lit,** not single positions. A mask leaves the other LEDs unchanged, so one group can mark the state while the other shows content. [measured]
4. **Repaint a partial pattern in two passes:** `allLEDsOff()` to every affected Splat, then the masks. End each temporary effect by restoring the state's resting pattern. [design]
5. **Light all 14 LEDs, with the Splat's sound, as feedback for an accepted press.** [design]

<example>

Splat Echo states:

| State | Active wand | Other wand | Splats | Hub |
|---|---|---|---|---|
| Add | `SHAPE_PLUS` in the selected Splat's color | dim `SHAPE_HOURGLASS` | Outside LEDs in each Splat's own color; a press adds that Splat | `"question"` |
| Watch | `SHAPE_HOURGLASS`, white | dim `SHAPE_HOURGLASS` | LEDs 1 and 7 red; the shown step lights the other 12 in its color, with its sound | — |
| Play | `SHAPE_PLAY`, green | dim `SHAPE_HOURGLASS` | LED 1 green; a correct press lights all 14 in its color, with its sound | `"start"` |
| Input not accepted | — | — | Outside LEDs blink red for 200 ms | Low buzz |
| Result | Rainbow, or red | Rainbow, or red | All green or all red | — |

Resting patterns are set by `base(mode)` and restored with `base(mode, only=i)`.

</example>
