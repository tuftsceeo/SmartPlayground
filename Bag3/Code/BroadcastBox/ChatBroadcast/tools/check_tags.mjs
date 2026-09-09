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

// Expected game-specific tags, from the plan's pinned table.
const EXPECTED = {
    melody: ["note_c","note_d","note_e","note_f","note_g","note_a","note_b","note_c_high","erase","melody","backspace"],
    nfc_sound: ["note_c","note_d","note_e","note_f","note_g","note_a","note_b"],
    cooking: ["tomato","milk","cheese","flour","egg","butter","sugar","cooking"],
    gestures: ["red","green","blue","play"],
    freeze_dance: ["caller","player","go","freeze","rejoin"],
    jump: [], jumpin: [], rainbow: [], shake: [], shake_rainbow: [],
    simpleicecream: [], multiicecream: [], sound: [],
};

const MW = resolve(HERE, "../../MockWand");
let fail = 0;
const eq = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());

console.log("== MockWand sources ==");
for (const [name, want] of Object.entries(EXPECTED)) {
    const src = readFileSync(`${MW}/${name}.py`, "utf8");
    const { declared, tags, unresolved } = extractGameTags(src);
    // A game with no COMMANDS assignment (jumpin) legitimately has no
    // game-specific tags; it is only an error if we expected some.
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

console.log(fail ? `\n${fail} FAILURES` : "\nall expectations met");
process.exit(fail ? 1 : 0);
