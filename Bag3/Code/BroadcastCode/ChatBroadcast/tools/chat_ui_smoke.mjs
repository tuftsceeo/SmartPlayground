/**
 * chat_ui_smoke.mjs — drive the real chat UI in headless Chromium against
 * scripted Claude replies. No API key and no network: the encrypted key,
 * the CodeMirror CDN modules and api.anthropic.com are all served by
 * request routing.
 *
 * Checks: knowledge loads; a complete game streams into the chat, lands in
 * the editor with its markers hidden and its choice chips shown; the next
 * request carries that code in the uncached session block; a snippet reply
 * leaves the editor unchanged; Advanced mode adds the addendum block.
 *
 * Needs Playwright (global install is fine) and Chromium. From
 * ChatBroadcast/:   NODE_PATH=$(npm root -g) node tools/chat_ui_smoke.mjs
 * Exits non-zero on the first failure.
 */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve, extname } from "node:path";
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const HERE = dirname(fileURLToPath(import.meta.url));
const SERVE_ROOT = resolve(HERE, "../../..");          // Bag3/Code
const PAGE = "/BroadcastCode/ChatBroadcast/index.html";
const PASS = "testpass";
const FAKE_KEY = "sk-ant-smoke-test-key";

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
               ".css": "text/css", ".md": "text/markdown", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png", ".py": "text/plain" };

const server = createServer(async (req, res) => {
    const path = resolve(SERVE_ROOT, "." + decodeURIComponent(req.url.split("?")[0]));
    if (!path.startsWith(SERVE_ROOT)) { res.writeHead(403); res.end(); return; }
    try {
        const body = await readFile(path);
        res.writeHead(200, { "Content-Type": MIME[extname(path)] || "application/octet-stream" });
        res.end(body);
    } catch {
        res.writeHead(404); res.end();
    }
});
await new Promise(r => server.listen(0, r));
const ORIGIN = `http://localhost:${server.address().port}`;

function xorB64(text, pass) {
    let out = "";
    for (let i = 0; i < text.length; i++) out += String.fromCharCode(text.charCodeAt(i) ^ pass.charCodeAt(i % pass.length));
    return Buffer.from(out, "binary").toString("base64");
}

// Minimal CodeMirror stand-ins: enough of the API editor.js uses.
const CM_STUB = `
class Doc { constructor(t){ this.t = t; this.length = t.length; } toString(){ return this.t; } }
export class EditorView {
  constructor(o){ this.state = { doc: new Doc(o.doc || '') }; }
  dispatch(tr){ const c = tr.changes; const t = this.state.doc.toString();
    this.state = { doc: new Doc(t.slice(0, c.from) + c.insert + t.slice(c.to)) }; }
  static theme(){ return {}; }
}
export const basicSetup = {};
export const python = () => ({});
export const HighlightStyle = { define: () => ({}) };
export const syntaxHighlighting = () => ({});
const fn = () => tags;
export const tags = new Proxy(fn, { get: () => tags, apply: () => tags });
`;

function sse(text) {
    const ev = [
        { type: "message_start", message: { usage: { input_tokens: 12, cache_read_input_tokens: 0 } } },
        { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } },
        ...text.match(/[\s\S]{1,40}/g).map(t => ({ type: "content_block_delta", index: 0, delta: { type: "text_delta", text: t } })),
        { type: "content_block_stop", index: 0 },
        { type: "message_delta", delta: { stop_reason: "end_turn" }, usage: { output_tokens: 50 } },
        { type: "message_stop" },
    ];
    return ev.map(e => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join("");
}

const GAME = `import time
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED

_EXIT_TAGS = exit_tags_excluding("red_flash")
COMMANDS = _EXIT_TAGS

def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS)
    try:
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            leds.fill(RED)
            time.sleep_ms(50)
    finally:
        leds.off()`;

const REPLIES = [
    `**Every wand glows red.**\n\n### How to play\n1. Tap the game card.\n\n[DEVICE: wand]\n\`\`\`python\n${GAME}\n\`\`\`\n[GAME_NAME: Red Flash]\n[CHOICES: "Make it blink", "Add a sound"]`,
    `Change the color line to \`leds.fill(BLUE)\`:\n\n\`\`\`python\nleds.fill(BLUE)\n\`\`\``,
    `Advanced reply.`,
];

