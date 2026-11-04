# CrowPanel 5" teacher tool: plan to match the design

Plan only. No code has been changed.

- **Design:** canvas "CrowPanel Teacher Tool", version `1793722623-32d5`, read fresh on 2026-11-03.
- **Code:** this folder at commit `fc125ba` on branch `Chat_to_Tap_Doggle`.
- **Docs read:** `AGENTS.md`, `HARDWARE_PROTOCOL.md`, and the front matter of
  `known_issues/2026-10-28-crowpanel5-display.md`. That note covers touch-bus and RGB stability, so
  none of its items block anything here. No other markdown was used, and code comments were not
  trusted as descriptions.

**Page names.** The canvas names the expansion pages differently from the brief:

| Brief | Canvas |
|---|---|
| NFC Screen Expansion | NFC Sub-Screens |
| Send Code Expansion | Send Code Sub-Screens |
| Connected Mode Expansion | Connected Mode Sub-Screens |

**Source tags.** Every item below says where it comes from:

- **[B]** a Main Screens Design board.
- **[X]** an expansion board. Where it shows a different state of the same screen, it wins over [B].
- **[N]** a review sticky note on the canvas whose change is **not yet drawn on any board**. The main
  boards still show text these notes say to remove: "12 wands · 2 stations", "11 ready", "See list
  →", "needs its code first", "All 14", the About block, `treasure:clue1`, and the dot legend.
  The [N] items are collected in D1, so they can be accepted or rejected together. They are not
  planned as changes otherwise.

**How behaviour and design are split.**

- *Design* covers layout, chrome, copy, colour, icons, and moving between screens or actions the
  code already has.
- *Behaviour* covers radio, NFC, the host protocol, and any new action, data source or saved state.
  A behaviour difference goes to "Needs a decision" (section 4).

---

## 1. Board → code map

Statuses: **Implemented** (layout and states are there; only visual or copy changes are needed),
**Partial** (the screen exists but states or parts are missing), **Missing** (nothing in the code).

| Board | Code | Status |
|---|---|---|
| 1 · Main (home) | `home.py` | Partial: no radar button, no Find button, footer battery never set |
| 2 · Recipients | `scr_recipients.py` | Partial: layout differs, pager instead of board chrome |
| 3 · Games (sheet) | `scr_games.py` | Partial: no "All" tab; tiles and footer laid out differently |
| 4 · SendCode | `scr_send.py`, `panel.send_code` | Partial: see 4.1–4.6 below |
| 4.1 Sending | `scr_send.refresh` | Implemented, but the layout differs |
| 4.2 Paused | `panel.pause`, `scr_send.py:66-67` | Partial: only the button label changes |
| 4.3 Partial (one no answer) | `scr_send.py:69,73` | Partial: Retry is per row, not one footer button |
| 4.4 Refused (update / battery) | none | Missing: `Panel.emit` drops `why` |
| 4.5 All done | `scr_send.py:73` | Implemented, but the layout differs |
| 4.6 Stopped | `scr_send._stop`, `:82-83` | Partial: no "Back to chat" or "Send to the other N" |
| 5 · Cards | `scr_cards.py` | Partial: one screen with tabs, see 5.x below |
| Tags Home | none | Missing |
| 5.7 Pick a game | `scr_cards.py:39-45` (`<` `>` pager) | Partial: a pager, not a list with Open |
| 5.1 Games ready | `scr_cards._arm` | Implemented, but the layout differs |
| 5.2 Writing | `scr_cards._result("busy")` | Implemented, but the layout differs |
| 5.3 Written, next | `scr_cards._result` + `_hold` | Implemented, but the layout differs |
| 5.4 Write failed | `scr_cards._result("failed")` | Partial: no cross icon, no error colour on the edge bars or list |
| 5.5 Rewrite one tag | none | Missing: rows cannot be tapped |
| 5.6 Whole set written | `scr_cards._arm` (`All done`) | Partial: no "Write another set" |
| 5.8 Write · type it | `kbd.py` (separate screen) | Partial: keyboard on its own screen with a different layout |
| 5.9 Write · tap a tag | `scr_cards` tab `own` | Partial: no Write History list |
| 5.10 Write · writing | same | Implemented, but the layout differs |
| 5.11 Write · another? | none | Missing: no "Same again" / "New text" |
| 5.12 Read · waiting | `scr_cards` tab `read` | Implemented, but the layout differs |
| 5.13 Read · result | `scr_cards._result("read")` | Partial: text only in the status line |
| 5.14 Read · blank | `scr_cards._result("empty")` | Partial: shown as an error, not as read |
| NFC no-reader state | `scr_cards.py:237-241`, `nfc_target.state("error","No reader")` | **No board exists** (D11) |
| 6 · Device | `scr_device.py` | Partial: layout differs, no reply bubbles, no aside |
| 7 · LinkPrompt / 7.1 Waiting | `scr_link_prompt.py` | Implemented, but the layout differs and there is an extra "Just charge" button |
| 7.2 Connecting | none | Missing: 7.1 and 7.2 are not told apart |
| 7.3 Update needed | none | Missing: no version check |
| 8 · Linked / 8.2 Sending | `scr_linked.py` | Implemented, but the layout differs |
| 8.1 Idle | `scr_linked._status` "Waiting" | Implemented, but the layout differs |
| 8.3 Playing | `scr_linked._status` "Playing" | Implemented, but the layout differs |
| 8.4 Stopped | `scr_linked._stop_all` | Implemented, but the layout differs |
| 8.5 Disconnected | none (`host.check` → `drop()` → home + toast) | Missing |
| 9 · LinkedCard / 9.1 Ready | `scr_linked_card.py`, `host.card_write` | Implemented, but the layout differs |
| 9.2 Writing | `host.card_result("busy")` | Implemented, but the layout differs |
| 9.3 Written · next | `host.card_done` → `shown` | Partial: shows Done; it doesn't know the next tag |
| 9.4 Write failed | `host.card_result` (error) | Partial: no cross icon or red bars |
| 9.5 Cancelled | `host.card_cancel` → `card_done` → `scr_linked` | **Already matches** the canvas note "Remove 9.5 … go straight back to 8.1, radio back on" |
| 9.6 Set done | none | Missing: the panel doesn't know the set |
| NfcTarget (shared) | `nfc_target.py` | Partial: different border, background, icon sizes and captions |
| LinkFlow / SendFlow (logic boards) | — | Reference only. They list the substates covered above. |

