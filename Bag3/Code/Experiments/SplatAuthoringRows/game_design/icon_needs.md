# Icon needs: 5x5 wand shapes and 16x16 display icons

Inventory checked 2026-11-13 against:

- **16x16:** `Bag3/Code/Stations/IconDisplay/icons/` (161 icons, the source of truth).
- **5x5:** `SHAPE_*` in `Bag3/Code/Wand Module/lib/leds.py` (letters, digits and about 70 symbols),
  mirrored by hand in `ChatBroadcast/js/ledicons/shapes5.js`.

Every icon listed under "Missing" was checked by filename and does not exist. Names are proposals.

Priority: **P1** a built-in game needs it; **P2** cooking parity or a backlog game needs it;
**P3** useful for future games.

## 1. Built-in games

| Game | Size | Need | Have | Missing |
|---|---|---|---|---|
| Color table (Simon Stomp, Pattern Stomp, Color Says) | 5x5 | circle, triangle, square, star | `SHAPE_O`/`SHAPE_0`, `SHAPE_RECTANGLE`/`SHAPE_BORDER`, `SHAPE_STAR` | **P1 `SHAPE_TRIANGLE`** |
| Color table, on the display | 16x16 | the same four shapes | `star` | **P1 `circle`, `triangle`, `square`** |
| Shared signal set | 5x5 | tick, sparkle | `SHAPE_CHECK`; sparkle is an animation | — |
| Move Mixer | 5x5 | jump, spin, wave, freeze, twice | `SHAPE_ARROW_UP`, `SHAPE_SPIRAL`, `SHAPE_DOUBLE` | **P1 `SHAPE_HAND`** (wave), **P1 `SHAPE_SNOWFLAKE`** (freeze) |
| Move Mixer | 16x16 | jump, spin, wave, freeze, twice | `bunny`, `sunflower`, `hand`, `snowflake`; "x2" as `draw16` text | **P2 `spin`** (a spiral or turning figure; `sunflower` is a weak stand-in) |
| Code Breakers | 16x16 | five animals, win | animals, `star`, `sparkles` | **P2 `chest`** (the spec uses `star` until it exists) |
| Picture Moves | 16x16 | animals, end screen | animals, `ready`, `sleepy` | **P3 `rest`** (an end screen; `sleepy` works) |
| Echo Beat | 5x5 | short/long beat, turn | rows and `SHAPE_PLAY` | — |

## 2. Cooking at 16x16 (scale-ups of the wand game)

`cooking.py` uses seven ingredients and five dishes, all as 5x5 color images or shapes. Only two
have 16x16 icons.

| Item | Wand (5x5) | 16x16 |
|---|---|---|
| tomato | `SHAPE_INNER_3x3`, red | **P2 missing `tomato`** |
| milk | `SHAPE_RAINDROP`, blue | `milk` |
| cheese | `SHAPE_DIAG_L`, orange | **P2 missing `cheese`** |
| flour | `SHAPE_CHECKERS`, white | **P2 missing `flour`** |
| egg | `SHAPE_0`, green | **P2 missing `egg`** |
| butter | `SHAPE_RECTANGLE`, yellow | **P2 missing `butter`** |
| sugar | `SHAPE_POWER`, pink | **P2 missing `sugar`** |
| dish: fried egg | `EGG` image | **P2 missing `fried_egg`** |
| dish: pancakes | `PANCAKES` image | **P2 missing `pancakes`** |
| dish: pizza | `PIZZA` image | `pizza` |
| dish: pasta | `PASTA` image | **P2 missing `pasta`** |
| dish: cupcake | `CUPCAKE` image | **P2 missing `cupcake`** |
| idle flame | `SHAPE_FLAME` | **P2 missing `flame`** (also a general "hot" or "go" cue) |

Ice cream games: `icecream` and `paleta` exist; no gap.

Recipe Mix-Up (backlog) rotates dishes beyond pie. Present: `pupusa`, `taco`, `elote`, `beans`,
`churro`, `concha`, `pan_de_muerto`, `agua_fresca`, `apple`. **P2 missing: `tamal`, `pie`,
`masa` (or `corn`), `rice`.**

## 3. 5x5 symbols with no 16x16 match

These exist on the wand but not on the display, so a game cannot show the same symbol on both.

