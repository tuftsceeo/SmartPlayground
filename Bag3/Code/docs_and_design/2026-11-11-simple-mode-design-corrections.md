# Simple mode design: corrections and how the design responds

These are design review notes for the ChatBroadcast simple mode ("Wand & Station Coder"). The audience is kindergarten teachers using a smart board. The design canvas is at https://claude.ai/artifact/WjCoDBJYxUKwinww3s8y2E.

## Standing principles

These came out of the corrections and apply across all screens.

- **Minimal text.** Leave out labels, counts or notes that are obvious from context or repeat what the screen already shows.
- **US spelling.** Write "color".
- **Vocabulary.** Say "NFC tags", "teacher hub", "icon display" and "Find Me". Avoid technical words such as "Flash".
- **Icons.** Use only real design-system icons, or no icon. Never use made-up drawings.
- **No big cards.** Cards make the screen look busy.
- **UI conventions.** Put secondary actions such as Refresh and Close as icon buttons at the top right.

## Icons

| Correction | How the design responds |
|---|---|
| Draw a Splat icon based strictly on the simulator drawing. | Built from the simulator's case and blob paths (`Simulator/js/panels/splats.js`). |
| Match the Splat's line weight to the other icons. | The stroke now scales with the icon instead of using a non-scaling stroke, so it matches the others. |
| Remove the three little dots in the center. | The LED dots are removed. |
| Fix the reversed icons (white on color). | Reversed icons now sit on darker, larger tiles with a heavier 1.6 stroke, for better contrast. |
| Add reversed filled icons. | Filled and reversed-filled variants added for all six icons. |
| Store them on an artboard and in the design system. | Added an Icons artboard. The design system's Icons group now holds 12 SVGs: 6 outline and 6 filled. |
| "What is this icon?" / "and this one?" | The made-up plug and device drawings were replaced with real icons (the teacher hub icon, plus dots). |

## Chat

| Correction | How the design responds |
|---|---|
| Don't label user messages "You asked"; follow the messaging-app pattern. | The label is removed. User messages are unlabeled bubbles on the right. Coder replies get a round sparkle avatar in the home icon gradient. |
| Bubbles should be more bubble-shaped. | Rounder corners (26–28px), with one tight tail corner pointing to the speaker. |
| Bubbles should be indented. | User bubbles are inset 56px from the left, and replies 56px from the right. |

## Opening the app

| Correction | How the design responds |
|---|---|
| Warn browsers without Web Serial when the app opens, before the magic code prompt. | New board "0 · Opening the app": an amber note above the magic code reads "This browser can't send games to wands. Use Chrome or Edge on a computer. You can still make and try games here." |

## Sending a game

| Correction | How the design responds |
|---|---|
| "Obviously it is connected... remove." | Removed the "Connected" banner from Send to device. |
| Only show the wand count when it means something. | No wand pill for 1 or 1+ wands (there is always at least one); show it for 2 or more. |
| Hide pills with a count of zero. | Icon display, NFC tag and Splat pills appear only when the game needs at least 1. The NFC tag count includes in-game tags only, not the code-pull or start-game tags. The agent supplies the minimum needed for a playable game. |
| "This should be a question." | The heading reads "Send it to the wands now?" |
| "Just say reconnecting." | The subtitle reads "Reconnecting…" (devices don't always restart). |

## Sharing to wands

| Correction | How the design responds |
|---|---|
| No count in the subtitle; it's redundant. | The subtitle reads "Tap a wand to choose it." |
| Wands can be 50+ feet away. | Removed "Keep the wands close…". |
| A dead battery wouldn't make the list. | Removed the battery notice. |
| Not "Empty". | The battery label reads "Critical". |
| "Flash" sounds technical. | The button reads "Find Me". |
| Refresh goes top right, as an icon. | Added a Refresh icon button next to Close, and removed the bottom button row. |
| Teachers can count. | Removed "1 of 2 wands ready". |
| The button text is too long. | The button reads "Sending…", gray and disabled until done, then becomes an active button. |

## Saved games

| Correction | How the design responds |
|---|---|
| Thumbnails should be 5×5 and come from each game's `GAME_ICON`. | Thumbnails are now 5×5 grids made from real wand `SHAPE_*` glyphs and LED colors. In the app, each card reads the game's stored icon. |

## Playing with several devices

| Correction | How the design responds |
|---|---|
| Hide the add options when the device count is known. | New board for a fixed 2-wand game, with no "Add a wand" or "Add an icon display". |
| Show add options only for open-ended games (no upper limit on wands). | The add tiles appear only on the open-ended board. |
| Start the known number of wands by default. | Fixed games open with every wand started: 2, 3 or 4. |
| Always open with the minimum. | Open-ended games open with only the minimum started, and you add more with "Add a wand". The not-started Player 2 panel is gone. |
| Tic Tac Toe always has 2 wands. | The open-ended example is now a 1+ wand game, "Color Hunt". On the Tic Tac Toe game screen, I removed the "1 wand / 2 wands" toggle and "Play more wands". |
| Remove the turn banner. | Removed. |
| Add a way to minimize devices. | Each wand and icon display has a "–" minimize button. |
| Show a 4-wand game with 3 minimized. | New board: Pass the Star, with Player 1 expanded and Players 2–4 minimized. |
| Minimized means the wand illustration only. | Minimized wands show only the wand drawing, a name and an expand button, with no controls. |
| No big cards. | Removed card borders and backgrounds from the multi-device boards. |
| "color, not british." | Fixed on the Mastermind and New game boards. |

## Splats

| Correction | How the design responds |
|---|---|
| Show Splats in this space, not paired to particular wands. | New "Wands and Splats" board. The Splats are one shared group with no link to a particular wand. The leftover X/O buttons are removed. |
| The 15 LEDs light the whole gray area; don't draw individual LEDs. | The lit area is a filled shape: gray when off, colored when lit. There are no dots or shadows. |
| Splats can fill inside vs outside, or left vs right; each part can have its own color or be off. | All four Splats show these modes: red outside with a yellow center; green with the center off; blue left with purple right; yellow left with the right off. |
| Gradients go between the two colors, not to white or gray within a section. | Each section is a solid color. The gradient only blends where two sections meet, or into gray when one section is off. |

## Still open

- **Mastermind:** this board still shows a "1 wand / 2 wands" toggle. That fits only if Mastermind is a 1+ wand game. If it always needs 2 wands, remove the toggle.
- **Placeholder games:** the mock games don't have stored `GAME_ICON` values, so I picked plausible icons for their thumbnails.