---

## 2. Foundations (do these first; every screen depends on them)

### 2.1 Fonts (blocked on D2)

**What the code has:** `lv.font_montserrat_12/14/16` only (`ui_kit.py:16-18`).

**What the boards use:** Nunito at 11, 12, 13, 14, 15, 16, 18, 20, 28, 30 and 32 px, and 60 px on
5.13. They use weights 400, 700, 800 and 900, and need these non-ASCII glyphs: `·`, `…`, `→`, `✓`,
`✕`, `⇧`, `⌫`. The current copy substitutes ASCII (`" - "`, `"..."`, `">"`) because Montserrat as
built has no such glyphs.

**Proposed minimum set** (the memory carve-out lets us collapse sizes):

- Nunito ExtraBold (800): 12, 14, 16, 18, 20.
- Nunito Black (900): 32. Use it for the 28, 30 and 32 px titles, and cap 5.13 at 32 px on two lines.
- Nunito Regular: 14, also used for the 15 px body text.
- Map 11 → 12, 13 → 14 and 15 → 14 or 16.
- Use ASCII plus the seven glyphs only.

At 4 bpp this is roughly 150 KB in total (est.), with the 32 px font roughly 50 KB of it (est.).

**Constraint:** `firmware/backup_2026-11-02/lvgl_micropy_CROWPANEL_S3_5-4.bin` is a merged image
(bootloader at 0, partition table at 0x8000). Its partition table gives `factory` 0x2C4000 bytes
(about 2.77 MB) at 0x10000 and `vfs` 0x12C000 bytes (about 1.17 MB) at 0x2D4000. The app in that
image fills `factory` to within about 2 KB, so compiled-in fonts do **not** fit without
repartitioning. The 8 MB PSRAM is available. This is the backed-up build; check the partition table
of the build actually flashed before deciding D2.

**Until D2 is settled,** keep the ASCII substitutes. Every `·` and `…` below is written as the board
writes it.

### 2.2 Colour tokens (`ds_tokens.py`)

These are in the boards but not in the tokens:

| Value | Used for |
|---|---|
| `#E0B445` | warn dot and bar: paused bar, refused rows, refused card border |
| `#C2B8D6` | "Waiting" dot, grey stopped bar, Linked "Skipped" dot |
| `#B9B4C6` | idle target foreground |
| `#FAFAFD` | not-heard tile background |
| `#FDECEB` | error track on 9.4 (`DANGER[1]` is `#FDECEA`; same thing, keep one) |
| `#F4F2FA` | segmented-control track; already `ui_kit.GREY` |

`MUTED_2` (`#A8A4B5`) is used for the wait dot in `scr_linked.py:17`. The boards use `#C2B8D6`.

### 2.3 Icons (blocked on exports; see section 5)

**New exports needed,** in the export style (white on alpha), converted by `make_icons.py` into
`icons/*.a8`:

- `radio_on_20` and `radio_off_20` (the radio with a slash: "Radio paused")
- `battery_24` (outline only; draw the fill level as a box inside if D3 gives a live level)
- `cross_56` (error target)
- `gamepad_88`, `pencil_88` and `nfc_waves_88` (Tags Home tiles)

**Files present but used wrongly or not at all:**

- `nfc_waves_56`: the board target uses 56. The code uses `nfc_waves_64` (`nfc_target.py:27`).
- `station_face_20`: for station avatars.
- `find_18`: also used on the Device aside button.

### 2.4 `ui_kit.py` components

- **`header()`** (`ui_kit.py:286-296`):
  - Add an optional subtitle: title 18/800 and sub 12/700, as on Recipients, SendFlow and Device.
  - Allow widgets on the right of the header.
  - The board back button is 44×44. The code's is 52 wide (`:292`).
- **Segmented control (new):**
  - Track `#F4F2FA`, radius 20, padding 4.
  - Items 40 px high, radius 16, 13 px text.
  - Active item: white background with `PINK_DARK` text. Inactive: transparent with `INK_3` text.
  - Used by Recipients, Games and the NFC screens. It replaces the pink-bordered outline tab
    buttons in `scr_recipients.py:83-87`, `scr_games.py:30-34` and `scr_cards.py:34-38`.
- **Primary button variants.** `button(primary=True)` is pink only (`ui_kit.py:180-182`). Add:
  - teal: Done, Find it again
  - purple: "Send to the other N", 7.3 "Try again", the keyboard's return key
  - The disabled grey `#D8D4E6` with white label already exists (`:188`). The boards show a disabled
    primary as grey fill with a **white** label. `set_enabled` sets `MUTED` (`:277`), so change it
    to white for primary buttons.
