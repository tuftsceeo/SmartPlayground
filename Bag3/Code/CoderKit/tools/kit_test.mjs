// Run from CoderKit/:  node tools/kit_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createKit, parseReply, buildSend, systemBlocks } from '../coderkit.js';
import { checkFrontEnd, warnFrontEnd } from '../check.js';
import { McpSerialAdapter, autoDevice, pickPort, createMcpDeviceLink, MCP_SERVER } from '../mcpSerial.js';
import { knowledgePaths } from '../../ChatBroadcast/js/prompt/buildRequest.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const cb = join(root, '../ChatBroadcast');
const files = Object.fromEntries(knowledgePaths().map(p => [p, readFileSync(join(cb, p), 'utf8')]));
let n = 0;
const test = async (name, fn) => { await fn(); n++; console.log('ok', name); };

const GAME = `def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):\n    leds.fill((0, 0, 255))\n`;
const REPLY = `Here is your game! [GAME_NAME: Blue Glow]\n\n[DEVICE: wand]\n\`\`\`python\n${GAME}\`\`\`\n\n[CHOICES: "Make it red", "Add a sound"]`;

await test('system blocks carry the real knowledge', () => {
    const sys = systemBlocks(files);
    const all = sys.map(b => b.text).join('\n');
    assert.ok(all.includes(files['knowledge/platform.md'].slice(0, 200)));
    assert.ok(all.includes('def play(nfc, leds'));
});

await test('parseReply pulls code, name, choices like app.js', () => {
    const r = parseReply(REPLY);
    assert.equal(r.code.wand.trim(), GAME.trim());
    assert.equal(r.gameName, 'Blue Glow');
    assert.deepEqual(r.choices, ['Make it red', 'Add a sound']);
    assert.ok(!r.text.includes('[GAME_NAME'));
});

await test('a block without play() is a snippet, not the game', () => {
    const r = parseReply('```python\nprint(1)\n```');
    assert.deepEqual(r.code, {});
    assert.equal(r.snippets.length, 1);
});

await test('buildSend meta matches confirmSend', () => {
    const p = buildSend({ wand: GAME }, 'Blue Glow', 'Dial');
    assert.ok(p.ok);
    assert.match(p.meta.slug, /^blue/);
    assert.equal(p.meta.destPath, `/flash/games/${p.meta.slug}.py`);
    assert.equal(p.meta.prettyName, 'Blue Glow');
    assert.ok(Array.isArray(p.meta.tags));
    assert.equal(buildSend({}, 'x').ok, false);
});

await test('chat + connect + send against fakes', async () => {
    const seen = {};
    const brain = async ({ system, history, onText }) => { seen.system = system; seen.history = history; onText('Here'); return { text: REPLY, stopReason: 'end_turn' }; };
    const handlers = {};
    const device = {
        on: (t, f) => { handlers[t] = f; },
        connect: async () => { setTimeout(() => handlers.identity({ type: 'identity', device: 'broadcast_dial' }), 0); },
        nudgeIdentify: async () => true,
        isConnected: () => true,
        sendGame: async (code, meta, onProgress) => { seen.sent = { code, meta }; onProgress({ current: 1, total: 1, status: 'done' }); return { ok: true }; },
    };
    const kit = createKit({ brain, device, files });
    await kit.ready;
    const r = await kit.chat('a blue game');
    assert.equal(r.gameName, 'Blue Glow');
    assert.equal(seen.history.at(-1).content, 'a blue game');
    assert.ok(seen.system.length >= 2);
    assert.equal((await kit.send()).ok, false, 'not connected yet');
    await kit.connect();
    await new Promise(r => setTimeout(r, 5));
    assert.equal(kit.state.link, 'live');
    assert.equal(kit.state.deviceName, 'teacher hub'); // deviceShortName(), as the app labels it
    const s = await kit.send();
    assert.ok(s.ok, s.error);
    assert.equal(seen.sent.code.trim(), GAME.trim());
    assert.equal(seen.sent.meta.deviceLabel, 'teacher hub');
    assert.equal(kit.state.link, 'live');
    assert.equal(kit.state.messages.length, 2);
    const lines = kit.state.log.map(l => l.text).join('\n');
    assert.match(lines, /Game code updated: wand/);
    assert.match(lines, /Connected to teacher hub/);
    assert.match(lines, /Sent "Blue Glow"/);
    assert.ok(kit.state.log.some(l => l.level === 'error' && /Connect your controller first/.test(l.text)));
});

await test('a failed reply leaves history clean', async () => {
    const kit = createKit({ brain: async () => ({ text: '', error: { message: 'boom' } }), device: { on() {} }, files });
    assert.equal(await kit.chat('hi'), null);
    assert.equal(kit.state.error, 'boom');
    assert.equal(kit.state.messages.at(-1).role, 'system');
    assert.equal(kit.state.log.at(-1).level, 'error');
});

