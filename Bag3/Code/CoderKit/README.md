# CoderKit: Playground Coder front-end lab

New IDEs for Playground Coder start from a blank page. CoderKit gives them Chat Broadcast's behavior with no interface: the chat with its real knowledge and priming, the Dial/Box connection, and sending a game. Every piece is imported unchanged from `../ChatBroadcast/js/`; nothing in Chat Broadcast is modified.

## Every IDE must have

`data-kit` = `chat-log`, `chat-input`, `chat-send`, `connect`, `send-to-device`. `check.js` rejects a design without them. Start from `frontends/blank.html`.

## Three ways to run an IDE

| Where | Claude runs on | Device |
|---|---|---|
| claude.ai artifact (`skill/kit/coderkit.js` published beside the page, `capabilities: {sample: {}}`) | the viewer's own account | simulated Dial |
| `run.html` (local or Live Pages): Open file, Paste design, or a `#f=` link | the shared key (magic code), so keep it short | real Dial/Box over Web Serial |
| Node tests | fakes | fakes |

`run.html` loads the design in a sandboxed frame (no same-origin), so a shared design cannot read the site's storage or the magic code. Its own **Connect controller** button is there in case a design's Connect does nothing.

## The team skill

`skill/` is a Claude skill (`SKILL.md`, the knowledge, `priming.md`, the bundled kit, the blank template). Upload `skill.zip` in claude.ai and share it with the team. Rebuild it whenever the knowledge changes:

```bash
npm install && node tools/build_skill.mjs
```

## Files

- `coderkit.js`: the kit (`createKit`, `parseReply`, `buildSend`, `systemBlocks`)
- `brains.js`: `apiKeyBrain` (shared key) and `sampleBrain` (claude.ai `sample`)
- `bridge.js`: the postMessage kit for sandboxed designs, and `#f=` links
- `check.js`: the contract check
- `artifact-entry.js`: the artifact build (knowledge bundled in, simulated Dial)
- `tools/kit_test.mjs`: `node tools/kit_test.mjs`