- **Edge bars (new, shared).**
  - 10 px wide. The left bar runs the full height (y 0–480) and fills from the bottom; the bottom
    bar runs the full width.
  - Each state sets a fill colour, a track colour and a value:

    | State | Fill | Track | Value |
    |---|---|---|---|
    | ready | — | none | 0 |
    | writing | purple | `PURPLE_50` | 60 |
    | done | teal | none | 100 |
    | error | red | none (5.4) / `#FDECEB` (9.4) | 40 |

  - This replaces the 6 px boxes from y=64 in `scr_cards.py:63-64,158-160`, and the bars from y=56
    in `scr_linked_card.py:45-49`.
  - The write is not instant, but `card_writer.write_text` blocks (`panel.py:485`), so the bar
    value stays fixed, as it does now.
- **Status icons (new).** A right-aligned group of the radio icon and battery icon for the 40 px
  footers of screens 8 and 9 [X]. Its battery part depends on D3.

### 2.5 `nfc_target.py`, to match the `NfcTarget` board

- **Box** (`nfc_target.py:26`): 240×180 at (528,150) is correct. Change it to radius 16 and a 2 px
  border. The code has a white fill, radius 20 and a 4 px purple border.
- **Background and colours per state.** Today only the border changes colour (`:13,40`).

  | State | Border | Background | Foreground | Icon | Caption |
  |---|---|---|---|---|---|
  | waiting | dashed `PINK` | `PINK_50` | `PINK_DARK` | waves 56 | Tap tag here |
  | writing | `PURPLE` | `PURPLE_50` | `PURPLE` | waves 56 | Writing… |
  | done | `TEAL` | `TEAL_50` | `TEAL_DARK` | tick 56 | Done |
  | error | `DANGER` | `#FDECEB` | `DANGER` | **cross 56** | Try again |
  | idle | dashed `BORDER` | `BG` | `#B9B4C6` | waves 56 | Not in use |
  | read-waiting (5.12) | dashed `PURPLE` | `PURPLE_50` | `PURPLE` | waves 56 | Tap tag to read |
  | read (5.13 / 5.14) | `TEAL` | `TEAL_50` | `TEAL_DARK` | tick 56 | Read |

  The code's captions (`:14`) are "Tap a tag here" and an empty error caption. Change them to the
  table.
- **Layout:** icon and caption are centred as one group with an 8 px gap. The caption is 15/800 in
  the foreground colour. The code puts the icon at y−20 and the caption at the bottom in `INK_3`.
- **Dashed border:** see the carve-outs in 2.6.

### 2.6 Deliberate departures from the boards (performance and memory carve-out)

The RGB-bus patches in `firmware/` show that full-screen redraw cost is already a concern on this
panel.

- **No box shadows** on primary buttons or the games sheet. LVGL shadows are drawn in software on
  every redraw.
- **135° gradients become horizontal,** as `ui_kit.grad` already does.
- **Asymmetric bubble corners** (`14 14 14 3`) become a uniform radius 14. LVGL has one radius per
  object.
- **1.5 px borders become 2 px,** as now.
- **Dashed borders** (target waiting and idle, home "New group"). An LVGL obj has no dashed border.
  Draw four `lv.line` segments with `line_dash_width` / `line_dash_gap` if this build supports
  them. Otherwise use a solid border in the same colour.
- **Signal bars** `▂▄▆█` (Recipients meta) are drawn as four small boxes of rising height, not as
  font glyphs.
- **The 60 px title on 5.13 is capped at 32 px** (2.1).
- **Drop `set_style_opa(150)`** on not-heard tiles (`scr_recipients.py:137`). The board uses a
  `#FAFAFD` background instead, and object opacity forces layer rendering.

---

## 3. Per-screen changes (design wins)

### 3.1 Screen 1 · Main (`home.py`, `panel.py`)

**Sidebar**

- **"Playground" title:** 18/900 at (16, 14). The code has F16 at y=24 (`home.py:50`).
- **Radar "Look for devices" button:** 44×44 at the right of the sidebar header [B]. It is not in
  the code. What it does is **D6**.
- **Chat-row subtitle:** use `" · "`, as in "12 wands · 2 stations" (`panel.py:247`).
- **Avatar per kind** (`home.py:27-29` uses `PURPLE` glyph text for every kind):

  | Kind | Background | Content |
  |---|---|---|
  | wand | `#F4F2FA` | hex tag, 12/800, `INK_3` |
  | group | `PURPLE_50` | letter, 15/900, `PURPLE` |
  | station | `TEAL_50` | `station_face_20` in `TEAL_DARK` |

  This needs `chat_rows` to pass the kind through, which it already has in `kind`/`macs`.
- **Device subtitle copy:** "Wand · battery low" in warn colour [B]. The code says "Battery low"
  (`panel.py:257`). Use the same "<Kind> · <state>" form for "not heard".
- **"New group":** dashed border (see 2.6) and 13/800 text. The code has a solid border
  (`home.py:53`).
- **Sidebar footer** (`home.py:60-68`) [B]:
  - A teal "ChatBroadcast linked" pill with `plug_14`.
  - A row with "Radio on" on the left and "Panel 82%" on the right, at 11/700.
  - The battery label is created but never set (`home.py:68`), which is D3.
  - The pill is shown only while `host.linked` (`home.py:276`). But a link also moves the screen
    to `scr_linked` (`host.py:78`), so the pill is almost never visible. See D15.

**Header**

- **Title:** 18/800. **Subtitle:** 12/700 "14 answered · 2 min ago" [B]. The code says
  "N of M answered - X min ago" (`panel.py:221`). Change the format to `f"{n} answered · {ago}"`.
