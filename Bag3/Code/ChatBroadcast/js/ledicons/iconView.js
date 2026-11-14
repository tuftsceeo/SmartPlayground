/**
 * Icon helpers for the workspace Icons view: which icons a game uses, which
 * one a display game starts on, and drawing one as the panel would show it.
 *
 * The renderer is the Icon Maker's, reached through iconmaker/js/pipeline/
 * rather than reimplemented -- it models the device's truncating LUT and the
 * additive bloom of real LEDs.
 */
import { renderPreview } from '../../iconmaker/js/pipeline/preview.js';
import {
    getIcon, getGameIcons, isCustom, iconNamesIn, missingIconsIn, W, H,
} from './iconLibrary.js';

/** Library flat duty -> the 256 [r,g,b] triples renderPreview wants. */
function toTriples(flat) {
    const out = new Array(W * H);
    for (let i = 0; i < W * H; i++) {
        out[i] = [flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]];
    }
    return out;
}

const BLANK = new Array(W * H).fill(null).map(() => [0, 0, 0]);

/**
 * The icon a display game shows first.
 *
 * Games name their resting picture in a module constant -- IDLE_ICON or
 * ICON_READY by convention -- so that is preferred; otherwise the first icon
 * the file mentions at all. Returns null when the game names none.
 */
export function startingIcon(code) {
    if (!code) return null;
    const named = code.match(/^\s*(?:IDLE_ICON|ICON_READY|ICON_IDLE)\s*=\s*["']([a-z0-9_]+)["']/m);
    if (named && getIcon(named[1])) return named[1];
    const all = iconNamesIn(code);
    return all.length ? all[0] : null;
}

/**
 * Draw one named icon into a canvas at a given intensity.
 * An unknown name draws a dark panel and says so, rather than silently
 * showing the last icon.
 *
 * @returns {{ok: boolean, error?: string}}
 */
export function drawIcon(canvas, name, intensity) {
    const flat = name ? getIcon(name) : null;
    if (!flat) {
        renderPreview(BLANK, intensity, canvas);
        return { ok: false, error: name ? `No icon named "${name}".` : 'This game names no icon.' };
    }
    renderPreview(toTriples(flat), intensity, canvas);
    return { ok: true };
}

/**
 * Every icon a game uses, each marked by where it comes from.
 *
 * The names are what the wand and display code mention (iconNamesIn, which
 * only reads known names, plus missingIconsIn for the read_icon() calls that
 * name nothing in the library) and every icon the game has its own version
 * of. status is 'custom' for this game's own version, 'missing' for a name
 * the library cannot resolve, otherwise 'built-in'.
 *
 * @param {string[]} codes  source files to scan (wand, display)
 * @returns {{name: string, status: 'built-in'|'custom'|'missing'}[]}
 */
export function gameIconEntries(codes) {
    const names = new Set(Object.keys(getGameIcons()));
    const missing = new Set();
    for (const code of codes) {
        if (!code) continue;
        iconNamesIn(code).forEach((n) => names.add(n));
        missingIconsIn(code).forEach((n) => { names.add(n); missing.add(n); });
    }
    return [...names].sort().map((name) => ({
        name,
        status: missing.has(name) ? 'missing' : isCustom(name) ? 'custom' : 'built-in',
    }));
}
