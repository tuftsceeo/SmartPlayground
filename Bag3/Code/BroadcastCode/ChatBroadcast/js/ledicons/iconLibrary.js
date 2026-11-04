/**
 * The named 16x16 icons a teacher can use, and the files they become on the
 * icon display.
 *
 * Icons are stored as flat linear-PWM-duty RGB arrays -- 768 values, row-major
 * from top-left -- which is what the device's icons/<name>.py holds and what
 * the Icon Maker calls "authored" values. They are NOT sRGB: convert at the
 * boundary with ledColor.js's predictLedAppearance() before putting one on a
 * screen.
 *
 * An icon resolves through three layers, nearest first:
 *
 *   1. the OPEN GAME's own edits   -- in memory, saved with the game
 *   2. the starter palette         -- read-only, shared, localStorage
 *   3. DEFAULT_ICONS               -- read-only, ships with the app
 *
 * Layer 1 is the important one. Editing an icon changes it for THIS GAME
 * ONLY: a game saved last week keeps the picture it was saved with, and
 * correcting `apple` here cannot reach back and alter a game that already
 * shipped with the old one. Games are already isolated on the device
 * (/flash/games/<slug>_icons/<name>.py); this makes the browser agree.
 *
 * Layer 2 is what the shared `chatbroadcast.ledicons` map became. It is read
 * as a starting point and never written to, so the edits already in it stay
 * available to open and copy from without being able to change anything
 * retroactively.
 */
import { DEFAULT_ICONS } from './defaultIcons.js';

export const W = 16;
export const H = 16;
export const N = W * H;

/** The legacy shared map. Read-only now -- see the layer note above. */
const STARTER_KEY = 'chatbroadcast.ledicons';

/**
 * Icon names are the device's rule, from icon_store.safe_name(): lowercase
 * letters, digits and underscore, not starting with a digit, <= 24 chars.
 */
const NAME_RE = /^[a-z_][a-z0-9_]*$/;
export const MAX_NAME_LEN = 24;

/** Module names on the display that an icon must not collide with. */
const RESERVED = [
    'main', 'boot', 'icon_matrix', 'icon_store', 'icon_server', 'json_link',
    'code_puller', 'pull_flag', 'display_tags',
];

export function isValidIconName(name) {
    return typeof name === 'string'
        && name.length > 0
        && name.length <= MAX_NAME_LEN
        && NAME_RE.test(name)
        && !RESERVED.includes(name);
}

function readStarter() {
    try {
        return JSON.parse(localStorage.getItem(STARTER_KEY) || '{}');
    } catch {
        return {};
    }
}

/**
 * Curate the shared starter palette.
 *
 * Read-only from inside ChatBroadcast -- a game must never be able to change
 * what another game draws. These exist for the STANDALONE Icon Maker, where
 * there is no open game and this palette is the whole library; without them
 * a standalone save would land in an in-memory map and vanish on reload.
 */
export function saveStarterIcon(name, duty) {
    if (!isValidIconName(name)) {
        throw new Error(`"${name}" is not a valid icon name (lowercase letters, digits and _, max ${MAX_NAME_LEN}).`);
    }
    if (!Array.isArray(duty) || duty.length !== N * 3) {
        throw new Error(`icon data must be ${N * 3} values, got ${duty?.length}`);
    }
    const starter = readStarter();
    starter[name] = duty.map((v) => Math.max(0, Math.min(255, Math.round(v))));
    localStorage.setItem(STARTER_KEY, JSON.stringify(starter));
    notify();
}

export function revertStarterIcon(name) {
    const starter = readStarter();
    delete starter[name];
    localStorage.setItem(STARTER_KEY, JSON.stringify(starter));
    notify();
}

/** True when the starter palette has its own version of this icon. */
export function isStarterIcon(name) {
    return Object.prototype.hasOwnProperty.call(readStarter(), name);
}

/**
 * The open game's own icons, {name: duty[768]}. Owned by app.js, which loads
 * it when a game is opened and hands it back when one is saved. Held in
 * memory rather than localStorage precisely so it cannot outlive the game it
 * belongs to.
 */
let gameIcons = {};

const listeners = new Set();
function notify() {
    listeners.forEach((cb) => {
        try { cb(); } catch (e) { console.error('[icons] listener threw', e); }
    });
}

/** Subscribe to edits of the open game's icons. Returns an unsubscribe fn. */
export function onIconsChange(cb) {
    listeners.add(cb);
    return () => listeners.delete(cb);
}