- **Buttons, left to right:** Roll call (teal), **Find** (`INK_3`, `find_18`), NFC Tags (purple,
  `cards_18`). Each is 44 px with 14/800 text. Find is missing (`home.py:77-84`), which is **D6**.

**Chat area**

- **Roll-call bubble:**
  - Title 14/800, as now (`home.py:219-220`). Chips as now (`:115-117`).
  - "See list →" is a 12/700 purple **text link** on the board. The code has a 44 px outline
    button (`home.py:118`). Restyle it as text, keeping a 44 px touch area around it.
  - [N] Making the whole bubble the tap target (and dropping the link) is a review note: D1.
- **Sent bubble:**
  - Game tile 28 px radius 8 with an icon, and 15/800 text, as now (`home.py:135-139`).
  - Subtitle "Playing on 11 of 12 · 5 min ago", teal, 11/700 [B].
  - The code freezes the subtitle at creation as "on N of M - just now" (`panel.py:311-314`), so it
    never ages. Store `ok` and `total` in the log entry and build the text in `_fill`, with the age
    taken from `entry["ts"]`.
  - When the game was broadcast to Everyone there is no count. See **D7**.
- **Error bubble:** background `#FDECEA`, the name in bold (needs D2), and a "Try again" button
  36 px, radius 12, 13/800 red. The code matches this apart from font sizes (`home.py:143-151`).
- **Empty-state text** (`home.py:176`): not on the board. Keep it; no board covers the empty state.

**Footer** (`home.py:179-190`): matches the board. Only the fonts change: 16/800 and 15/800.

### 3.2 Screen 2 · Recipients (`scr_recipients.py`)

**Header** [B]

- Back button, "Who gets it?" 18/800, and the subtitle **"Hold one to make it blink"**. The code
  has no subtitle.
- **Segmented control** "All 14 / Wands / Stations" in the header. The code puts outline buttons
  at y=72 (`:81-87`).
- **Roll call button** (teal, 44 px) at the right of the header. The code puts it in the footer
  (`:97-98`).

**Grid**

- 4 columns, tiles 72 px high with a 10 px gap, starting at y=78, about 184 px wide. The code uses
  182×88 starting at y=120 (`:12-22`). There are three rows of 12 tiles, which is the same count
  as now.

**Tile** [B]

- Avatar on the left: a 40 px circle with the hex tag in 11/900. Stations show "STN" on
  `TEAL_50` / `TEAL_DARK`.
- Name 14/800.
- **One meta line** at 11/700: "90% · " followed by the signal bars.
  - Low battery: "Battery low · bars", in warn colour.
  - Station: "Station · bars".
  - Not heard: "Not heard · 6 min" in red, with the tile background `#FAFAFD`.
- The code has a name, a tag pill at the top right, a battery line and a signal-word line
  (`:23-28, 129-137`).
- Picked tiles: pink border and `PINK_50` background, as now.

**Footer** (74 px) [B]

- "4 picked" 15/800, "Save group" (outline, 52), and "**Chat with 4 →**" (primary, 52).
- The code footer is at y=416 with 48 px buttons and a Roll call button (`:96-108`).

**Remove** "N picked - page x/y" and the `<` `>` pager (`:88-92`). How to show more than 12 devices
is **D8**.

**Group mode** (title "New group", primary "Save group"): no board covers it. Keep the code
(`:146-151`).

### 3.3 Screen 3 · Games sheet (`scr_games.py`)

**Overlay and sheet**

- Overlay `INK` at 35%: opacity about 89. The code uses 120 (`:22`).
- Sheet at y=60, 420 high, radius 20. The code uses y=96 and radius 24 (`:10,24`). Make it 440 high
  so the bottom corners sit below the screen.

**Header row** [B]

- "**Start a game**" 18/800. The code says "Pick a game" (`:26`).
- Subtitle "To: Everyone · 14 devices" (`:137-138`, using `·`).
- **Segmented control "On wands / New / All".** The code has "Ready / New" (`:30`).
  - "On wands" is the code's `ready` filter. Rename it.
  - "All" is a new filter that lists every game. It has no other effect. Add it in `_games()`
    (`:108-117`).
- "**Not yet**" button (44 px) in the header row. The code puts it in the footer (`:53`).

**Tiles**

- 4×2 grid, 128 px high, 12 px gap, 20 px side padding.
- A **40 px colour square** with radius 10 and no icon. The code has a 28 px swatch with a music
  icon (`:43-44`).
- Name 15/800, meta 11/700.
- Selected tile: pink border **and** `PINK_50` background **and** meta in `PINK_DARK`. The code
  only changes the border (`:156`).

**Meta copy** [B]

- "New · on 0 of 12". The code says "New" (`:128`).
- "On 9 of 12" in warn colour when partial. The code says "on n of m".
- "Playing now", as now.
- Built-in games: "On all 12" on the board versus "Built in" in the code (`:129`). That is **D9**.

**Footer**

- Message 14 px with the game name in bold.
- "**Send code**" (outline purple, 52) then "**Start →**" (primary, grey when disabled).
- The code order is Start, Send code, Not yet (`:51-53`). The enable logic is already correct
  (`:164-165`).

**Remove** the `<` `>` pager (`:35-38`). See **D8**.

### 3.4 Screen 4 · Sending code (`scr_send.py`): follow SendFlow [X]

**Header**

- Back button, the **target name** at 18/800, and the subtitle "12 wands · 2 stations".
- The code title is "Sending code - <game>" (`:60`).
- Remove "Radio busy - games paused" (`:20, 65`). It is on no board.

**Sent bubble**

