/**
 * prompt_eval.mjs — run teacher-style prompts against the real model with the
 * app's exact request, check each reply automatically, and write a Markdown
 * report for a person to read.
 *
 * Uses js/prompt/buildRequest.js and js/prompt/stream.js, so the request is
 * byte-for-byte what the app sends (minus per-teacher icon edits).
 *
 * Usage, from ChatBroadcast/:
 *   node tools/prompt_eval.mjs --dry-run            build every request, no API calls
 *   node tools/prompt_eval.mjs --self-test          run the automatic checks on canned replies
 *   ANTHROPIC_API_KEY=sk-ant-... node tools/prompt_eval.mjs [--out report.md] [--only id,id]
 *
 * Costs real API usage when not a dry run: about 20 requests, mostly cache
 * reads of the ~12k-token system prompt after the first.
 *
 * Automatic checks per reply (reported, never fatal):
 *   - every code block is a complete game for its [DEVICE:] role (validateGameCode,
 *     which includes the wand size limit)
 *   - icon display games name only existing icons; Splat games only known actions
 *   - no f-strings; no reserved ESP-NOW message types used as game messages
 *   - the case's own expectations: code expected or not, phrases required or forbidden
 * Exit code: 0 when every check passed, 1 otherwise, 2 on setup errors.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import {
    knowledgePaths, knowledgeText, buildSystemBlocks, buildRequestBody, requestHeaders,
    ADVANCED_KNOWLEDGE, CLAUDE_MODEL, CLAUDE_EFFORT,
} from "../js/prompt/buildRequest.js";
import { readMessageStream } from "../js/prompt/stream.js";
import { extractCodeBlocks, parseNfcCards, parseGameName, parseChoices, stripAllMarkers } from "../js/chat.js";
import { validateGameCode } from "../js/upload.js";
import { listSplatActions, unknownSplatActionsIn } from "../js/splat/splatActionCheck.js";
import { listIcons, missingIconsIn } from "../js/ledicons/iconLibrary.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const DRY = args.includes("--dry-run");
const SELF_TEST = args.includes("--self-test");
const outArg = args.indexOf("--out");
const OUT = outArg >= 0 ? args[outArg + 1] : "prompt_eval_report.md";
const onlyArg = args.indexOf("--only");
const ONLY = onlyArg >= 0 ? new Set(args[onlyArg + 1].split(",")) : null;

const WAND_GAME = readFileSync(resolve(ROOT, "tools/eval_fixtures/red_glow_wand.py"), "utf8");

/**
 * Test cases. `expect.code`: true = must write at least one complete file,
 * false = must not write any code block. `roles`: roles that must get a file.
 * `must` / `mustNot`: regexes over the visible prose (markers stripped).
 */
const CASES = [
    { id: "simple-wand", prompt: "Make the wand flash blue five times when the button is pressed",
      expect: { code: true, roles: ["wand"] } },
    { id: "vague", prompt: "make a fun game for my class",
      expect: { code: true, choices: true } },
    { id: "follow-up-slower", prompt: "make it slower", editor: { wand: WAND_GAME },
      expect: { code: true, roles: ["wand"], must: [], keepsFrom: { wand: "red_glow" } } },
    { id: "snippet-question", prompt: "which line makes it red?", editor: { wand: WAND_GAME },
      expect: { code: false } },
    { id: "red-x", prompt: "the wand shows a red X and beeps when I tap the game card",
      expect: { code: false, must: [/could not start|couldn't start|didn't start|did not start/i] } },
    { id: "red-x-with-code", prompt: "I sent the game and the wand shows a red X three times with low beeps. What's wrong?",
      editor: { wand: WAND_GAME.replace("batt=None):", "batt=None)") },
      expect: { code: true, roles: ["wand"] } },
    { id: "usb", prompt: "My computer won't connect to the box over USB",
      expect: { code: false, must: [/chrome|edge/i],
                mustNot: [/driver/i, /app store|play store|install (an|the) app/i] } },
    { id: "nfc-writing", prompt: "How do I put the game onto the cards?",
      expect: { code: false, must: [/box|dial/i], mustNot: [/phone|nfc tools|app store|play store/i] } },
    { id: "unknown-signal", prompt: "The wand lights are flashing purple and green in a spiral before the game even starts",
      expect: { code: false, must: [/don.?t know|not sure|team/i] } },
    { id: "off-topic", prompt: "Can you help me write my class newsletter?",
      expect: { code: false } },
    { id: "outputs", prompt: "Tell me what sorts of outputs are available",
      expect: { code: false, mustNot: [/GPIO|I2C|0x24/] } },
    { id: "display-picture", prompt: "Show a whale on the big display when a wand is shaken",
      expect: { code: true, roles: ["wand", "icon"] } },
    { id: "display-count", prompt: "Count how many times the class taps the star card and show it on the display so the kids can count",
      expect: { code: true, roles: ["icon"] } },
    { id: "splat", prompt: "When a kid jumps on the splat it turns green and barks",
      expect: { code: true, roles: ["splat"] } },
    { id: "splat-wand", prompt: "When someone presses the splat, every wand lights up the same color as the splat",
      expect: { code: true, roles: ["wand", "splat"] } },
    { id: "roles", prompt: "Freeze dance where my wand is the caller and the kids' wands are players",
      expect: { code: true, roles: ["wand"] } },
    { id: "teams-display", prompt: "Two teams race to tap the goal card, and the display shows which team got there first",
      expect: { code: true, roles: ["wand", "icon"] } },
    { id: "too-big", prompt: "Make a huge game with 20 different levels, each with its own animations, sounds and rules",
      expect: { code: true } },
    { id: "tilt", prompt: "Play a high note when the wand tilts left and a low note when it tilts right",
      expect: { code: true, roles: ["wand"] } },
    { id: "team-member", prompt: "I'm on the Tufts team. Why does the template poll NFC every 10 frames instead of every loop?",
      expect: { code: false, must: [/200|500|ms|millisecond/i] } },
    { id: "advanced-serial", advanced: true,
      prompt: "Serial shows:\n[FAIL] game load: red_glow (module red_glow)\nTraceback (most recent call last):\n  File \"red_glow.py\", line 9\nSyntaxError: invalid syntax",
      editor: { wand: WAND_GAME.replace("batt=None):", "batt=None)") },
      expect: { code: true, roles: ["wand"] } },
];