/** Load a game's icons. Called with {} for a new game. */
export function setGameIcons(map) {
    gameIcons = {};
    for (const [name, duty] of Object.entries(map || {})) {
        if (Array.isArray(duty) && duty.length === N * 3) gameIcons[name] = duty.slice();
    }
    notify();
}

/** The open game's icons, for saving with it. Only what this game edited. */
export function getGameIcons() {
    const out = {};
    for (const [name, duty] of Object.entries(gameIcons)) out[name] = duty.slice();
    return out;
}

/** Every icon name available to the open game, across all three layers. */
export function listIcons() {
    return [...new Set([
        ...Object.keys(DEFAULT_ICONS),
        ...Object.keys(readStarter()),
        ...Object.keys(gameIcons),
    ])].sort();
}

/**
 * One icon's duty bytes, or null if there is no such icon.
 * The open game's version shadows the starter palette, which shadows the default.
 */
export function getIcon(name) {
    if (gameIcons[name]) return gameIcons[name].slice();
    const starter = readStarter();
    if (starter[name]) return starter[name].slice();
    if (DEFAULT_ICONS[name]) return DEFAULT_ICONS[name].slice();
    return null;
}

/** True when THIS GAME has its own version of the icon. */
export function isCustom(name) {
    return Object.prototype.hasOwnProperty.call(gameIcons, name);
}

/**
 * Store an icon under a name.
 * @param {string} name
 * @param {number[]} duty  768 linear-duty values
 */
export function saveIcon(name, duty) {
    if (!isValidIconName(name)) {
        throw new Error(`"${name}" is not a valid icon name (lowercase letters, digits and _, max ${MAX_NAME_LEN}).`);
    }
    if (!Array.isArray(duty) || duty.length !== N * 3) {
        throw new Error(`icon data must be ${N * 3} values, got ${duty?.length}`);
    }
    gameIcons[name] = duty.map((v) => Math.max(0, Math.min(255, Math.round(v))));
    notify();
}

/**
 * Drop this game's version. The starter palette's or the shipped default of
 * the same name comes back; an icon that only ever existed in this game
 * disappears. Affects this game alone.
 */
export function revertIcon(name) {
    delete gameIcons[name];
    notify();
}

/**
 * The text of icons/<name>.py as the display stores it.
 *
 * icon_store.read_icon() is a text parser, not an importer: it reads any line
 * starting with "(" as an (r,g,b) triple, in order, with SIZE making the file
 * self-describing. This writes the same shape icon_store.write_icon() does.
 */
export function iconFileText(name) {
    const duty = getIcon(name);
    if (!duty) throw new Error(`no icon named "${name}"`);
    const lines = [
        `# ${name} -- 16x16 linear PWM duty bytes, row-major from top-left.`,
        `SIZE = (${W}, ${H})`,
        'ICON = (',
    ];
    for (let y = 0; y < H; y++) {
        const parts = [];
        for (let x = 0; x < W; x++) {
            const o = (y * W + x) * 3;
            parts.push(`(${duty[o]}, ${duty[o + 1]}, ${duty[o + 2]})`);
        }
        lines.push('    ' + parts.join(', ') + ',');
    }
    lines.push(')', '');
    return lines.join('\n');
}

/**
 * Icon names a display game refers to, read statically from its source.
 *
 * Matches the two ways a game names one: a call to icon_store.read_icon, and
 * any string literal that happens to be a known icon name (which covers a
 * table like TEAM_ICON = {"green": "tree"}). Strings that are not icons in
 * the library are ignored, so this over-reads nothing.
 */
export function iconNamesIn(code) {
    if (!code) return [];
    const known = new Set(listIcons());
    const found = new Set();
    for (const m of code.matchAll(/read_icon\s*\(\s*["']([a-z0-9_]+)["']/g)) {
        found.add(m[1]);
    }
    for (const m of code.matchAll(/["']([a-z_][a-z0-9_]{0,23})["']/g)) {
        if (known.has(m[1])) found.add(m[1]);
    }
    return [...found].sort();
}

/**
 * Names a display game refers to that the library does not have.
 * These are reported to the teacher rather than sent as blanks -- a game that
 * draws nothing is the hardest failure to diagnose from across a room.
 */
export function missingIconsIn(code) {
    const known = new Set(listIcons());
    const named = new Set();
    for (const m of code.matchAll(/read_icon\s*\(\s*["']([a-z0-9_]+)["']/g)) {
        named.add(m[1]);
    }
    return [...named].filter((n) => !known.has(n)).sort();
}