- Right-aligned purple gradient bubble: `code_18` icon, "Send code: Treasure Hunt" 15/800, and
  "Just now" 11/700 at 80% opacity, inline.
- The code has a `PURPLE_50` box on the left (`:21-22, 61`).
- [N] would remove it (D1).

**Progress card**

- A left-aligned white bubble, 560 wide, radius 14, with a 2 px border. The border is `#E0B445`
  in the refused state.
- **Head row:** the status text at 15/800 in the state colour, plus a small **Pause / Resume**
  button (100×40) inside the card. The code puts Pause in the footer (`:36-37`).
- **Bar:** 10 px. Teal while sending, `#E0B445` when paused, `#C2B8D6` when stopped. The code has
  a 12 px teal bar only (`:24`).
- **Rows:** a 2-column grid of 6 rows × 22 px. Each row has a 10 px dot, the name at 13/800 and
  the state at 12/700, coloured. That is **12 rows**. The code shows 8 in one column on the right,
  each with its own Retry button (`:10, 26-34`).
- **Row states:**

  | State | Dot | Text colour |
  |---|---|---|
  | Has it | `TEAL` | `TEAL_DARK` |
  | Sending | `PINK` | `PINK_DARK` |
  | Waiting | `#C2B8D6` | `INK_3` |
  | No answer | red | red |
  | Not sent | `BORDER` | `INK_3` |

  The code's Sending row is purple (`:13`).
- Remove "Keep wands near the panel" (`:25`). SendFlow drops it, and the expansion wins over the
  main board.

**Footer** (74 px): button A is 170 wide (outline) and button B is 230 wide (primary).

| State | Head | Small button | A | B |
|---|---|---|---|---|
| sending | "7 of 12 wands have it" | Pause | Stop sending (red) | "Start <game> →", grey, disabled |
| paused | "Paused · 7 of 12 have it" (warn) | Resume | Stop sending | grey, disabled |
| partial | "11 of 12 wands have it" | hidden | "Retry <wand>" (red) | "Start anyway →", pink |
| refused | "10 of 12 wands have it", yellow border | hidden | see D10 | "Start anyway →", pink |
| all done | "All 12 wands have it" (teal) | hidden | hidden | "Start <game> →", pink |
| stopped | "Stopped · 7 of 12 have it" (red) | hidden | "Back to chat" | see D10 |

What the code does today for these states:

- Paused: rows still being sent should read "Waiting". Only the label changes today (`:67`).
- Partial: Retry is per row today (`:87`). With more than one failure, see **D10**.
- Stopped: the code keeps the Start button (`:40, 73`). "Back to chat" = `leave_send`, which
  already exists.
- Visibility already matches: the code hides Pause and Stop when nothing is busy (`:71-72`).

### 3.5 Screen 5 · NFC Tags (`scr_cards.py`, `kbd.py`): follow the NFC sub-screens [X]

These changes apply whatever D11 decides.

**Chrome**

- Header 64 px: back button, a title (Games / <game name> / Write a tag / Read a tag), and the
  segmented control **Games / Write / Read** in the header.
- The code has "NFC Tags" and the text "Radio paused while writing" in the header, and tabs
  "Game / My own / Read" at y=72 (`:30-38`).

**Left list** (Games and Write tabs)

- 290 wide at x=16, y=78.
- Heading 12/800: "Pick a Game", "Tags in this Game" or "Write History".
- Rows 42 px with a 6 px gap, radius 12.
- **22 px mark circle:** ✓ teal, → pink, **!** red on error, empty `BORDER` for to-do.
- Name 14/800. Right-hand meta 11 px (for example "7 tags").
- The code has 30 px rows, 480 wide, with the words "done", "now" and "todo" (`:46-50, 209-213`).
- It shows `label: text`, which means the **raw tag** (`:212`). The boards show the name only;
  naming is **D5**.
- The windowing that keeps the current row visible (`:202`) stays.

**Right panel**

- White box from x=320 to x=784, radius 16. It has 272 px of right padding so the text column
  clears the target.
- Contents:
  - kicker 12/800
  - title 20/900 (28 high)
  - hint 14 px (38 high, 2 lines)
  - a **Radio paused icon pill** (`radio_off_20` in `#A8781E` on `#FFF8E0`) at the bottom
- Remove the `prog` status line (`:53` and every `k.st(_w["prog"], …)`). The boards hide that
  slot; state is shown by the target, the edge bars and the list marks.
- The read text and reader errors that went to `prog` move to the title (5.13) or to D11
  (no reader).

**Footer** (74 px)

- Secondary button 150 wide (outline) and primary 170 wide, **teal**. The code's Done is pink
  (`:61`).
- Remove "Type text" (`:57`). Rename "Copy to tag" (`:59`) as below.

| State | Kicker | Title | Hint | Secondary | Primary |
|---|---|---|---|---|---|
| 5.7 pick a game | GAME | <game> | "All, Code, Play, then its N game tags" | hidden | Open |
| 5.1 ready | NOW WRITING | <tag> | "Hold until the beep" (D4) | Skip | Done |
| 5.2 writing | NOW WRITING | <tag> | "Hold still" | Skip | Done |
| 5.3 written | NOW WRITING | <tag> | "Next: <next tag>" | Skip | Done |
| 5.4 failed | NOW WRITING | <tag> | (as ready) | Skip | Done |
| 5.5 rewrite one | REWRITE ONE TAG | <tag> | — | Back to the set | Done |
| 5.6 set done | SET COMPLETE | "All N written" | — | **Write another set** (= `_load()`) | Done |
| 5.9 own ready | NOW WRITING | <text> | "Hold until the beep" | **Edit text** (= `_type`) | Done |
| 5.10 own writing | NOW WRITING | <text> | "Hold still" | Edit text | Done |
| 5.11 own done | DONE | <text> | "Write another tag with the same text?" | New text | Same again |
| 5.12 read waiting | READ | "Tap a tag" | — | hidden | Done |
| 5.13 read result | THIS TAG SAYS | <tag text>, 32 px, 2 lines | — | **Write it again** (= `_copy`) | Done |
| 5.14 read blank | THIS TAG SAYS | "Blank Tag" | — | **Write a tag** (Write tab + `_type`) | Done |