await test('blank.html and full.html pass the checker with no warnings', () => {
    for (const f of ['blank', 'full']) {
        const html = readFileSync(join(root, `frontends/${f}.html`), 'utf8');
        assert.deepEqual(checkFrontEnd(html), [], f);
        assert.deepEqual(warnFrontEnd(html), [], f);
    }
});

await test('checker warns on unknown parts', () => {
    assert.equal(warnFrontEnd('<i data-kit="simulator"></i><i data-kit="sparkles"></i><i data-kit="sparkles"></i>').length, 1);
});

await test('checker rejects missing parts and foreign scripts', () => {
    const p = checkFrontEnd('<div data-kit="chat-log"></div><script src="https://evil.example/x.js"></script>');
    assert.equal(p.length, 5);
});

// ---------- phase 2 parts ----------
const mem = {};
globalThis.localStorage = { getItem: k => mem[k] ?? null, setItem: (k, v) => { mem[k] = String(v); }, removeItem: k => { delete mem[k]; } };

function fakeDevice(answers = {}) {
    const h = {};
    const d = {
        on: (t, f) => { (h[t] ||= []).push(f); return () => {}; },
        emit: (t, o) => (h[t] || []).forEach(f => f(o)),
        connect: async () => { setTimeout(() => d.emit('identity', { type: 'identity', device: 'broadcast_dial' }), 0); },
        nudgeIdentify: async () => true,
        isConnected: () => true,
        sendGame: async () => ({ ok: true }),
        cmds: [],
        sendCmd: async (c) => { d.cmds.push(c); const a = answers[c.cmd]; return typeof a === 'function' ? a(c) : (a || { ok: true }); },
    };
    return d;
}
const tick = () => new Promise(r => setTimeout(r, 5));
const ICON = `def play(nfc, panel, enow):\n    panel.show('heart')\n`;

await test('versions: chat replies add versions; prev/next move between them', async () => {
    const replies = [REPLY, REPLY.replace('0, 0, 255', '255, 0, 0')];
    const kit = createKit({ brain: async () => ({ text: replies.shift() }), device: fakeDevice(), files });
    await kit.chat('blue'); await kit.chat('red');
    assert.equal(kit.state.versions.wand.list.length, 2);
    assert.match(kit.state.code.wand, /255, 0, 0/);
    kit.prevVersion('wand');
    assert.match(kit.state.code.wand, /0, 0, 255/);
    kit.nextVersion('wand');
    kit.setCode('wand', GAME + '# edited\n');
    assert.equal(kit.state.versions.wand.list.at(-1).label, 'Edited');
});

await test('next-device chaining asks once for the display file', async () => {
    const asks = [];
    const first = `Wand part [GAME_NAME: Hearts]\n[DEVICE: wand]\n\`\`\`python\n${GAME}\`\`\`\n[NEXT_DEVICE: icon]`;
    const second = `Display part\n[DEVICE: icon]\n\`\`\`python\n${ICON}\`\`\`\n[NEXT_DEVICE: wand]`;
    const replies = [first, second];
    const kit = createKit({ brain: async ({ history }) => { asks.push(history.at(-1).content); return { text: replies.shift() }; }, device: fakeDevice(), files });
    await kit.chat('hearts on the display');
    assert.equal(asks.length, 2, 'one automatic request, and [NEXT_DEVICE: wand] after it is ignored');
    assert.match(asks[1], /\[DEVICE: icon\]/);
    assert.ok(kit.state.code.icon);
    assert.equal(kit.state.messages.filter(m => m.role === 'user').length, 1);
});

await test('examples: list, open, remix', async () => {
    const kit = createKit({ brain: async () => ({ text: REPLY }), device: fakeDevice(), files, exampleCode: async (ex) => `# ${ex.id}\n${GAME}` });
    const { list, categories } = kit.examples();
    assert.ok(list.length > 3 && categories.length);
    await kit.openExample(list[0].id);
    assert.match(kit.state.code.wand, new RegExp(list[0].id));
    assert.equal(kit.state.gameName, list[0].name);
    await kit.remixExample(list[0].id);
    assert.match(kit.state.gameName, /remix/);
});

await test('saved games: save, list, open, rename, delete (same store as the app)', async () => {
    const kit = createKit({ brain: async () => ({ text: REPLY }), device: fakeDevice(), files });
    await kit.chat('a blue game');
    const e = kit.saveGame();
    assert.equal(e.name, 'Blue Glow');
    assert.ok(mem['wandcoder.savedGames']);
    kit.newGame();
    assert.deepEqual(kit.state.code, {});
    kit.openSaved(e.id);
    assert.equal(kit.state.code.wand.trim(), GAME.trim());
    assert.equal(kit.state.messages.length, 2);
    kit.renameSaved(e.id, 'Calm Blue');
    assert.equal(kit.saved()[0].name, 'Calm Blue');
    kit.deleteSaved(e.id);
    assert.equal(kit.saved().length, 0);
});

