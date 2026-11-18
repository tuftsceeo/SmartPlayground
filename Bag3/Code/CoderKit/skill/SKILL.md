---
name: playground-ide
description: Build a brand-new Playground Coder IDE (front end) for the Smart Playground, as a claude.ai artifact. Use when someone wants to design, prototype or try a new interface for making playground games (wand, Dial, Box, icon display). The IDE chats with Claude using the real Chat Broadcast knowledge and priming, so the games it makes run on the playground.
---

# Playground IDE kit

You are helping a teammate make a **new IDE from a blank page**. Do not copy the look of Chat Broadcast (its fonts, icons, colors or layout). Start from one of two templates, both plain default Tailwind, and design what the person describes:

- `templates/blank.html`: only the required parts. Best for a fresh idea.
- `templates/full.html`: every part (home, examples, saved games, interview, code view, simulator, controller panel, distribute, log). Best when the person wants something close to the full web app; remove or rearrange parts freely.

Both templates include a small "Click the Chat button" callout (`#chat-callout`) for people opening the shared artifact. Remove it from the person's own design unless they want to keep it.

## The contract (required in every IDE)

Mark these elements with `data-kit` attributes. `kit/check.js` (`checkFrontEnd(html)`) rejects a design without them:

| `data-kit` | Part |
|---|---|
| `chat-log` | a chat column showing the conversation |
| `chat-input` | a text box for the message |
| `chat-send` | a button that sends it |
| `connect` | a button that connects the Dial or Box (teacher controller) |
| `send-to-device` | a button that sends the game to the controller |

## Optional parts

Add any of these with their `data-kit` value. `warnFrontEnd(html)` warns about values not in this list. "Artifact" says how each part behaves in a claude.ai artifact.

| `data-kit` | Part | Kit API | Artifact |
|---|---|---|---|
| `game-name` | game name field | `state.gameName`, `setGameName(n)` | real |
| `choices` | suggested replies | `state.choices` → `chat(choice)` | real |
| `log` | activity log | `state.log`, `log(text, level)`, `clearLog()` | real |
| `home` | start screen | `newGame()` plus the parts below | real |
| `examples` | example games | `examples()` → `{categories, list}`, `openExample(id)`, `remixExample(id)` | real |
| `saved-games` | saved games (browser storage) | `saved()`, `saveGame(name?)`, `openSaved(id)`, `renameSaved(id, n)`, `deleteSaved(id)` | real |
| `interview` | plan a game with questions | `startInterview()`, then `chat(answer)`; `finishInterview()`, `cancelInterview()`; `state.interview` `{asked, max}`; `state.brief` and `makeFromBrief()` | real |
| `code-view` | code per device, with versions | `roles` `[{key, label}]`, `state.code[role]`, `state.versions[role]` `{list:[{label,t}], index}`, `setCode(role, code)`, `prevVersion(role)`, `nextVersion(role)` | real |
| `simulator` | the playground simulator | `mountSimulator(el)` once; it follows the code. `fixSimError()` asks Claude to fix the last simulator error | real when the page has `<meta name="coderkit-simulator">` before the kit script and is published with the simulator files (see below); otherwise a placeholder |
| `device-panel` | games on the controller | `state.device` `{mode, active, games:[{slug, name}]}`, `refreshGames()`, `selectGame(slug)`, `deleteGame(slug)`, `state.tagWrites` | simulated |
| `distribute` | send a game to many devices | `distribute.open()`, `.scan()`, `.toggle(mac, on)`, `.send(slot?)`, `.find(mac)`, `.close()`; `state.distribute` `{pretty, status, rows, running, done, total, needsSlot, slots}` | simulated |

`state.can` `{simulator, realDevice}` says what is real here, so a design can hide or label the rest. `kit.chat` also asks again for the next device when a game needs both (wand and icon display); you don't have to.

## The kit (`window.kit`)

Load it with `<script src="coderkit.js"></script>` in the head, before the page's own script.

```js
kit.on('change', state => render(state));   // re-render from state on every change
kit.chat(text)                  // -> {reply, code, gameName, choices} or null on error
kit.connect()                   // call inside a click handler
kit.disconnect()
kit.send()                      // -> {ok, error}: the latest game to the controller
kit.reset()                     // new game
kit.setGameName(name)
kit.state = {
  link: 'idle' | 'opening' | 'live' | 'sending',
  deviceName,                   // e.g. "teacher hub" once it answers
  gameName, code: {wand, icon}, // code per device
  messages: [{role: 'user'|'assistant'|'system', text, streaming?, code?}],
  choices: [],                  // suggested follow-ups (buttons that call kit.chat)
  busy, progress /* 0..1 while sending */, error,
  log: [{id, t, level, text}],  // what is happening, newest last
}
kit.log(text, level)            // add your own line
kit.clearLog()
```

Assistant `text` has the code blocks in it as markdown fences; render it as text or as simple markdown. Do not call Claude yourself and do not write your own system prompt: the kit already sends Chat Broadcast's full knowledge and priming (`priming.md`, `knowledge/`). That is what makes the games work on the playground.

## Making it an artifact

1. Write the IDE as one HTML page (Tailwind from `https://cdn.tailwindcss.com/3.4.17`, plain JS, no other script hosts).
2. Publish it as an artifact with `capabilities: {sample: {}}` and publish `kit/coderkit.js` beside it via `files: {"coderkit.js": "<path to kit/coderkit.js>"}`.
3. Chat runs on the **viewer's own Claude account**. Connect and send use a **simulated Dial** in artifacts (Web Serial is blocked there); the page should still show both buttons.
4. With a simulator: add `<meta name="coderkit-simulator">` before `coderkit.js` and publish every file listed in `kit/full-files.json` too (paths as keys). Pyodide and the simulator then load from the artifact itself; CDNs are blocked there.
5. To try it on a real Dial or Box: export the HTML and open it in the team runner, `CoderKit/run.html` (Live Pages), with **Open file** or **Paste design**.

## Good practice

- Keep it simple for teachers: the chat and the two device buttons should be obvious.
- Show `state.error` somewhere visible, and `state.link` as connection status.
- Show what is happening: toast new `state.log` lines whose `level` is `'ok'` or `'error'` (track the last `id` you showed), and offer the full log somewhere (a panel or drawer). `'device'` lines are raw controller messages; hide them by default.
- Disable the send button while `state.busy`.
- Don't use `alert`, `confirm` or `prompt`.
