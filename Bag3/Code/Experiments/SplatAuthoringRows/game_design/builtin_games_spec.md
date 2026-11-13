# Built-in example games: build spec

Seven games, one per game type except 6 and 7, to ship as built-in examples on Bag3 wands, the
icon display, and the ChatBroadcast example gallery. Each game teaches one computational thinking
(CT) outcome and builds in the access rules of ChatBroadcast `knowledge/accessibility.md`.

Generated games copy these closely, so each one is also the canonical example of its type.

## Scope and rules

- **Equipment:** wands, Splats, the icon display (16x16, with its own NFC reader). No speaker station.
- **Tree:** Bag3 only. Work under `Bag3/Code/Experiments/SplatAuthoringRows/` until promoted, as the
  plan requires. Bag2 is not touched.
- **Splat games assume the experiment's code is verified on hardware:** type 2 (`SPLATS_LOCAL`) and
  the Splat host role.
- **Device code:** AGENTS.md applies. No allocation ahead of radio bring-up, `py_compile` only
  off-device, f-strings allowed, no type annotations, `time.sleep_ms(1)` in every serial loop.
- **Start:** one step, tap the game card. Every wand game returns on `stop` or a `start_game` for
  another game, as the canonical template does.

## Shared access rules (apply to every game)

| Rule | Implementation |
|---|---|
| Color is never the only signal | Each color also has a wand matrix shape (`leds.show_shape`) and, on Splats, its own note. |
| Color-blind-safe pairs | Prefer blue/yellow. Avoid red/green as a pair that must be told apart. |
| Every key sound is also visible | Each speaker (`buz`) cue has a matching light change. |
| Every key light is also audible | Each light cue has a speaker cue. Distinct sounds per event kind: turn, right, wrong, win. |
| Gentle mistakes | A soft low beep, never a long or loud one. Sound and vibration cues stay under 4 s. |
| Predictable | The same signal always means the same thing, across all seven games. |
| Progress shown | Rounds, pattern length or score shown on the matrix or display. |
| Mobility | Splats can be pressed by hand; no game requires running. |

**Shared signal set** (use these exact cues in every game, so children learn them once):

| Event | Light | Sound |
|---|---|---|
| Your turn / watch | white pulse | `buz.info()` |
| Right | green tick shape | `buz.confirm()` |
| Wrong | dim amber, no flashing | one soft low `buz.beep` |
| Level up | brief sparkle | `buz.success()` |
| Win / end | rainbow | `buz.celebrate()` |

## Color, shape and note table

Shared by Simon Stomp, Pattern Stomp and Color Says. Splat color names are `splat_api.COLOR_RGB`
keys; notes are `NOTE_VALUES` keys.

| Color | Splat color | Wand shape | Splat note |
|---|---|---|---|
| Blue | `turnblue` | circle | `note_c` |
| Yellow | `turnyellow` | triangle | `note_e` |
| Purple | `turnpurple` | square | `note_g` |
| White | `turnwhite` | star | `note_c_high` |

Red and green are left out of the patterns: green is the "right" cue, and leaving both out avoids
the red/green pair. Shapes are 5x5 matrix index lists, defined once per game.

---

## 1. Echo Beat (type 1: one child, wand only)

> "Your wand beeps a little rhythm of short and long beats. Shake it back the same way. Get it
> right and the next rhythm is one beat longer."

- **CT:** pattern recognition (strong); decomposition (a long rhythm as short pieces).
- **Access target:** 10/10.

**Play**
1. Show round 1 on the matrix. Beep a rhythm of 2 beats (piezo speaker), each beat short (150 ms) or long (450 ms),
   and flash the matrix in time with each beat.
2. Show "your turn" and record shakes for up to 5 s after the first shake.
3. Compare shake count and gaps. A gap is "long" if it is over the short/long midpoint. Allow
   ±40% timing tolerance.
4. Right: confirm, add one beat (max 6). Wrong: soft beep, replay the same rhythm. Three wrong in a
   row: drop one beat.
5. Win at 6 beats: celebrate, then start again at 2.

**Notes**
- Rhythms come from a fixed list per length, not random, so a child can practice the same one.
- Shake detection: reuse the shake logic in `shake.py`.

## 2. Simon Stomp (type 2: one child, wand plus 2 Splats)

> "Your wand shows a pattern of colors. Stomp your Splats in that order. Each time you get it
> right, the pattern grows by one."

