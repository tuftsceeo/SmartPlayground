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
 * DEFAULT_ICONS ships with the app; anything a teacher edits or adds is kept
 * in localStorage on top of it, so a default can be corrected without losing
 * the original.
 */
import { DEFAULT_ICONS } from './defaultIcons.js';

export const W = 16;
export const H = 16;
export const N = W * H;

const STORE_KEY = 'chatbroadcast.ledicons';

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

function readOverrides() {
    try {
        return JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    } catch {
        return {};
    }
}

function writeOverrides(obj) {
    localStorage.setItem(STORE_KEY, JSON.stringify(obj));
}

/** Every icon name available, defaults and teacher edits together. */
export function listIcons() {
    return [...new Set([...Object.keys(DEFAULT_ICONS), ...Object.keys(readOverrides())])].sort();
}

/**
 * One icon's duty bytes, or null if there is no such icon.
 * A teacher's version shadows the default of the same name.
 */
export function getIcon(name) {
    const over = readOverrides();
    if (over[name]) return over[name].slice();
    if (DEFAULT_ICONS[name]) return DEFAULT_ICONS[name].slice();
    return null;
}

/** True when this icon has been edited or added by the teacher. */
export function isCustom(name) {
    return Object.prototype.hasOwnProperty.call(readOverrides(), name);
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
    const over = readOverrides();
    over[name] = duty.map((v) => Math.max(0, Math.min(255, Math.round(v))));
    writeOverrides(over);
}

/**
 * Drop a teacher's version. A default of the same name comes back; an icon
 * that only ever existed here disappears.
 */
export function revertIcon(name) {
    const over = readOverrides();
    delete over[name];
    writeOverrides(over);
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