await test('interview: questions, then a brief, then the game', async () => {
    const calls = [];
    const brief = JSON.stringify({ message: 'Here is the plan.', title: 'Tag Race', wands: '2', play: 'Race to tap tags', extras: 'None',
        how_to_play: 'Tap tags fast', what_happens: 'Lights', start_and_end: 'Shake', cards: 'red, blue', defaults: '' });
    const kit = createKit({ brain: async (req) => {
        calls.push(req);
        if (req.format) return { text: brief };
        if (calls.length === 1) return { text: 'Who plays? [CHOICES: "Kids", "Teens"]' };
        return { text: REPLY };
    }, device: fakeDevice(), files });
    kit.startInterview();
    assert.equal(kit.state.interview.asked, 1);
    await kit.chat('Tag Race');
    assert.equal(kit.state.interview.asked, 2);
    assert.match(kit.state.messages.at(-1).text, /Who plays/);
    await kit.finishInterview();
    assert.ok(calls.at(-1).format, 'last turn asks for the brief format');
    assert.equal(kit.state.interview, null);
    assert.match(kit.state.brief, /Title: Tag Race/);
    await kit.makeFromBrief();
    assert.match(calls.at(-1).history.at(-1).content, /Make this game for my class/);
    assert.ok(kit.state.code.wand);
});

await test('controller games: list after connect, select, delete', async () => {
    const d = fakeDevice({ 'games.list': { list: [{ slug: 'blueglow', name: 'Blue Glow' }], active: 'blueglow' } });
    const kit = createKit({ brain: async () => ({ text: REPLY }), device: d, files });
    await kit.connect(); await tick(); await tick();
    assert.equal(kit.state.device.games.length, 1);
    assert.equal((await kit.selectGame('blueglow')).ok, true);
    await kit.deleteGame('blueglow');
    assert.deepEqual(d.cmds.map(c => c.cmd), ['games.list', 'games.select', 'games.list', 'games.delete', 'games.list']);
});

await test('distribute: scan, rows, send, progress, done', async () => {
    const d = fakeDevice({ 'games.list': { list: [] } });
    const kit = createKit({ brain: async () => ({ text: REPLY }), device: d, files });
    await kit.chat('blue');
    await kit.connect(); await tick();
    await kit.send();
    await kit.distribute.open();
    assert.ok(d.cmds.some(c => c.cmd === 'fleet.scan'));
    d.emit('status_report', { mac: 'aa:bb', kind: 'wand', battery: 90, g: [] });
    d.emit('status_report', { mac: 'cc:dd', kind: 'icon_display', g: [] });
    d.emit('status_done', {});
    const rows = kit.state.distribute.rows;
    assert.equal(rows.length, 2);
    assert.equal(rows.find(r => r.mac === 'aa:bb').selected, true);
    assert.equal(rows.find(r => r.mac === 'cc:dd').selected, false, 'game has no display code');
    await kit.distribute.send();
    const c = d.cmds.find(c => c.cmd === 'fleet.distribute');
    assert.deepEqual(c.macs, ['aa:bb']);
    d.emit('dist_progress', { mac: 'aa:bb', ok: true, done: 1, total: 1 });
    d.emit('dist_done', { done: 1, total: 1 });
    assert.equal(kit.state.distribute.rows[0].status, 'done');
    assert.match(kit.state.log.at(-1).text, /1 of 1 devices updated/);
    kit.distribute.close();
    assert.equal(kit.state.distribute, null);
});

await test('simulator: placeholder without one; follows code with one', async () => {
    const el = { textContent: '' };
    let kit = createKit({ brain: async () => ({ text: REPLY }), device: fakeDevice(), files });
    assert.equal(kit.mountSimulator(el), null);
    assert.match(el.textContent, /runner/);
    const seen = [];
    kit = createKit({ brain: async () => ({ text: REPLY }), device: fakeDevice(), files, simulator: () => ({ update: (c) => seen.push(c) }) });
    kit.mountSimulator(el);
    await kit.chat('blue');
    assert.ok(seen.at(-1).wand);
    assert.equal(kit.state.can.simulator, true);
});