const RESERVED = ["stop", "start_game", "score", "splat_config", "battery", "scan_request",
                  "find_device", "status_poll", "status_report"];

function autoChecks(c, raw) {
    const problems = [];
    const shown = stripAllMarkers(raw);
    const blocks = extractCodeBlocks(raw);
    const e = c.expect;
    if (e.code === true && !blocks.length) problems.push("expected a game file, got no code block");
    if (e.code === false && blocks.length) problems.push(`expected no code, got ${blocks.length} block(s)`);
    for (const role of e.roles || []) {
        if (!blocks.some(b => b.role === role)) problems.push(`no [DEVICE: ${role}] file`);
    }
    for (const b of blocks) {
        const [ok, err] = validateGameCode(b.code, b.role);
        if (!ok) problems.push(`[${b.role}] ${err.replace(/\n/g, " ")}`);
        if (/\bf["']/.test(b.code)) problems.push(`[${b.role}] contains an f-string`);
        if (b.role === "icon") {
            const missing = missingIconsIn(b.code);
            if (missing.length) problems.push(`[icon] unknown icons: ${missing.join(", ")}`);
        }
        if (b.role === "splat") {
            const unknown = unknownSplatActionsIn(b.code);
            if (unknown.length) problems.push(`[splat] unknown actions: ${unknown.join(", ")}`);
        }
        for (const m of b.code.matchAll(/broadcast\(\s*\{[^}]*["']type["']\s*:\s*["']([a-z_]+)["']/g)) {
            if (RESERVED.includes(m[1])) problems.push(`[${b.role}] broadcasts reserved type "${m[1]}"`);
        }
    }
    if (blocks.length && !parseGameName(raw)) problems.push("no [GAME_NAME:] marker");
    if (e.choices && !parseChoices(raw)) problems.push("no [CHOICES:] marker");
    for (const re of e.must || []) if (!re.test(shown)) problems.push(`missing ${re}`);
    for (const re of e.mustNot || []) if (re.test(shown)) problems.push(`should not mention ${re}`);
    for (const [role, needle] of Object.entries(e.keepsFrom || {})) {
        const b = blocks.find(x => x.role === role);
        if (b && !b.code.includes(needle)) problems.push(`[${role}] lost "${needle}" from the existing game`);
    }
    return { problems, blocks, shown };
}

function proseWords(shown) {
    return shown.replace(/```[\s\S]*?```/g, "").split(/\s+/).filter(Boolean).length;
}

/** The automatic checks against canned replies: one good, one of each fault. */
function selfTest() {
    const game = WAND_GAME;
    const good = `**Glow!**\n[DEVICE: wand]\n\`\`\`python\n${game}\n\`\`\`\n[GAME_NAME: Red Glow]\n[CHOICES: "Faster"]`;
    const cases = [
        ["good reply passes", { expect: { code: true, roles: ["wand"], choices: true, keepsFrom: { wand: "red_glow" } } }, good, 0],
        ["missing role file", { expect: { code: true, roles: ["icon"] } }, good, 1],
        ["code when none expected", { expect: { code: false } }, good, 1],
        ["f-string and reserved type", { expect: { code: true } },
            good.replace("buz.confirm()", 'print(f"x{1}"); enow.broadcast({"type": "score"})'), 2],
        ["snippet block", { expect: { code: true } }, "[DEVICE: wand]\n```python\nleds.fill(RED)\n```\n[GAME_NAME: X]", 1],
        ["forbidden phrase", { expect: { code: false, mustNot: [/driver/i] } }, "Install the driver.", 1],
        ["unknown icon", { expect: { code: true } },
            "[DEVICE: icon]\n```python\nimport icon_store\ndef play(nfc, panel, enow):\n    icon_store.read_icon(\"no_such_icon_x\", into=panel.src)\n```\n[GAME_NAME: X]", 1],
    ];
    let bad = 0;
    for (const [name, c, reply, want] of cases) {
        const got = autoChecks(c, reply).problems;
        const ok = got.length === want;
        if (!ok) bad++;
        console.log(`${ok ? "ok  " : "FAIL"} ${name}: ${got.length} problem(s)${got.length ? " — " + got.join("; ") : ""}`);
    }
    return bad ? 1 : 0;
}

async function main() {
    if (SELF_TEST) return selfTest();
    const files = Object.fromEntries(knowledgePaths().map(p => [p, readFileSync(resolve(ROOT, p), "utf8")]));
    const knowledge = knowledgeText(files, listSplatActions());
    const icons = listIcons();
    const cases = CASES.filter(c => !ONLY || ONLY.has(c.id));
    const key = process.env.ANTHROPIC_API_KEY;
    if (!DRY && !key) {
        console.error("ANTHROPIC_API_KEY is not set. Use --dry-run to build requests without calling the API.");
        process.exit(2);
    }

    const rows = [];
    const details = [];
    let failures = 0;
    for (const c of cases) {
        const editorCode = c.editor || {};
        const system = buildSystemBlocks({
            knowledge, advanced: files[ADVANCED_KNOWLEDGE], advancedMode: !!c.advanced, icons, editorCode,
        });
        const body = buildRequestBody({ system, history: [{ role: "user", content: c.prompt }] });
        if (DRY) {
            const chars = system.reduce((n, b) => n + b.text.length, 0);
            console.log(`${c.id.padEnd(18)} ${system.length} blocks, ${chars} system chars (~${Math.round(chars / 4)} tokens)`);
            continue;
        }
        const t0 = Date.now();
        const resp = await fetch("https://api.anthropic.com/v1/messages", {
            method: "POST", headers: requestHeaders(key), body: JSON.stringify(body),
        });
        if (!resp.ok) {
            const err = await resp.text();
            console.error(`${c.id}: HTTP ${resp.status} ${err}`);
            process.exit(2);
        }
        const r = await readMessageStream(resp);
        const totalMs = Date.now() - t0;
        const { problems, blocks, shown } = r.error
            ? { problems: [`stream error: ${JSON.stringify(r.error)}`], blocks: [], shown: "" }
            : autoChecks(c, r.text);
        if (r.stopReason !== "end_turn") problems.push(`stop_reason ${r.stopReason}`);
        if (problems.length) failures++;
        const sizes = blocks.map(b => `${b.role} ${Buffer.byteLength(b.code)} B`).join(", ") || "—";
        rows.push(`| ${c.id} | ${problems.length ? "**FAIL**" : "pass"} | ${r.firstTextMs ?? "—"} | ${totalMs} | ` +
                  `${r.usage.cache_read_input_tokens ?? 0} | ${r.usage.output_tokens ?? 0} | ${proseWords(shown)} | ${sizes} |`);
        details.push(`## ${c.id}\n\n**Prompt:** ${c.prompt.replace(/\n/g, "  \n")}\n\n` +
            (problems.length ? `**Problems:**\n${problems.map(p => `- ${p}`).join("\n")}\n\n` : "") +
            `**NFC cards:** ${JSON.stringify(parseNfcCards(r.text))} · **Name:** ${parseGameName(r.text) ?? "—"} · ` +
            `**Choices:** ${JSON.stringify(parseChoices(r.text))}\n\n<details><summary>Reply</summary>\n\n${r.text}\n\n</details>\n`);
        console.log(`${problems.length ? "FAIL" : "pass"} ${c.id} (${totalMs} ms)${problems.length ? ": " + problems.join("; ") : ""}`);
    }
    if (DRY) return 0;

    const report = `# Prompt eval — ${new Date().toISOString().slice(0, 10)}\n\n` +
        `Model \`${CLAUDE_MODEL}\`, effort \`${CLAUDE_EFFORT}\`. ${cases.length - failures}/${cases.length} passed the automatic checks. ` +
        `Automatic checks do not judge tone or teaching quality — read the replies.\n\n` +
        `| Case | Checks | First text ms | Total ms | Cache read tok | Output tok | Prose words | Files |\n` +
        `|---|---|---|---|---|---|---|---|\n${rows.join("\n")}\n\n${details.join("\n")}`;
    writeFileSync(OUT, report);
    console.log(`\nReport written to ${OUT}`);
    return failures ? 1 : 0;
}

process.exit(await main());