- 5.5 depends on **D11**. In 5.11, "New text" and "Same again" depend on **D11**.
- The code's hints today are "Hold a blank tag on the target" (`:219`) and "Writing... keep
  holding" (`:123`).
- **5.4 error:** list mark `!` in red on the current row, target error (cross), and red edge bars
  at 40%. The code resets the edges to 0 (`:126`) and has no cross icon.
- **5.14:** use the teal "Read" target state. The code shows a red "Empty tag" (`:134-136`). This
  only changes how the state looks.
- **Read layout:** no left list. The text box is 486 wide from x=16.

**5.8 keyboard look.** The board draws it inline; whether to do that is **D11**. Restyle the `kbd`
screen to match the board anyway:

- Input 52 px with a 2 px purple border, text 20/800.
- **Cancel** (150, outline) and **"Use this text"** (170, pink). The code has OK and Cancel stacked
  (`kbd.py:26-27`).
- Custom key map via `set_map`: Q–P / A–L / ⇧ Z–M ⌫ / 123, space (420), ., return (120, purple).
- Keys 20/800 on `#F4F2FA`, radius 10.
- Remove the byte counter (`kbd.py:25, 40-45`); the board has none. Text over the limit is still
  refused by the toast (`kbd.py:50-52`).

### 3.6 Screen 6 · Device (`scr_device.py`)

**Layout** [B]: a main column (552 wide) plus a right **aside** (248 wide, white, border on the
left).

**Main column**

- **Header:** back button, a 40 px avatar with the hex tag, the name 18/800, and the subtitle
  "Wand · heard 1 min ago" from `roster.age`, which exists. The code has a title, a tag pill and a
  **Rename** button (`:34-38`).
- **Chat log as bubbles:**
  - "Find it" in pink, sent by the teacher, with its age.
  - Replies as left bubbles.
  - The code prints flattened text lines (`:50-51, 64-72`).
  - Use a small bubble pool like home's `_slot`.
  - Find replies are **D13**.
- **Footer order:** Start game (primary 56), **Stop**, **Send code**. The code has Start, Send
  code, then Stop at the far right (`:55-57`).

**Aside**

- "ABOUT THIS WAND" (11/700 caps).
- **Nickname** field, 44 px. It looks like an input and opens `kbd` on tap, so it replaces the
  Rename button (true inline editing is **D13**).
- **Battery** tile (warn background when low) and **Signal** tile.
- "Last sent: <game>", from `P.playing`. The code currently shows "Last game".
- "Groups: <names>": derived from `store.groups` membership, for display only.
- "MAC …:7C:3F:2A": the last three bytes.
- A spacer, then **"Find it again"** (teal primary, 52, `find_18`). The code says "Find it" (`:46`).

The [N] note would remove most of the aside (D1).

### 3.7 Screen 7 · Connecting (`scr_link_prompt.py`): follow 7.1 [X]

- The tile and icon are correct: 220 at (56,130) with `computer_link_120` (`:13-14`).
- **Right column** at x=316, vertically centred:

  | Item | Size | y |
  |---|---|---|
  | kicker (empty) | 26 high | ≈119 |
  | title "Connecting" | 30/900 | ≈159 |
  | body | 15 px | ≈209 |
  | status: dot 10 + "Waiting…" | 13/700 | ≈269 |
  | button row | 52 | ≈309 |

- Remove the teal "Waiting..." kicker (`:16`). The board's kicker is empty.
- Title font: the code uses F16 (`:17`).
- **"Just charge"** (`:21-22`) is not on 7.1 or 7.2. Removing it is **D12**.

### 3.8 Screen 8 · Connected (`scr_linked.py`): follow 8.1–8.4 [X]

- **Stop all** (`:31`): visible while sending or playing (and on 8.5). Hidden on 8.1 idle and on
  8.4 stopped. The code shows it always.
- **Status card**
  - Position and size: x16, y70, width **504**, down to y=426. The code has width 340 (`:34`).
  - Content is vertically centred with 24 px padding:
    - "STATUS" 11/700
    - the status line at **32/900** (the code uses F16, `:36`)
    - a 12 px bar, **only while sending**
    - the sub line at 14/700, **only while sending** ("7 of 10 have it")
  - Drop "On N devices" (`:82`) and "Nothing running" (`:87`). The boards leave the sub line empty.
- **Devices aside**
  - x=530, w=250, **visible only while sending**. The code has x=372, w=412, always visible
    (`:40-55`).
  - "Devices" 15/800 and "14 heard" 12/700 ([N] removes these).
  - A 2-column grid with 9 px dots and names at 12/700 in 24 px rows (the code uses F14 in 38 px
    rows).
  - The legend at the bottom in 11 px.
  - Wait dot `#C2B8D6`.
  - `_dot`'s non-sending colours (`:62-64`) stop mattering once the aside is shown only while
    sending.
- **New footer:** 40 px, white, with a top border, and the radio and battery icons on the right.
- The "Sent <game>" state (`:85-86`) is on no board: **D12**.