// ---------- Playground Serial (mcp) transport, with a pretend extension ----------
/** Behaves like serial-extension/server/index.js with a Dial on the port. */
function fakeMcp({ version = '0.1.2', ports } = {}) {
    let open = false, lines = [];
    const calls = [], written = [];
    const reply = (o) => lines.push(JSON.stringify(o));
    const tools = {
        status: () => ({ open, version }),
        list_ports: () => ({ ports: ports || [{ path: '/dev/cu.debug' }, { path: '/dev/cu.usbmodem1101', manufacturer: 'M5Stack', vendorId: '303a' }] }),
        open: ({ path }) => { open = true; setTimeout(() => reply({ type: 'heartbeat', up: 1 }), 5); return { open, path }; },
        write: ({ text }) => {
            written.push(text);
            for (const l of text.split(/\r?\n/).filter(Boolean)) {
                const c = JSON.parse(l);
                if (c.cmd === 'identify') reply({ type: 'identity', device: 'broadcast_dial', id: c.id });
                else if (c.cmd === 'games.list') reply({ type: 'games', list: [{ slug: 'blue_glow', name: 'Blue Glow' }], active: 'blue_glow', id: c.id });
                else reply({ type: 'ok', id: c.id });
            }
            return { written: text.length };
        },
        read: () => { const out = lines; lines = []; return { lines: out, open }; },
        close: () => { open = false; return { open }; },
    };
    return {
        calls, written, unplug: () => { open = false; },
        async callTool(server, tool, input) {
            assert.equal(server, MCP_SERVER);
            calls.push(tool);
            await new Promise(r => setTimeout(r, 1));
            return { payload: tools[tool](input || {}) };
        },
    };
}
const until = async (fn, ms = 3000) => { const t = Date.now(); while (!fn()) { if (Date.now() - t > ms) throw new Error('timed out'); await new Promise(r => setTimeout(r, 10)); } };

await test('mcp: pickPort prefers the M5 controller', () => {
    assert.equal(pickPort([{ path: 'a' }, { path: 'b', vendorId: '303a' }]).path, 'b');
    assert.equal(pickPort([{ path: '/dev/cu.Bluetooth' }]), null);
});

await test('mcp: adapter opens the controller and feeds lines to the reader', async () => {
    const mcp = fakeMcp();
    const a = new McpSerialAdapter(mcp, { idleMs: 5 });
    let seen = '';
    a.onData = (c) => { seen += c; };
    await a.connect();
    assert.equal(a.path, '/dev/cu.usbmodem1101');
    assert.equal(a.longPoll, true);
    await until(() => seen.includes('heartbeat'));
    await a.writeChunked('{"cmd":"identify","id":7}\r\n');
    await until(() => seen.includes('identity'));
    await a.disconnect();
    assert.ok(mcp.calls.includes('close'));
});

await test('mcp: no controller plugged in gives a plain message', async () => {
    const a = new McpSerialAdapter(fakeMcp({ ports: [] }), { idleMs: 5 });
    await assert.rejects(a.connect(), /No USB ports found/);
});

await test('mcp: Connect asks which port, and Cancel opens nothing', async () => {
    const mcp = fakeMcp();
    let offered;
    const a = new McpSerialAdapter(mcp, { idleMs: 5, choosePort: async (ports, suggested) => { offered = { ports, suggested }; return '/dev/cu.debug'; } });
    await a.connect();
    assert.equal(offered.ports.length, 2);
    assert.equal(offered.suggested, '/dev/cu.usbmodem1101');
    assert.equal(a.path, '/dev/cu.debug');
    await a.disconnect();
    const b = new McpSerialAdapter(fakeMcp(), { idleMs: 5, choosePort: async () => null });
    await assert.rejects(b.connect(), /No port selected/);
    assert.equal(b.isConnected(), false);
});

await test('mcp: kit goes real when the extension answers, and talks to the Dial', async () => {
    const mcp = fakeMcp();
    const device = autoDevice({ fallback: { ...fakeDevice(), isConnected: () => false }, probe: async () => mcp, makeReal: (m) => createMcpDeviceLink(m, { idleMs: 5 }) });
    const kit = createKit({ brain: async () => ({ text: REPLY }), device, files });
    assert.equal(kit.state.can.realDevice, false);
    assert.equal(await device.ready, true);
    assert.equal(kit.state.can.realDevice, true);
    await kit.connect();
    await until(() => kit.state.link === 'live');
    const r = await device.sendCmd({ cmd: 'games.list' });
    assert.equal(r.list[0].slug, 'blue_glow');
    mcp.unplug();
    await until(() => kit.state.link === 'idle');
});

await test('mcp: without the extension the kit stays in practice mode', async () => {
    const sim = fakeDevice();
    const device = autoDevice({ fallback: sim, probe: async () => null });
    const kit = createKit({ brain: async () => ({ text: REPLY }), device, files });
    assert.equal(await device.ready, false);
    assert.equal(kit.state.can.realDevice, false);
    assert.equal(device.simulated, true);
});

console.log(`\n${n} tests passed`);
