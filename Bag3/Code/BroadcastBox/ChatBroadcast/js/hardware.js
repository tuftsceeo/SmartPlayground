/**
 * What a game needs in the real world: wands, stations, NFC tags.
 *
 * One derived object so the send-confirm overlay can state requirements in
 * words instead of guessing three unrelated things in three places. Tags are
 * "baseline 2 + game-specific": every game on the Box needs a `getcode:<slug>`
 * pickup card and a `<slug>` play card (see the connection-and-library plan's
 * derived TAG_LIST), plus whatever tags the game itself reads.
 */

import { slugify } from "./gameName.js";

/** Tags every game needs, whatever it does. */
export function baselineTags(slug) {
    const s = slug || "game";
    return [`getcode:${s}`, s];
}

/**
 * @param {object}   opts
 * @param {string}   opts.code        current editor source
 * @param {string}   opts.gameName    pretty name (slugified for the baseline tags)
 * @param {string[]} opts.declared    tags declared by the game ([NFC_CARDS:] or an example)
 * @param {number}   opts.minWands    override; defaults to 1
 * @param {string[]} opts.stations    station names; empty until stations are implemented
 */
export function buildHardwareReqs({ code, gameName, declared, minWands, stations } = {}) {
    const slug = slugify(gameName || "") || "game";
    const specific = declared && declared.length ? declared : sniffTags(code);
    const tags = [];
    for (const t of [...baselineTags(slug), ...specific]) {
        if (t && !tags.includes(t)) tags.push(t);
    }
    return {
        minWands: minWands || 1,
        stations: stations || [],
        tags,
        declaredTags: declared && declared.length ? [...declared] : null,
    };
}

/**
 * The one code heuristic worth keeping: melody games name a tag per note.
 * Everything else must declare its tags -- guessing from word lists produced
 * checklists full of cards the game never reads.
 */
function sniffTags(code) {
    const notes = (code || "").match(/note_[a-g](?:_high)?/gi);
    if (!notes || notes.length < 2) return [];
    return [...new Set(notes.map((t) => t.toLowerCase()))];
}

/** Plain-language rows for the send-confirm overlay. */
export function formatHardwareReqs(reqs) {
    if (!reqs) return [];
    const rows = [];
    const w = reqs.minWands || 1;
    rows.push({ icon: "wand", label: w === 1 ? "at least 1 wand" : `at least ${w} wands` });
    if (reqs.stations && reqs.stations.length) {
        const n = reqs.stations.length;
        rows.push({
            icon: "cable",
            label: `${n} station${n === 1 ? "" : "s"} — ${reqs.stations.join(", ")}`,
        });
    }
    const n = (reqs.tags || []).length;
    if (n) {
        rows.push({ icon: "nfcCard", label: `${n} NFC tag${n === 1 ? "" : "s"}` });
    }
    return rows;
}