### 3.9 Screen 9 · Connected tag (`scr_linked_card.py`): follow 9.1–9.4 [X]

- **Header:** "Radio paused" becomes an **icon-only** pill (`radio_off_20`, purple on `PURPLE_50`).
  The code uses a text pill (`:28`).
- **Body column** at x=40, width 440, vertically centred:

  | Item | Size | Code today |
  |---|---|---|
  | kicker | 13/700, "<game> · tag n of m" (D5) | "THE COMPUTER ASKS FOR A TAG" (`:30`) |
  | title | **32/900**, label only | "Tag: <label>" (`:31, 78`) |
  | hint | 15 px, "Hold until the beep" in ready, writing and error (D4) | long `_HINT` texts (`:17-19`) and the error message (`host.py:291`) |
  | raw tag chip | **hidden** | shown (`:33-34`) |
  | status slot | **hidden** | shown (`:35-38`) |

- **Footer:** 40 px with the **battery icon only**. Remove "Last tag: …" (`:42, 89-90`).
  `host.last_card` can then go.
- **Edge bars** per 2.4. They are full height from y=0; the code starts the left bar at y=56
  (`:45`). The error state is red at 40% on `#FDECEB`; the code shows purple at 0 (`:16`).
- **Target** per 2.5. The error caption is "Try again" with the cross icon. The code passes an
  empty string (`:91`).

---

## 4. Needs a decision

Each item gives a recommendation; nothing is planned until it is decided.

**D1. Review notes not yet drawn on boards [N].** Accept them in bulk, item by item, or wait until
they are on the boards?

<details><summary>The notes</summary>

- **Main**
  - Sidebar footer becomes connection and battery icons, with no "ChatBroadcast".
  - "14 answered" only, and bubble times become "# ago".
  - Drop "12 wands · 2 stations".
  - The roll-call bubble opens the list, with no "See list →".
  - Drop the "11 ready" chip; show issues and special counts only.
- **Recipients**
  - A battery icon before %.
  - "Not heard" becomes "Last heard".
  - A find icon on each tile, replacing the subtitle (see D14).
  - "All", not "All 14".
  - Remove "4 picked".
- **Games**
  - Tapping a game starts it and auto-sends code, which drops "needs its code first", the grey
    Start and Send code.
  - Drop "· 14 devices".
  - Show the "On all" meta only when some devices lack the game.
  - "Not yet" becomes ✕.
- **SendCode / SendFlow**
  - Drop the sent bubble.
  - Auto-start after loading, or show Start only when some wands already had it.
  - 4.4: drop "Show the 2 wands".
- **Cards / NfcFlow**
  - "Radio paused" becomes an icon (already done on the expansion boards).
  - Remove "3 of 7".
  - Headings become "NFC TAGS".
  - "NOW WRITING" becomes "WRITING".
  - Drop "SET COMPLETE".
  - Drop "THIS TAG SAYS".
- **Device**
  - "heard 1 min ago" stays.
  - Remove MAC, Last sent, the battery and signal tiles, and Groups.
  - Battery and signal appear only as replies.
  - Add a **"Status Check"** ping button (a new action).
- **Linked**
  - Remove "14 heard" and the legend.
  - Footer becomes icons (already done on the expansion boards).
  - 8.5 can't know "Playing <game>", so remove it.
  - 9.x: remove "Last tag ✓/✗".
- **NfcTarget**
  - Consider the icon only while writing.

</details>

*Recommendation:* take the copy-only removals now. Treat Games auto-start, SendFlow auto-start and
Status Check as behaviour (D9–D13).

**D2. Font route.** Choose one:

- (a) Compile Nunito subsets into the firmware. No heap cost, but a firmware rebuild **and a new
  partition table**: the backed-up image leaves about 2 KB free in `factory` (2.1), so the app
  partition must grow by about 150 KB (est.) at the expense of `vfs`.
- (b) Load `.bin` fonts with `lv.binfont_create` from `vfs` after radio bring-up. No rebuild, but
  about 150 KB (est.) of `vfs` space and of heap, ideally PSRAM. Loading after bring-up is what
  AGENTS.md's memory rule allows; it must not move into any module imported before the radio.

To check on the device: whether this build includes binfont, the flashed partition table, and
free `vfs` space. *Recommendation:* (b), because (a) needs a repartition and a reflash that wipes
`vfs`; fall back to (a) if binfont is not built in.

**D3. Panel battery source.**

- Facts: there is no battery reading in `board.py`, and `home.py:68` is never set. The boards show
  "Panel 82%" (home) and a battery icon (screens 8 and 9).
- Options: wire an ADC or charger pin if the hardware has one, or leave the battery out.
- *Recommendation:* leave it out until the hardware is confirmed.

**D4. "Hold until the beep."**

- Facts: nothing on the panel beeps. `board.py:38-40` defines I2S pins, but no code uses them. The
  canvas note says sounds are still to do.
- Options: keep the board copy and add sounds, or say "Hold until Done" until sounds exist.

**D5. Tag names, the "All" card, and "<game> · tag n of m".**

- Facts:
  - `.tags.json` holds raw strings (`library.py:42-48`). `lib.cards()` returns Code, Play and the
    raw tags, with no "All" card (`library.py:135-147`).
  - ChatBroadcast sends `card.write` with `label: tag`, the raw tag (`ChatBroadcast/js/app.js:1026`),
    and no game, index or total.
- Options:
  - A local display rule. For example, `treasure:clue1` → "Clue 1", `getcode:x` → "Code", `x` →
    "Play", `all` → "All".
  - Names supplied in `tags.json` and the host command (this changes another tree).
