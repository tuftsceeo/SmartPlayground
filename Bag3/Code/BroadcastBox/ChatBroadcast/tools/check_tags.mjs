/**
 * check_tags.mjs — verify the tag extractor against every game source.
 *
 * Tag derivation drives both the send checklist and the tags pushed to the
 * Box, so a wrong list here means a teacher writes the wrong cards. Run from
 * this directory:  node tools/check_tags.mjs
 * Exits non-zero on any mismatch.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
import { extractGameTags } from "../js/gameTags.js";
import { buildHardwareReqs } from "../js/hardware.js";
import { EXAMPLES } from "../js/examples.js";

// Expected game-specific tags per source file.
//
// Only a game still on the pre-Device signature declares a COMMANDS set for
// the extractor to read. A play(dev) game reads cards through dev.event(),
// so its source names no tag set at all and its card list reaches the
// checklist from the reply's [NFC_CARDS:] marker or an example's own tags
// list instead. Those files are expected to yield nothing here.
const EXPECTED = {
    cooking: ["tomato","milk","cheese","flour","egg","butter","sugar","cooking"],
    gestures: ["red","green","blue","play"],
    freeze_dance: ["caller","player","go","freeze","rejoin"],
    color_quest: [],
    melody: [], nfc_sound: [], jump: [], jumpin: [], rainbow: [],
    shake: [], shake_rainbow: [], simpleicecream: [], multiicecream: [],
    sound: [], finddevice: [],
};

const GAMES = resolve(HERE, "../../../Wand Module");
let fail = 0;
const eq = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

console.log("== wand game sources ==");
for (const [name, want] of Object.entries(EXPECTED)) {
    const src = readFileSync(`${GAMES}/${name}.py`, "utf8");
    const { declared, tags, unresolved } = extractGameTags(src);
    // A game with no COMMANDS assignment legitimately has no game-specific
    // tags to find; it is only an error if we expected some.
    const ok = eq(tags, want) && unresolved.length === 0 && (declared || !want.length);
    if (!ok) fail++;
    console.log(`${ok ? "ok  " : "FAIL"} ${name.padEnd(16)} ${JSON.stringify(tags)}` +
        (declared ? "" : "  (no COMMANDS declared)") +
        (unresolved.length ? ` unresolved=${JSON.stringify(unresolved)}` : "") +
        (ok ? "" : `\n     want ${JSON.stringify(want)}`));
}

console.log("\n== example gallery (code now loads from Simulator/vendor/games) ==");
const VENDOR = resolve(HERE, "../../../Simulator/vendor/games");
for (const ex of EXAMPLES) {
    const src = readFileSync(`${VENDOR}/${ex.vendorGame}.py`, "utf8");
    const { declared, tags, unresolved } = extractGameTags(src);
    const reqs = buildHardwareReqs({ code: src, gameName: "My " + ex.name, declared: ex.tags });
    if (unresolved.length) fail++;
    console.log(`${unresolved.length ? "FAIL" : "ok  "} ${ex.id.padEnd(14)} ` +
        `${declared ? JSON.stringify(tags) : "(no COMMANDS declared)"}` +
        (unresolved.length ? ` unresolved=${JSON.stringify(unresolved)}` : ""));
    console.log(`     sent -> ${JSON.stringify(reqs.tags)}`);
}

// A game that declares no COMMANDS falls back to the example's `tags`, which
// name the built-in it was copied from. Writing that card launches the
// built-in, not the teacher's copy -- so it must not reach the checklist.
console.log("\n== wand built-ins never reach the card list ==");
{
    const jumpin = EXAMPLES.find((e) => e.id === "jumpin");
    const src = readFileSync(`${VENDOR}/${jumpin.vendorGame}.py`, "utf8");
    const tags = buildHardwareReqs({
        code: src, gameName: "My Jump In", declared: jumpin.tags,
    }).tags;
    const ok = !tags.includes("jumpin");
    if (!ok) fail++;
    console.log(`${ok ? "ok  " : "FAIL"} jumpin example drops the built-in tag  ${JSON.stringify(tags)}`);

    // ...but a reserved word a game reads as its own card does belong on the
    // list: melody clears with an "erase" card, which is a reserved slug and
    // not a card the wand acts on.
    const mel = EXAMPLES.find((e) => e.id === "melody");
    const melTags = buildHardwareReqs({
        code: readFileSync(`${VENDOR}/${mel.vendorGame}.py`, "utf8"),
        gameName: "My Melody", declared: mel.tags,
    }).tags;
    const ok2 = melTags.includes("erase") && melTags.includes("backspace");
    if (!ok2) fail++;
    console.log(`${ok2 ? "ok  " : "FAIL"} melody keeps its own card names  ${JSON.stringify(melTags)}`);
}

console.log(fail ? `\n${fail} FAILURES` : "\nall expectations met");
process.exit(fail ? 1 : 0);