| 5x5 | 16x16 status |
|---|---|
| `SHAPE_CHECK` | **P1 missing `check`** (right answer) |
| `SHAPE_X` | **P1 missing `cross`** (not "wrong" in red; a neutral mark) |
| `SHAPE_QUESTION` | **P2 missing `question`** |
| `SHAPE_EXCLAIM` | **P3 missing `exclaim`** |
| `SHAPE_ARROW_UP/DN/L/R` | **P2 missing `arrow_up`, `arrow_down`, `arrow_left`, `arrow_right`** (directions, path coding) |
| `SHAPE_PLUS` | **P3 missing `plus`** |
| `SHAPE_PLAY`, `SHAPE_PAUSE` | **P3 missing `play`, `pause`** |
| `SHAPE_HOURGLASS` | **P2 missing `hourglass`** (timers, "wait") |
| `SHAPE_BULLSEYE` | **P3 missing `target`** |
| `SHAPE_DIAMOND` | **P3 missing `diamond`** (also a gem for treasure games) |
| `SHAPE_SPIRAL` | **P2 missing `spiral`** (doubles as Move Mixer "spin") |
| `SHAPE_RAINDROP` | **P3 missing `raindrop`** (`rain_cloud` exists) |
| `SHAPE_FLAME` | see cooking: `flame` |
| `SHAPE_NEUTRAL_FACE` | **P3 missing `neutral`** |
| `SHAPE_HAPPY/SAD/SLEEPY/ANGRY_FACE` | `happy`, `sad`, `sleepy`, `mad` exist |
| heart, star, moon, house, tree, fish, bird, ghost, music, lightning | all exist |

`SHAPE_PACMAN` and `SHAPE_INVADER` resemble trademarked game characters. Do not add 16x16
versions, and consider renaming or redrawing the 5x5 shapes.

## 4. 16x16 icons with no 5x5 match (for wand-side cues)

| Need | Use | Priority |
|---|---|---|
| `SHAPE_TRIANGLE` | color table | P1 |
| `SHAPE_HAND` | Move Mixer wave | P1 |
| `SHAPE_SNOWFLAKE` | freeze in Move Mixer and Color Says | P1 |
| `SHAPE_FROG`, `SHAPE_BUNNY`, `SHAPE_CAT`, `SHAPE_DOG` | wands echoing a display animal (Picture Moves, Habitat Hop) | P3 |
| `SHAPE_SUN`, `SHAPE_CLOUD` | weather themes | P3 |
| `SHAPE_SPLAT` | "stomp a Splat" cue | P3 |

## 5. Future games (P3 unless noted)

| Theme | Missing 16x16 | Present |
|---|---|---|
| Treasure and rewards | `chest` (P2), `coin`, `map`, `key`, `lock`, `gem` (or `diamond`), `trophy`, `medal`, `crown` | `star`, `sparkles` |
| Teams | `flag` (plain, colored by the game), team-neutral shapes (the circle/triangle/square above) | — |
| Feelings | `scared`, `neutral`/`calm`, `proud` | `happy`, `sad`, `mad`, `silly`, `surprised`, `sleepy`, `embarrassed`, `laugh`, `love` |
| Moves (Move Mixer extensions) | `spin`, `clap`, `stomp` (a foot), `run`, `reach` (arms up), `crouch` | `hand`, `jump_rope` |
| Instruments | `drum`, `guitar`, `marimba`, `bell`, `trumpet` | `music`, `maracas` |
| Weather | `wind`, `storm` | `sun`, `cloud`, `rain_cloud`, `snowflake`, `lightning`, `rainbow`, `umbrella` |
| Growing | `seed`, `pot` | `sprout`, `flower`, `sunflower`, `tree`, `leaf`, `marigold` |
| Coding and paths | arrows (P2), `start`, `finish` (a flag), `loop` | — |
| Instructions | `wand`, `card` ("tap a card"), `ear` ("listen"), `splat` exists | `eyes`, `hand`, `splat` |
| Habitats (Habitat Hop) | `jungle`, `farm` (or use `barn`), `cave`, `sky` | `ocean`, `forest`, `desert`, `pond`, `igloo`, `barn` |
| Story | `castle`, `dragon`, `robot`, `fairy` | `griffin`, `monster`, `witch_hat`, `rocket`, `astronaut` |

## Adding icons

- **16x16:** add to `Stations/IconDisplay/icons/`, then run `ChatBroadcast/tools/sync_icons.py`
  (`--check` for drift). Also copy by hand to `Stations/Icon Display Station/icons/` and
  `ChatBroadcast/iconmaker/`, per AGENTS.md. Until then, a generated game naming the icon is
  refused at send time.
- **5x5:** add to `Wand Module/lib/leds.py` and, by hand, to `ChatBroadcast/js/ledicons/shapes5.js`.
  `leds.py` is imported early on the wand: keep additions to constant tuples, nothing that
  allocates more at import than the existing shapes do (AGENTS.md radio-first rule).
- **Access:** shapes that carry meaning (the color table, right/wrong) must differ in outline, not
  only color.

## Summary by priority

- **P1 (built-in games):** 5x5 `SHAPE_TRIANGLE`, `SHAPE_HAND`, `SHAPE_SNOWFLAKE`; 16x16 `circle`,
  `triangle`, `square`, `check`, `cross`.
- **P2 (cooking parity, backlog):** 16x16 `tomato`, `cheese`, `flour`, `egg`, `butter`, `sugar`,
  `fried_egg`, `pancakes`, `pasta`, `cupcake`, `flame`, `chest`, `spin`/`spiral`, `question`,
  `hourglass`, four arrows, `tamal`, `pie`, `masa`/`corn`, `rice`.
- **P3:** everything else above.
