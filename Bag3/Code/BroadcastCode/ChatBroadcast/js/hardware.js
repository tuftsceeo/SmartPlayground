/**
 * What a game needs in the real world: wands, stations, NFC tags.
 *
 * One derived object so the send-confirm overlay can state requirements in
 * words instead of guessing three unrelated things in three places. Tags are
 * "baseline 2 + game-specific": every game on the Box needs a `getcode:<slug>`
 * pickup card and a `<slug>` play card (see the connection-and-library plan's
 * derived TAG_LIST), plus whatever tags the game itself reads.
 */

import { slugify, WAND_RESERVED } from "./gameName.js";
import { extractGameTags } from "./gameTags.js";

/** Tags every game needs, whatever it does. */
export function baselineTags(slug) {
    // Advisory text only: this app has no way to know a host's HOST_ID, so
    // it shows the bare "getcode:<slug>" form here. The bytes actually
    // written to a card come from the device's own menu (bdial_server.py /
    // bbox_server.py's _card_text()), which appends "@<host_id>" to any
    // getcode row at write time -- so the printed requirements card and
    // the physical card can legitimately differ by that suffix.
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
 * @param {number}   opts.displays    icon displays the game needs; defaults to 0
 * @param {number}   opts.splats      Splats the game needs; defaults to 0
 */
export function buildHardwareReqs({ code, gameName, declared, minWands, stations, displays, splats } = {}) {
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
        slug,
        minWands: minWands || 1,
        displays: displays || 0,
        splats: splats || 0,
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
 * Strip names that address a wand built-in rather than this game.
 *
 * Only ever applied to the `declared` fallback. An example's `tags` list names
 * the built-in it was copied from -- jumpin's is `["jumpin"]` -- and a card
 * saying that launches the built-in, not the teacher's copy. Their copy is
 * reachable through the baseline `getcode:<slug>` / `<slug>` pair instead.
 *
 * Never applied to names a game takes from its own COMMANDS set: melody
 * deliberately re-declares `melody` there as an in-game erase control, and
 * that card does belong on the list.
 */
function dropWandBuiltins(tags) {
    const reserved = new Set(WAND_RESERVED);
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

/**
 * Requirement pills for simple mode: [{icon, label}].
 *
 * Wands show only at 2 or more (there is always at least one). Icon displays,
 * NFC tags and Splats show only at 1 or more. The NFC count leaves out the
 * baseline `getcode:<slug>` and `<slug>` tags every game has.
 */
export function requirementPills(reqs) {
    if (!reqs) return [];
    const pills = [];
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    if ((reqs.minWands || 1) >= 2) {
        pills.push({ icon: "wand", label: plural(reqs.minWands, "wand", "wands") });
    }
    if ((reqs.displays || 0) >= 1) {
        pills.push({ icon: "iconDisplay", label: plural(reqs.displays, "icon display", "icon displays") });
    }
    const baseline = baselineTags(reqs.slug);
    const nfc = (reqs.tags || []).filter((t) => !baseline.includes(t)).length;
    if (nfc >= 1) pills.push({ icon: "nfcCard", label: plural(nfc, "NFC tag", "NFC tags") });
    if ((reqs.splats || 0) >= 1) {
        pills.push({ icon: "splat", label: plural(reqs.splats, "Splat", "Splats") });
    }
    return pills;
}

/** Tag names shown as a colored tile. */
export const TAG_COLORS = {
    red: { fill: "#ff3b3b", edge: "#ff3b3b", ink: "#fff" },
    orange: { fill: "#ff8a1f", edge: "#ff8a1f", ink: "#fff" },
    yellow: { fill: "#ffd23f", edge: "#e0a800", ink: "#231f2e" },
    green: { fill: "#22c35a", edge: "#22c35a", ink: "#fff" },
    blue: { fill: "#3b5bff", edge: "#3b5bff", ink: "#fff" },
    purple: { fill: "#c03bff", edge: "#c03bff", ink: "#fff" },
    pink: { fill: "#ff7ab8", edge: "#ff7ab8", ink: "#231f2e" },
    white: { fill: "#ffffff", edge: "#8b859a", ink: "#231f2e" },
};
const CONTROL_TAGS = /^(restart|reset|start|stop|exit|next|undo|again|new)$/;
const ROLE_TAGS = /^(code(maker|breaker)|player\w*|team\w*|x|o)$/;

/**
 * Sort tags into Roles, Colors and Controls, in that order; anything else
 * goes under Tags. PEER: Simulator/sim-room.js groupTags() holds a copy of
 * the same rules.
 * @param {string[]} tags
 * @returns {{name: string, tags: string[]}[]}
 */
export function groupTags(tags) {
    const buckets = { Roles: [], Colors: [], Controls: [], Tags: [] };
    for (const t of tags) {
        const key = ROLE_TAGS.test(t) ? "Roles" : t in TAG_COLORS ? "Colors" : CONTROL_TAGS.test(t) ? "Controls" : "Tags";
        buckets[key].push(t);
    }
    return Object.entries(buckets).filter(([, v]) => v.length).map(([name, list]) => ({ name, tags: list }));
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