const requests = [];
const browser = await chromium.launch();
const page = await browser.newPage();
const pageErrors = [];
page.on("pageerror", e => pageErrors.push(e.message));

await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.startsWith(ORIGIN)) return route.continue();
    if (url.includes("esm.sh/")) return route.fulfill({ contentType: "text/javascript", body: CM_STUB });
    if (url.includes("encrypted_key.txt")) return route.fulfill({ contentType: "text/plain", body: xorB64(FAKE_KEY, PASS) });
    if (url.startsWith("https://api.anthropic.com/v1/messages")) {
        const body = JSON.parse(route.request().postData());
        const headers = route.request().headers();
        requests.push({ body, headers });
        return route.fulfill({ status: 200, contentType: "text/event-stream", body: sse(REPLIES[requests.length - 1]) });
    }
    return route.fulfill({ status: 204, body: "" });   // fonts, other CDNs
});

let passed = 0;
async function test(name, fn) { await fn(); passed++; console.log(`ok   ${name}`); }

await page.goto(ORIGIN + PAGE, { waitUntil: "load" });
await page.waitForFunction(() => document.getElementById("modal-passphrase"));
await page.fill("#modal-passphrase", PASS);
await page.click("#btn-modal-unlock");
await page.click("#btn-scratch");

async function send(text) {
    const before = requests.length;
    await page.fill("#user-input", text);
    await page.click("#btn-send");
    await page.waitForTimeout(600);
    assert.equal(requests.length, before + 1, "one API request per send");
}

await test("page has no errors after load", () => {
    assert.deepEqual(pageErrors, []);
});

await test("first reply: complete game lands in the editor, markers hidden, chips shown", async () => {
    await send("Make every wand glow red");
    const r = requests[0];
    assert.equal(r.body.model, "claude-sonnet-5-5");
    assert.equal(r.body.stream, true);
    assert.equal(r.headers["anthropic-beta"], "server-side-fallback-2026-07-01");
    assert.equal(r.body.system.length, 2);
    assert.ok(r.body.system[0].text.includes("# SmartPlayground Game Helper"));
    assert.ok(r.body.system[1].text.includes("The editor is empty"));
    const chat = await page.textContent("#chat-box");
    assert.ok(chat.includes("Every wand glows red"));
    assert.ok(!/\[(DEVICE|GAME_NAME|CHOICES):/.test(chat), "markers must be hidden");
    assert.ok(chat.includes("Code updated"));
    const chips = await page.$$eval(".choice-chips .starter-chip", els => els.map(e => e.textContent));
    assert.deepEqual(chips, ["Make it blink", "Add a sound"]);
});

await test("second request carries the editor code; snippet leaves the editor unchanged", async () => {
    await send("How do I make it blue?");
    const r = requests[1];
    assert.ok(r.body.system[1].text.includes('exit_tags_excluding("red_flash")'), "editor code sent");
    assert.ok(!r.body.system[1].cache_control, "session block is not cached");
    assert.equal(r.body.messages[0].role, "user");
    const chat = await page.textContent("#chat-box");
    assert.ok(chat.includes("This is a code snippet — your game was not changed."));
    const editorCode = await page.evaluate(async () => (await import("./js/editor.js")).getCode("wand"));
    assert.ok(editorCode.includes("leds.fill(RED)"), "editor still holds the full game");
});

await test("Advanced mode adds the addendum block", async () => {
    await page.evaluate(async () => (await import("./js/uiMode.js")).setUiMode("advanced"));
    await send("Explain the loop");
    const r = requests[2];
    assert.equal(r.body.system.length, 3);
    assert.ok(r.body.system[1].text.includes("# Advanced mode"));
});

await test("no page errors during the run", () => {
    assert.deepEqual(pageErrors, []);
});

await browser.close();
server.close();
console.log(`\n${passed} checks passed`);
