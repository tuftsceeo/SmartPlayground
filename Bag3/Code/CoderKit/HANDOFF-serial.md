# Handoff: real USB serial for the Playground IDE artifacts

## Goal
Testers are mostly non-technical people who use Claude chat (not Claude Code). They mock up IDE front ends as claude.ai artifacts. Today, inside an artifact, **Connect / Send to Device / device panel / distribute are simulated**, because claude.ai's artifact frame does not allow Web Serial. That is confirmed: the test artifact https://claude.ai/artifact/7BoscfpDc8QEHy5dinFLEu (source `CoderKit/artifact/serial-test.html`) shows no serial access.

Make a real controller (the Dial or the Box, over USB serial) work from the artifacts, with the **easiest possible setup** for non-coders.

## What exists (read these first)
- `Bag3/Code/CoderKit/` is the headless kit and its tools:
  - `coderkit.js` (the kit: `kit.connect()`, `kit.send()`, `state.link`, device panel, distribute);
  - `bridge.js` (the runner ↔ sandboxed-frame relay);
  - `run.html` (the "runner", a local page meant to host a design with real Web Serial);
  - `artifact-entry.js` (the artifact build, with a simulated device);
  - `tools/build_skill.mjs` (builds `artifact/*.html` plus the files maps);
  - `tools/kit_test.mjs` (17 tests, `node tools/kit_test.mjs`).
- `Bag3/Code/ChatBroadcast/` is the real web app.
  - Its serial code (Web Serial, protocol, `games.list` / `games.select` / `fleet.*` commands) is the reference for how the Dial and Box talk.
  - **Do not modify ChatBroadcast or Simulator.** Import from them; don't copy.
- Published artifacts (all private):
  - Blank: https://claude.ai/artifact/XZp1mnt6eGydTNeByq4HSm
  - Full: https://claude.ai/artifact/BJDJgDev3LkKciVtdwFuMz
  - ChatBroadcast-style: https://claude.ai/artifact/LcFNJ9fzQvcqwGsyNK3Ams
- Local dev server: `cd Bag3/Code && python3 -m http.server 8790`, then `http://localhost:8790/CoderKit/run.html?src=frontends/full.html`.

**Important:** the owner has **never seen `run.html` connect to a real controller.** Treat the runner's serial path as unverified. Do not build on it until it has been proven with hardware.

## Rules
- Do not commit, push, or publish to GitHub Pages or Live Pages without the owner's OK. Work on branch `stress-unattended-2026-11-18` or a new branch.
- Don't change ChatBroadcast or Simulator.
- Keep the kit's API the same, so existing designs keep working. Choose real versus simulated inside the kit.
- Write user-facing text in plain language for non-coders.

## Plan

### Phase 0: prove serial works at all, outside artifacts (about 30 min)
1. Serve `CoderKit/artifact/serial-test.html` from localhost (e.g. `http://localhost:8790/CoderKit/artifact/serial-test.html`), open it in Chrome with a Dial or Box plugged in, and Connect.
   - Confirm the port opens and the controller's output appears.
   - Note the baud rate and line format. Check against ChatBroadcast's serial code; 115200 is a guess.
2. Then try `run.html` with a real controller: Connect, then Send to Device with an example game. Fix whatever breaks.
   - The owner must do the physical step. Write exact click-by-click instructions for them and ask them to report back.

### Phase 1: proof of concept for a local MCP bridge (the "inside the artifact" path)
Artifacts can call MCP servers that run **on the viewer's own computer**, through the `mcp` capability with `server: "host:<name>"`. This works in the Claude desktop app only; elsewhere the call fails with `server_not_connected`. Load the `artifact-capabilities` skill and read the `mcp` type definitions before writing code. Don't guess the call shapes.

1. Build a tiny local MCP server, **"Playground Serial"** (Node, using the `serialport` package, or Python with `pyserial`), with these tools:
   - `list_ports`;
   - `open(path, baud)`;
   - `write(text)` (or `write_bytes`);
   - `read()`, which returns the lines buffered since the last read;
   - `close`;
   - `status`.
2. Package it as a **Claude Desktop extension (`.mcpb`)** so a tester installs it by double-clicking. Bundle the dependencies, so testers don't need Node or Python installed. Check what format the current Desktop extension uses.
3. Make a copy of the serial test artifact that declares `capabilities: {mcp: {servers: [{server: "host:playground-serial", tools: [...]}]}}` and uses `callTool` for list, open, write and read, polling `read` every 200–300 ms.
4. With the owner, check in the Claude desktop app with real hardware. Record:
   - the consent prompts;
   - the latency;
   - Windows driver needs, if anyone tests on Windows.

**Go/no-go:** an artifact in the desktop app lists the ports, opens one, and shows the controller's output.

### Phase 2: wire it into the kit (if Phase 1 works)
1. Add an MCP serial transport to the kit, behind the same interface the kit's real serial transport uses (find it in `coderkit.js` and `run.html`).
   - The kit picks it when `claude.use("mcp")` resolves and `host:playground-serial` answers `status`.
   - Otherwise it falls back to the simulated device, as today.
2. Expose `state.can.realDevice` so the designs can show "Real controller" or "Practice mode".
3. Add the `mcp` capability to the three IDE artifacts in `build_skill.mjs` (they already declare `sample`), rebuild, and republish to the same URLs (only with the owner's OK).
4. Add tests in `tools/kit_test.mjs` with a fake MCP transport.

### Phase 3 (optional, no install): a "Test on my controller" button
If Phase 0 shows that `run.html` works, offer a hosted runner, for example on GitHub Pages. This needs the owner's OK.
- An artifact button packs the current design into a link (`packDesign` in `bridge.js`) and opens the runner.
- This works in Chrome with nothing to install, but the work happens outside the artifact.

### Phase 4: tester docs
- Update the tester guide doc https://claude.ai/artifact/4bbNaga6dBVqBJXXPn7cH2 with a short **"Use a real controller"** section:
  - install the extension (one double-click);
  - use the Claude desktop app;
  - plug in the controller;
  - click Connect and Allow.
- Add a troubleshooting list:
  - no ports listed;
  - the port is busy because another tab or the web app has it;
  - Windows drivers.

## Done means
- A non-technical tester can install one file, open an IDE artifact in the Claude desktop app, click Connect, and send a game to a real Dial or Box.
- Without the extension, everything still works in practice mode.
- The tests pass.
- Nothing is committed or published without the owner's OK.
- Report what was verified with hardware and what wasn't.
