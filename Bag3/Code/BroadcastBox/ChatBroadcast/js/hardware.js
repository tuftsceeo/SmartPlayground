/**
 * What a game needs in the real world: wands, stations, NFC tags.
 *
 * One derived object so the send-confirm overlay can state requirements in
 * words instead of guessing three unrelated things in three places. Tags are
 * "baseline 2 + game-specific": every game on the Box needs a `getcode:<slug>`
 * pickup card and a `<slug>` play card (see the connection-and-library plan's
 * derived TAG_LIST), plus whatever tags the game itself reads.
 */

import { slugify, FRAMEWORK_CARDS } from "./gameName.js";
import { extractGameTags } from "./gameTags.js";

/** Tags every game needs, whatever it does. */
export function baselineTags(slug) {
    const s = slug || "game";
    return [`getcode:${s}`, s];
}

/**
 * @param {object}   opts
 * @param {string}   opts.code        current editor source
 * @param {string}   opts.gameName    pretty name (slugified for the baseline tags)
 * @param {string[]} opts.declared    fallback tags ([NFC_CARDS:] or an example) for code
 *                                 that names no COMMANDS set of its own
 * @param {number}   opts.minWands    override; defaults to 1
 * @param {string[]} opts.stations    station names; empty until stations are implemented
 */
export function buildHardwareReqs({ code, gameName, declared, minWands, stations } = {}) {
    const slug = slugify(gameName || "") || "game";

    // The code's own COMMANDS set outranks everything: it is what the wand
    // will actually match a card against. `declared` only fills in for code
    // that names no such set, and the note sniff only for code that names
    // neither.
    const fromCode = extractGameTags(code);
    let specific;
    if (fromCode.declared) {
        specific = fromCode.tags;
    } else if (declared && declared.length) {
        specific = dropWandBuiltins(declared);
    } else {
        specific = sniffTags(code);
    }

    const tags = [];
    for (const t of [...baselineTags(slug), ...specific]) {
        if (t && !tags.includes(t)) tags.push(t);
    }
    return {
        minWands: minWands || 1,
        stations: stations || [],
        tags,
        declaredTags: declared && declared.length ? [...declared] : null,
        // Names in the COMMANDS expression that could not be reduced to tag
        // literals. Non-empty means the list above is probably short, which
        // the teacher must be told rather than left to discover at the Box.
        unresolved: fromCode.unresolved,
    };
}

/**
 * Strip names the wand itself acts on rather than handing to the game.
 *
 * Only ever applied to the `declared` fallback. An example's `tags` list names
 * the built-in it was copied from -- jumpin's is `["jumpin"]` -- and a card
 * saying that launches the built-in, not the teacher's copy. Their copy is
 * reachable through the baseline `getcode:<slug>` / `<slug>` pair instead.
 *
 * Only launch and control cards go: an ordinary word a game reads as its own
 * card ("erase", "done") stays on the list even though it is a reserved slug.
 */
function dropWandBuiltins(tags) {
    const reserved = new Set(FRAMEWORK_CARDS);
    return tags.filter((t) => !reserved.has(t));
}

/**
 * Last resort for code that declares no COMMANDS set at all. Everything else
 * must declare its tags -- guessing from word lists produced checklists full
 * of cards the game never reads.
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
    if (reqs.unresolved && reqs.unresolved.length) {
        rows.push({
            icon: "nfcCard",
            label: `tag list may be short — could not resolve ${reqs.unresolved.join(", ")}`,
        });
    }
    return rows;
}