- **CT:** pattern recognition, algorithms (strong).
- **Access target:** 10/10.

**Declarations:** `SPLATS_LOCAL = 2`; `play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None)`.
The loader refuses the game unless 2 Splats are connected, so `splats` is not `None`.

**Play**
1. Splat 0 is blue, Splat 1 yellow (table above). Both glow dim between turns.
2. Show the pattern on the wand: each step shows the color's shape, lights that Splat brightly
   and plays its note. Start at length 2.
3. Read `splats.poll()` each loop. Each press lights and sounds that Splat and is compared with
   the next step.
4. Right sequence: confirm, add a step (max 8). Wrong: soft beep, replay the pattern.
5. Win at 8: celebrate.

**Notes**
- The loop calls `enow.poll()` and `splats.poll()` every pass.
- Leave the Splats as they are at exit; the wand turns them off after the game.
- This replaces Color Pads as the type 2 example in `knowledge/wand_type2.md`.

## 3. Move Mixer (type 3: build a dance on the wand; share it to the icon display)

> "Move cards are spread far apart around the playground: jump by the slide, spin by the fence,
> wave by the tree, freeze by the bench, and a 'do it twice' card in the middle. Everyone runs to
> collect moves and builds their own dance. When you like your dance, share it, and it plays on
> the big display for everyone to dance along."

- **CT:** algorithms (strong: a dance as ordered steps, with a repeat step); decomposition
  (a dance as moves).
- **Gross motor:** running between cards to build, then dancing.
- **Graded?** No. The wand does not check moves; dancing is honor system and just for fun.
- **Access target:** 10/10. With no motion checks, any move can be done seated or adapted.
- **Why type 3:** every child builds on their own wand at once. The display is output only: it
  plays the latest shared dance, replacing the one before. Sharing is the child's choice, and
  nothing on the display says who shared. With no display, children still build and dance.

**Play (on the wand)**
1. **Collect:** tap move cards to add steps, up to 6. Each tap shows the move's shape and plays
   its tone; the matrix edge shows the step count. `twice` repeats the previous step.
2. **Preview:** press the button to play the dance on the wand: each step's shape and tone, to a
   steady beat (one step every 2 s), so the child can dance it.
3. **Change:** tap a move card during preview to replace that step; a long button press clears the
   dance.
4. **Share:** tap the `share` card (beside the display, or anywhere). The wand plays a short
   sparkle and broadcasts once: `{"type": "dance", "s": ["jump", "jump", "spin", "freeze"]}`.

**Display (output only)**
- Plays the shared dance as icons in a loop, one step every 2 s, with a step counter and a
  beat bar so dancers can keep time.
- Holds each dance for at least 2 full loops before a newer one replaces it, so a dance is never
  cut off mid-way. The newest share waiting replaces any older waiting one.
- No sender data is sent or shown.

**Move cards and icons**

| Card | Move | Icon (present) | Wand tone |
|---|---|---|---|
| `move_jump` | jump | `bunny` | rising chirp |
| `move_spin` | spin around | `sunflower` | swirl |
| `move_wave` | wave arms | `hand` | two beeps |
| `move_freeze` | freeze | `snowflake` | low hold |
| `move_twice` | repeat the last step | — (shows "x2") | double click |
| `share` | send this dance to the display | — | sparkle |

**Notes**
- Card names are prefixed `move_` to avoid the existing `jump` game tag; check `share` too.
- Place move cards at least 10 m apart.
- With display station mode (ask D3), the display needs no game of its own for this.

## 4. Color Says (type 4: teacher's wand leads)

> "I tap a color card on my wand and every wand shows that color and its shape. Blue circle means
> wiggle, yellow triangle means jump, purple square means freeze, white star means spin."

- **CT:** algorithms (strong: follow a rule table); abstraction (a color stands for a move).
- **Access target:** 10/10.
- **Framing:** Simón Dice / Simon Says. Name it in the teacher text.

**Play**
1. Leader: the teacher's wand. Use the same leader mechanism as the existing Freeze Dance game.
2. The teacher taps a color card (`turnblue`, `turnyellow`, `turnpurple`, `turnwhite`). The leader
   broadcasts the color.
3. Every wand shows the color with its shape and plays that color's note.
4. "Freeze" (purple square): each wand checks for movement for 3 s and shows a soft amber if it
   moved. No score; a reminder only.
5. The rule table (color → move) is on a printed card the teacher can change.

**Notes**
- Movement check while frozen: reuse Freeze Dance's motion check.
- No running moves in the default table.

