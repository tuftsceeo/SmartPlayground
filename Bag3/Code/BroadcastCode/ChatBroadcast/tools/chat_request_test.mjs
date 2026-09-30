/**
 * chat_request_test.mjs — offline checks for the chat request pipeline.
 *
 * No network and no API key. Covers: every knowledge file exists and loads
 * into the system blocks in order; block layout and cache markers; the
 * history window; the SSE reader against a synthetic stream; marker
 * parsing; and the complete-file check that decides whether a code block
 * may replace the editor. Run from ChatBroadcast/:
 *   node tools/chat_request_test.mjs
 * Exits non-zero on the first failure.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import assert from "node:assert/strict";

import {
    knowledgePaths, knowledgeText, buildSystemBlocks, buildRequestBody,
    historyWindow, ADVANCED_KNOWLEDGE, CLAUDE_MODEL,
} from "../js/prompt/buildRequest.js";
import { readMessageStream } from "../js/prompt/stream.js";
import { extractCodeBlocks, parseChoices, stripAllMarkers, parseNfcCards, parseGameName } from "../js/chat.js";
import { validateGameSignature, validateGameCode, MAX_WAND_GAME_BYTES } from "../js/upload.js";
import { listSplatActions } from "../js/splat/splatActionCheck.js";
import { drawStarterIdeas, STARTER_IDEAS, GUIDED_STEPS, guidedPrompt } from "../js/starterIdeas.js";
import { ROLES } from "../js/roles.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
let passed = 0;
function test(name, fn) {
    return Promise.resolve().then(fn).then(() => { passed++; console.log(`ok   ${name}`); });
}

export function loadFilesFromDisk() {
    return Object.fromEntries(knowledgePaths().map(p => [p, readFileSync(resolve(ROOT, p), "utf8")]));
}

const files = loadFilesFromDisk();
const knowledge = knowledgeText(files, listSplatActions());

await test("every knowledge file is non-empty", () => {
    for (const p of knowledgePaths()) assert.ok(files[p].length > 200, `${p} looks empty`);
});

await test("knowledge text contains every file, policy first", () => {
    assert.ok(knowledge.indexOf("# SmartPlayground Game Helper") < knowledge.indexOf("# Device: Wand"));
    for (const h of ["# Platform rules", "# Game patterns", "# Troubleshooting",
                     "# Device: Wand", "# Device: Icon display", "# Device: Splat Companion",
                     "SPLAT ACTION NAMES"]) {
        assert.ok(knowledge.includes(h), `missing ${h}`);
    }
    assert.ok(!knowledge.includes("# Advanced mode"), "advanced.md must not be in the cached base");
});

await test("missing knowledge file throws", () => {
    const partial = { ...files };
    delete partial["knowledge/policy.md"];
    assert.throws(() => knowledgeText(partial, listSplatActions()), /policy\.md/);
});

await test("system blocks: simple mode has 2 blocks, advanced 3; only stable ones cached", () => {
    const base = { knowledge, advanced: files[ADVANCED_KNOWLEDGE], icons: ["whale", "ready"],
                   editorCode: { wand: "def play(nfc, leds, buz, accel, i2c, enow, batt=None):\n    pass", icon: "" } };
    const simple = buildSystemBlocks({ ...base, advancedMode: false });
    assert.equal(simple.length, 2);
    assert.ok(simple[0].cache_control && !simple[1].cache_control);
    assert.ok(simple[1].text.includes("whale, ready"));
    assert.ok(simple[1].text.includes("[DEVICE: wand]"));
    assert.ok(!simple[1].text.includes("[DEVICE: icon]"), "empty roles are not sent");
    const adv = buildSystemBlocks({ ...base, advancedMode: true });
    assert.equal(adv.length, 3);
    assert.ok(adv[1].cache_control && adv[1].text.includes("# Advanced mode"));
});

await test("empty editor says so", () => {
    const b = buildSystemBlocks({ knowledge, advanced: "", advancedMode: false, icons: [], editorCode: {} });
    assert.ok(b[1].text.includes("The editor is empty"));
});

await test("history window starts on a user turn", () => {
    const h = [];
    for (let i = 0; i < 11; i++) h.push({ role: i % 2 ? "assistant" : "user", content: String(i) });
    const w = historyWindow(h, 10);
    assert.equal(w[0].role, "user");
    assert.equal(w.at(-1).content, "10");
    const body = buildRequestBody({ system: [], history: h });
    assert.equal(body.model, CLAUDE_MODEL);
    assert.equal(body.stream, true);
    assert.equal(body.messages[0].role, "user");
});

function sseResponse(events) {
    const text = events.map(e => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join("");
    // Split mid-event to exercise buffering across chunks.
    const bytes = new TextEncoder().encode(text);
    const cut = Math.floor(bytes.length / 3);
    const chunks = [bytes.slice(0, cut), bytes.slice(cut, cut * 2), bytes.slice(cut * 2)];
    return new Response(new ReadableStream({
        start(c) { for (const ch of chunks) c.enqueue(ch); c.close(); },
    }));
}

await test("SSE reader accumulates text, stop reason and usage", async () => {
    const seen = [];
    const r = await readMessageStream(sseResponse([
        { type: "message_start", message: { usage: { input_tokens: 10, cache_read_input_tokens: 9000 } } },
        { type: "content_block_start", index: 0, content_block: { type: "thinking", thinking: "" } },
        { type: "content_block_stop", index: 0 },
        { type: "content_block_start", index: 1, content_block: { type: "text", text: "" } },
        { type: "content_block_delta", index: 1, delta: { type: "text_delta", text: "**Jump** " } },
        { type: "content_block_delta", index: 1, delta: { type: "text_delta", text: "game" } },
        { type: "message_delta", delta: { stop_reason: "end_turn" }, usage: { output_tokens: 5 } },
        { type: "message_stop" },
    ]), t => seen.push(t));
    assert.equal(r.text, "**Jump** game");
    assert.equal(r.stopReason, "end_turn");
    assert.equal(r.usage.cache_read_input_tokens, 9000);
    assert.equal(r.usage.output_tokens, 5);
    assert.deepEqual(seen, ["**Jump** ", "**Jump** game"]);
    assert.equal(r.error, null);
});

await test("SSE reader surfaces an error event", async () => {
    const r = await readMessageStream(sseResponse([
        { type: "error", error: { type: "overloaded_error", message: "Overloaded" } },
    ]));
    assert.equal(r.error.type, "overloaded_error");
});

const WAND_GAME = [
    "import time",
    "def play(nfc, leds, buz, accel, i2c, enow, batt=None):",
    "    pass",
].join("\n");

await test("complete game passes; snippet and wrong-device code do not", () => {
    assert.ok(validateGameSignature(WAND_GAME, "wand")[0]);
    assert.ok(!validateGameSignature("leds.fill(RED)", "wand")[0]);
    assert.ok(!validateGameSignature("def play(nfc, panel, enow):\n    pass", "wand")[0]);
    assert.ok(validateGameSignature("def play(nfc, panel, enow):\n    pass", "icon")[0]);
});

await test("over-size wand game passes the signature check but not the send check", () => {
    const big = WAND_GAME + "\n" + "# x\n".repeat(MAX_WAND_GAME_BYTES / 4 + 10);
    assert.ok(validateGameSignature(big, "wand")[0]);
    assert.ok(!validateGameCode(big, "wand")[0]);
});

await test("markers parse and strip", () => {
    const reply = [
        "**Frogs hop!**",
        "[DEVICE: wand]",
        "```python", WAND_GAME, "```",
        '[NFC_CARDS: "red", "blue"]',
        "[GAME_NAME: Jumping Frogs]",
        '[CHOICES: "Make it slower", "Add a winning song"]',
    ].join("\n");
    assert.deepEqual(parseNfcCards(reply), ["red", "blue"]);
    assert.equal(parseGameName(reply), "Jumping Frogs");
    assert.deepEqual(parseChoices(reply), ["Make it slower", "Add a winning song"]);
    const shown = stripAllMarkers(reply);
    assert.ok(!/\[(DEVICE|NFC_CARDS|GAME_NAME|CHOICES):/.test(shown));
    const blocks = extractCodeBlocks(reply);
    assert.equal(blocks.length, 1);
    assert.equal(blocks[0].role, "wand");
});

await test("starter draws always include a non-wand idea; ideas name real roles", () => {
    const keys = new Set(ROLES.map(r => r.key));
    for (const idea of STARTER_IDEAS) for (const r of idea.roles) assert.ok(keys.has(r), `${idea.text}: ${r}`);
    let seed = 1;
    const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < 500; i++) {
        const d = drawStarterIdeas(4, rand);
        assert.equal(d.length, 4);
        assert.equal(new Set(d).size, 4);
        assert.ok(d.some(x => x.roles.some(r => r !== "wand")));
    }
});

await test("guided prompt uses every answer", () => {
    const p = guidedPrompt(GUIDED_STEPS.map(s => s.options[1]));
    for (const s of GUIDED_STEPS) assert.ok(p.includes(s.options[1].says));
});

console.log(`\n${passed} checks passed`);
