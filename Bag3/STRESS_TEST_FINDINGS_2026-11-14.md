# Hands-on test findings, 2026-11-14

Branch `ccr-eec157d8-pkam3d`. One tester, ChatBroadcast in Simple mode, a Broadcast Dial and two
wands. One generated game (Memory, a Splat host game) was taken from the interview through the
Simulator and Dial to the wands. Each item says what the user saw, what was done and where it
is recorded. Nothing below has been fixed unless it says so.

## Fixed during testing
| # | Issue | Fix |
|---|---|---|
| F1 | Interview ended with a summary but never offered to make the game. The model left out the closing `[/GAME_BRIEF]` tag. | `parseGameBrief` accepts a brief with no closing tag (`d9cd1d96`). Not yet rechecked in the browser. |
| F2 | "Can't simulate": the generated game's `import signals` failed (`ModuleNotFoundError`). The Simulator never copied the wand's `lib/signals.py`. | `signals` added to the Simulator's copied libraries (`35975021`). 9 Simulator tests already failed before this change; they belong to S6 item 1. |

## Open: generated games and the knowledge files
| # | Issue | Note |
|---|---|---|
| K1 | Games end after a win. Every game should show a celebration and then start a new round, forever, until a stop message is sent (examples: melody, cooking, freeze_dance). No knowledge file says this, and the interview asks how a game "ends". | `known_issues/2026-11-14-games-must-repeat.md` |
| K2 | The generated host game ignored `splat_lost`, which `splat_host_games.md` requires. | `known_issues/2026-11-14-send-check-errors-ux.md` |
| K3 | Splat host games leave the host wand out of the count. The app shows "2 wands, 4 Splats" when the game needs 3 wands. `savedGameDevices()` never adds the host, and the brief format doesn't say to count it. | `known_issues/2026-11-14-splat-host-wand-count.md` |
| K4 | The Simulator's card tray offers the game's own start card ("memory"), although the game starts without it. The start card should not be a play card, because it is sometimes used to reset or clear a game. | `known_issues/2026-11-14-start-tag-in-tray.md` |

## Open: how the app and devices behave for a teacher
| # | Issue | Note |
|---|---|---|
| U1 | Send-time check errors show as a toast in code terms (`net.poll`, `splat_lost`), and the Simulator never runs those checks, so they appear late. There is no way to ask the chat to fix them. Wanted: run the checks when a game is made; failures get a "fix it" path like "Can't simulate" has; in Simple mode they go to the chat automatically. | `known_issues/2026-11-14-send-check-errors-ux.md` |
| U2 | "Hold the helper wand's button to start" is unclear. Every hold should show progress from press to trigger, as the Dial does. The Splat host already fills a cross from 0.4 s (the start fires at 1.5 s), but the tester still found it unclear, and game text never says what to watch for. | `known_issues/2026-11-14-hold-interactions-ux.md` |
| U3 | The full brief is shown to Simple mode users, although it is mostly written for the agent. | Not recorded yet |

## Open: Dial
| # | Issue | Note |
|---|---|---|
| D1 | Every Send to device restarts the Dial and drops USB: the app writes the game through the raw REPL and then soft-resets the Dial. The Box works the same way. | Added to the plan as S5 step 4 (`e92d637e`): upload over the JSON link, no reset |
| D2 | With the keyboard open, one distribute failed for both wands: the Dial sent the push, but neither wand's request arrived (no `[ENX] offer`), and both timed out. The Dial printed `RuntimeError: schedule queue full` from its screen timer, meaning its main loop stalled. After a USB reconnect, with the keyboard still open, the same send worked (one wand needed retries, `send_fail=2`). The failure came about 14 s after the keyboard was first built (free memory went from 53 KB to 27 KB); the success came about 160 s after. Cause not confirmed. | Not recorded yet. Test: restart the Dial, open the keyboard, send at once; then send while turning the dial; then send minutes later |
| D3 | Right after the soft reset for an upload, about 20 lines of `TypeError: '' object isn't callable` / `'bool' object isn't callable` came before the program's first output, then USB dropped. Source unknown. | Not recorded yet |
| D4 | S4 (radio stays on): the radio came back with the keyboard open (pushes sent, no `radio_on() failed`). Wands pulled games on the second try. | First hardware evidence for S4 |
| D5 | S5 (reconnect state): after an upload, auto-reconnect reopened the port and identified the Dial with no error this time. The original bug (app shows disconnected and Connect says "already open") was not reproduced, and no debug log of it was captured. | S5 steps 2 and 3 still open |

## Decisions the planning agent needs
1. Which stage owns K1–K4, the knowledge changes. They are not in S0–S9; S7 is the nearest.
2. Whether U1, with automatic fixes in Simple mode, is in scope before the stress test.
3. Whether to repro D2 before the stress test. The keyboard is what a teacher uses to write NFC card text.
4. When to do S5 step 4 (D1). Doing it would remove the most common trigger of the reconnect bug.