- An "All" card writes a new tag, `all`, so it is behaviour. The game counter on 9.x also needs
  host fields.
- *Recommendation:* a local display rule now; protocol fields as a separate ChatBroadcast change.

**D6. Home "Look for devices" (radar) and header "Find".** No action is defined.

- Radar could run a roll call (which is already a header button) or open Recipients.
- Find with a group or Everyone target is undefined; the code only finds one MAC.

**D7. "Playing on N of M" for Everyone.** The code **broadcasts** to Everyone with no acks
(`panel.py:290-294`), so it can't count. Options:

- unicast to Everyone (slower, but it gives counts)
- show "Sent to everyone · <age>"

**D8. More items than one screen holds.** Recipients holds 12 tiles, Games 8, Send rows 12, and
Linked devices 14. The boards have no pager. Options:

- LVGL scrolling (more objects or redraw cost)
- keep a small pager in a spot the board leaves free

**D9. Built-in games meta.** The board shows "On all 12". The code says "Built in" (`scr_games.py:129`)
because it can't tell whether wands have built-ins.

**D10. Send.**

- **Refused reasons.** `Panel.emit` drops `why`, and wands report none for battery or version.
  "Needs update" and "Battery low" rows need a reason from the wands.
- **More than one failure.** The board names one wand ("Retry W-09C1"). Options: "Retry N wands",
  or keep per-row retry.
- **"Send to the other N" after Stop.** This is a new action (re-distribute to the not-sent
  wands).
- **Auto-start after loading** ([N]).

**D11. NFC.**

- **Tags Home.** Should there be a hub before the modes? Should the radio go off on the hub or
  only on entering a mode? Today it goes off when `scr_cards` opens (`:237`).
- **Game picker.** Use a list with Open instead of the pager. Should it include built-ins and a
  "Utility" set?
- **Rewrite one tag** (5.5): tapping a done row rewrites it.
- **Write History** (5.9–5.11): needs saved state; nothing like it exists now.
- **5.11 "Same again" / "New text"** after writing your own text.
- **Inline keyboard (5.8) or the `kbd` screen.** In the code `kbd` is its own screen
  (`kbd.py:16`, `k.new_screen()`). My judgement, not measured: a separate screen keeps typing from
  redrawing the NFC screen behind it, which may matter given the redraw cost in 2.6.
- **No-reader and reader-error state.** No board covers it. The code shows a red target "No
  reader" and the error text (`scr_cards.py:237-241`).

**D12. Connected mode.**

- **Remove "Just charge"** (which sends `released`, `host.py:98-101`)? Without it, the only way to
  return is the computer's unlink or the 15 s timeout.
- **7.1 Waiting or 7.2 Connecting:** which event switches between them? Today screen 7 appears on
  the first passive command (`host.py:51-55`).
- **7.3 "Update needed" and Try again:** no version check exists.
- **8.5 Disconnected:** today the timeout returns home with a toast (`host.py:90-96`).
- **The state after a send finishes** (the code shows "Sent <game>", `scr_linked.py:85-86`): use
  8.1 Waiting or 8.3 Playing?
- **9.3 "Written · next tag"** and **9.6 "All N written":** both need the set from the host (D5).
  Today a written tag shows Done until the next command (`host.py:313-317`).

**D13. Device.**

- **Find replies** ("Blinking and buzzing", "Battery 18% · charge soon"). Today `fleet.find` only
  repeats the command and handles no reply.
- **True inline nickname editing** versus a field that opens `kbd`.
- **[N] Status Check ping.**

**D14. Recipients find.** Keep long-press to find (the board's subtitle describes it) or use the
[N] find icon on each tile.

**D15. Home connection pill.** While linked, the panel sits on screen 8, so the pill on home almost
never shows. Should the home footer show the connection at all?

---

## 5. Blocked on assets

- **Fonts** (D2): Nunito subsets per 2.1.
- **Icons** (2.3): `radio_on_20`, `radio_off_20`, `battery_24`, `cross_56`, `gamepad_88`,
  `pencil_88`, `nfc_waves_88`. They need exports on the canvas, then `make_icons.py`.

## 6. No change needed

- **9.5 Cancelled:** the code already returns to screen 8 with the radio on.
- **The NFC target position** (528,150, 240×180) and the fixed slots on every card screen.
- **Home footer actions,** Roll call, and Try again on the error bubble.
- **Screen-8 header** colour, icon and title.
- **The 7 · Connecting tile** and icon.

## 7. Out of scope

- The "(old) Resized Design" page (`P2*` boards) and its notes.
- The page-2 rows in `project/exports/icons/README.md`.
- Behaviour of the radio, fleet, code serving and the card writer, except where a D item asks.
- `REVIEW_2026-10-30.md` and the other markdown in this folder (not read).

## 8. Suggested order

1. Settle D2 and D3. Export the icons.
2. Tokens (2.2), `ui_kit` components (2.4), `nfc_target` (2.5).
3. Screens in order of use: 1 → 2 → 3 → 4 → 5 → 6, then 7 → 8 → 9.
4. Then D items, as they are decided.

**Checks after each step**

- `python -m py_compile` on each changed file. That is the only off-device check (`AGENTS.md`).
- On the device, follow `HARDWARE_PROTOCOL.md`:
  - Ask which port is the panel.
  - Copy with one batched `mpremote … resume` call, then a plain `reset`.
  - Get the user's eyes on each screen.
- `shot.py` / `shot_host.py` may help capture screens for comparison.
