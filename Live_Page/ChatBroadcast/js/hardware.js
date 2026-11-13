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
        open: isLobbyGame(code),
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

/** True when the code is a lobby game: any number of wands can join. */
export function isLobbyGame(code) {
    return /SPLATS_MIN|lobby_game|lobbyGame/.test(code || "");
}

const DEVICE_ICONS = { wand: "wand", display: "iconDisplay", station: "station", splat: "splat", nfc: "nfcCard" };

/**
 * The devices a game needs, in words: [{kind, label}], in the order wands,
 * icon displays, stations, Splats, NFC tags. One device is named without a
 * number ("wand", "icon display"); two or more are counted ("3 wands").
 * Wands are always listed; a lobby game with no set count says "wands".
 * The rest are listed only at 1 or more.
 *
 * Shared by the send overlay's pills and the My games / Example games
 * cards, so both say the same thing.
 * @param {{wands?: number, open?: boolean, displays?: number, stations?: number, splats?: number, nfcTags?: number}} n
 */
export function deviceNeeds({ wands = 1, open = false, displays = 0, stations = 0, splats = 0, nfcTags = 0 } = {}) {
    const say = (count, one, many) => (count === 1 ? one : `${count} ${many}`);
    const out = [];
    out.push({ kind: "wand", label: wands >= 2 ? `${wands} wands` : open ? "wands" : "wand" });
    if (displays >= 1) out.push({ kind: "display", label: say(displays, "icon display", "icon displays") });
    if (stations >= 1) out.push({ kind: "station", label: say(stations, "station", "stations") });
    if (splats >= 1) out.push({ kind: "splat", label: say(splats, "Splat", "Splats") });
    if (nfcTags >= 1) out.push({ kind: "nfc", label: say(nfcTags, "NFC tag", "NFC tags") });
    return out;
}

/** "2 wands · icon display · 3 NFC tags", first letter capitalized. */
export function deviceLine(needs) {
    const text = needs.map((n) => n.label).join(" · ");
    return text ? text[0].toUpperCase() + text.slice(1) : "";
}

/** Requirement pills for the send overlay: [{icon, label}], from deviceNeeds. */
export function requirementPills(reqs) {
    if (!reqs) return [];
    const baseline = baselineTags(reqs.slug);
    const needs = deviceNeeds({
        wands: reqs.minWands || 1,
        open: reqs.open,
        displays: reqs.displays || 0,
        stations: (reqs.stations || []).length,
        splats: reqs.splats || 0,
        nfcTags: (reqs.tags || []).filter((t) => !baseline.includes(t)).length,
    });
    return needs.map((n) => ({ icon: DEVICE_ICONS[n.kind], label: n.label[0].toUpperCase() + n.label.slice(1) }));
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