## 5. Picture Moves (type 5: everyone, led by the icon display)

> "The display shows an animal. Everyone moves like that animal until the next one appears. Your
> wand chimes when it changes."

- **CT:** abstraction (strong: an animal reduced to one way of moving).
- **Access target:** 9/10 (blind children follow the wand's chime plus a partner naming the animal).

**Play**
1. Tap the game card on the display to start.
2. The display shows an animal icon for 15 s, then the next.
3. On each change it broadcasts the animal name. Wands play a change chime and show a shape; a
   wand near a Splat host can also play the animal's sound where one exists.
4. After 8 animals, a "rest" icon and end.

**Icons (present):** `frog`, `bird`, `fish`, `bunny`, `snake`, `elephant`, `butterfly`, `penguin`,
`turtle`, `monkey`, `dog`, `cat`, `duck`, `torogoz`.

**Notes**
- Mix animals from several regions; `torogoz` is El Salvador's national bird.
- Moves are the children's choice; there is no wrong move.

## 6. Code Breakers (type 8: small group at the icon display)

> "Your group gets a set of animal cards. Tap three on the display in the right order to open the
> treasure. The display shows how many are in the right place."

- **CT:** algorithms (strong: order matters); pattern recognition (using the feedback).
- **Access target:** 9/10 (raised marks on cards for blind children).

**Play**
1. The display picks a secret code of 3 from a set of 5 animal cards.
2. The group taps 3 cards in turn. Each tap shows that animal small, in its slot.
3. After 3, the display shows feedback: one bright dot per animal in the right place, one dim dot
   per right animal in the wrong place (a simplified Mastermind).
4. Right code: a win animation (`sparkles` or `star`), then a new code. Wrong: clear and try again,
   keeping the last guess visible above.
5. Show the try count.

**Icons:** `frog`, `cat`, `fish`, `bird`, `bunny` for the cards; `star`, `sparkles` for the win.
No treasure or chest icon exists; use `star`, or add a `chest` icon to `Stations/IconDisplay/icons/`
and re-run `ChatBroadcast/tools/sync_icons.py`.

**Notes**
- Layout: slots and feedback separated by blank space, per the display guidance.

## 7. Pattern Stomp (type 9: up to 4 children, Splat host + 4 Splats)

> "The host lights a pattern across the four Splats. The group stomps it back in order. Each round
> adds one more step."

- **CT:** pattern recognition, algorithms (strong).
- **Access target:** 10/10.

**Declarations:** host game per the type 9 template in `knowledge/splat_host_games.md`
(`SPLAT_HOST = True`, `SPLATS_MIN = 4`, `play(..., batt=None, net=None)`). Write it fresh from the
template, as `host_splattag.py` was.

**Play**
1. Splats 0-3 take the four colors and notes in the table above. Each glows dim between turns.
2. The host shows the pattern: each step lights one Splat brightly and plays its note. Start at 2.
3. Any child may stomp; the group plays as a team. The host compares stomps with the pattern.
4. Right: confirm on the host and every player wand, add a step (max 10). Wrong: soft beep, replay.
5. Player wands show the round number.
6. Lost Splat: pause and show the shared "watch" signal until it returns or the host ends the game,
   as the template does.

**Notes**
- Scoring is the group's. A Splat does not know who stomped it.
- This replaces `host_lobbytest.py` as the second host example. Splat Tag stays the first.

## Bonus games (multi-station; need new system support)

These use several stations as one game: one host, the rest peripheral. Each needs a protocol
the system does not have yet (asks M1-M3 below). Build after the seven above.

### B1. Habitat Hop (several icon displays: 1 host, 2-4 peripheral)

> "The big display shows an animal. Run to the display showing where it lives, ocean, forest,
> desert or pond, and tap that habitat's card with your wand. The animal moves into that habitat
> on the display, and the big display counts how many found their home."

- **CT:** abstraction, classification (strong: sort by one feature, where it lives).
- **Type:** 5 (whole class, led by the host display), with wands at the center: each child's wand
  checks the answer.
- **Host display:** shows the current animal and a count of homes found. Every 30 s it picks a new
  animal and broadcasts it.
- **Peripheral displays:** each shows one habitat icon and, when a child's wand reports a correct
  answer, briefly shows the animal there. A habitat card sits beside each peripheral.
- **Wand:** knows the current animal from the host's broadcast. A habitat card tap is checked on
  the wand: right gives "right" and reports to the host and that habitat's peripheral; wrong gives
  a hint (the right habitat's shape) with no penalty.
- **Icons (all present):** habitats `ocean`, `forest`, `desert`, `pond`, `igloo`; animals `whale`,
  `octopus`, `shark`, `owl`, `deer`, `camel`, `frog`, `duck`, `swan`, `turtle`, `penguin`,
  `polar_bear`, `torogoz`, `parrot`, `monkey`.
- **Access:** 9/10. Walking pace is fine; blind children play with a partner.
- **Needs:** M1 (display roles), M3 (targeted messages).

### B2. Stepping Song (8 Splats: one lead host, one peripheral host)

> "Eight Splats in a row make a giant xylophone, low C to high C. The host plays a short tune by
> lighting the Splats. The group steps it back. Then a child composes a tune with their wand and
> the group plays it."

- **CT:** pattern recognition, algorithms (strong: a tune as an ordered list of steps);
  decomposition in the composing round (a tune as phrases).
- **Type:** 9, extended to two Splat hosts.
- **Setup:** the 8 Splats map to the 8 note names in `NOTE_VALUES` (`note_c` ... `note_c_high`).
  The lead host holds Splats 0-3, a peripheral host holds 4-7; the lead runs the game and sends
  the peripheral which of its Splats to light and play.
- **Play:** listen round (the lead plays 3 notes, lighting each Splat), echo round (the group steps
  them back, any child may step), grow by one note to 8. Composing round: one child taps note
  cards on their own wand, the lead plays the result, the group echoes it.
- **Colors:** low notes blue, middle yellow, high purple, top C white, so the scale is also visible.
- **Access:** 10/10. Strong for blind children (pitch rises along the row); Splats can be pressed by
  hand.
- **12-Splat variant, Frog Crossing:** 3 hosts, a 3x4 grid. One child codes a path with arrow
  cards on their wand (forward, left, right); the grid lights the path; a friend walks it; the
  group debugs a path that falls in the water. Algorithms and debugging (strong).
- **Needs:** M2 (multi-host Splat groups).

## New system asks from these games

| ID | Ask | Games | Conflict / note |
|---|---|---|---|
| **M1** | Icon display roles: one host runs the game, peripherals show what it sends | Habitat Hop | Icon display games today have no roles. |
| **M2** | Splat host federation: a lead host drives peripheral hosts' Splats (4 each), with presses forwarded back | Stepping Song, Frog Crossing | The pooled path removed in Phase 2 was a similar idea for player wands; this is host-to-host only. Latency per step adds a radio hop. |
| **M3** | Targeted messages to one display or host | Habitat Hop, Stepping Song | Conflicts with the decision that icon displays and station mode never filter by sender or target. Needs a decision: an optional target field ignored by single-station games. |
| **D2** | A `dance` message the display loops as last-received, held for 2 loops minimum | Move Mixer | Small; fits the existing "every display obeys" rule. No sender data. |
| **D3** | Display station mode: with no game running, the display obeys `show` messages (icon by name, a few pixels, short text) from any wand | Move Mixer; Melody once the speaker works | Mirrors Splat station mode. Removes the need for a display game per wand game. |

---

## Delivery checklist (per game)

- **Code:** under the experiment (`wand/games/` for wand and host games; a display games folder for
  the icon display games, mirroring `Stations/IconDisplay/games/`).
- **Check:** `py_compile`; the experiment's unit tests; `node js/splat_game_check_test.mjs` for the
  Splat games.
- **Game tags:** new slugs `echobeat`, `simonstomp`, `movemixer`, `colorsays`, `picturemoves`,
  `codebreakers`, `patternstomp`. Check none collide with existing tags. Record the four consumers
  (`lib/game_tags.py`, `Live_Page/WebApp2/hubCode2/game_tags.py`, `commands.json`, `wand_icons.html`)
  as promotion steps; don't edit them in the experiment.
- **Gallery:** draft `js/examples.js` entries (id, name, icon, category, description, tags,
  `starterPrompt`, `simProfile`) in the experiment, not the live file.
- **Teacher text:** the quoted request above, the card list and the access notes, for the gallery
  description.
- **Report:** files changed and check results, under 150 words, per game.

## Out of scope

- Speaker station games (abilities unverified).
- Team totals across wands, peer token passing, and rhythm relay (not built).
- Type 6 and type 7 examples.
- Bonus games B1 and B2 until M1-M3 are decided and built.
