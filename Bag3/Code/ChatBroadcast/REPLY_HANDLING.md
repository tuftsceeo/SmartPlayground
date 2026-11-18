# How ChatBroadcast reads a chat reply

The model replies in plain text: Markdown prose, fenced code blocks and marker lines. The rules it
follows are in `knowledge/policy.md` (reply layout) and `knowledge/platform.md` (markers). The app
reads the reply with the parsers in `js/chat.js`; `callClaude()` in `js/app.js` acts on them.

## Reply layout (game replies)

1. One short bold line with the big idea.
2. The code block or blocks, each after a `[DEVICE: <role>]` line.
3. `### How to play`: 3 to 6 numbered, action-first phrases a teacher reads aloud
   ("Players push the button.", "Tilt the wands to pass the ball.").
4. `### Cards you need`, when the game reads NFC tags.
5. Optionally one offered next change.

Code comes early so a long reply is less likely to be cut off before the code ends.

## Markers

| Marker | Read by | Effect |
|---|---|---|
| `[DEVICE: wand\|icon]` | `extractCodeBlocks` | Assigns the next code block to that role's editor. Unmarked blocks are wand code. |
| `[GAME_NAME: …]` | `parseGameName` | Game name; slugified for storage and baseline tags. |
| `[GAME_ICON: SHAPE_X, COLOR]` | `parseGameIcon` | Start signature; stored with the game (`gameIcon` in state and the saved entry). The same in every version; a new pair (only when the teacher asks for one) replaces it. |
| `[NFC_CARDS: "a", "b"]` | `parseNfcCards` | Declared tags; used for the tag list only when the code has no `COMMANDS` set. |
| `[GAME_SETTINGS: {…}]` | `parseGameSettings` | Simulator wand count (1–4) and Splats per wand (0–2). Not used for hardware requirements. |
| `[NEXT_DEVICE: <role>]` | `parseNextDevice` | Another device still needs its file; the app requests it automatically. |
| `[CHOICES: "…", …]` | `parseChoices` | Up to 4 follow-up chips. Not shown when an automatic next-device request follows. |

`stripAllMarkers` hides every marker from the teacher, including partial markers while streaming.

## Code blocks

- A block replaces its role's editor only if it passes the role's `play()` signature check.
  Otherwise it is a snippet: it stays in the chat and the game is unchanged.
- History keeps `[code: N lines, sent to editor]` in place of each block; the current editor code is
  sent in the per-turn system block instead.

## Display while streaming and when finished

- **While streaming**, the reply is rendered as it arrives, including raw code from an open code
  block. This is intended and should stay.
- **A finished message never shows incomplete code.** `hideOpenCode` removes an unclosed code
  block from the final render.

## Cut-off replies (`stop_reason: max_tokens`)

`MAX_TOKENS` is in `js/prompt/buildRequest.js`.

1. No code reaches the editor. The message keeps only the prose before the code (or is removed if
   there is none), and history records that the code was cut off.
2. The first cut-off is re-asked automatically in a hidden message asking for the same file,
   shorter. The teacher sees "That reply was too long — asking for a shorter version…".
3. If the re-ask is also cut off, the teacher is told the game was not changed and asked to request
   a simpler version. There is no further retry.

## Multi-device games

A new game for more than one device is written one device per reply, wand first. A reply that
writes a complete file and ends with `[NEXT_DEVICE: <role>]` triggers a hidden request for that
role's file. The app follows the marker only for a known role not written in the same reply, and
at most once per additional role, so it cannot loop. A cut-off or snippet reply triggers no
next-device request.
