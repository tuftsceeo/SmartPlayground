/**
 * Splat action names: the list the system prompt carries, and the static
 * check a Splat game gets before it is sent.
 *
 * The names come from splatActions.js, generated from the wand's
 * MockWand/lib/splat_api.py -- see tools/sync_splat_actions.py.
 */
import { COLORS, NOTES, SOUNDS } from './splatActions.js';

const BY_METHOD = {
    color: new Set(COLORS),
    note: new Set(NOTES),
    sound: new Set(SOUNDS),
};
const ALL = new Set([...COLORS, ...NOTES, ...SOUNDS]);

/** Every action name by category, for the system prompt. */
export function listSplatActions() {
    return { colors: [...COLORS], notes: [...NOTES], sounds: [...SOUNDS] };
}

/**
 * Action names a Splat game passes as string literals that the device does
 * not have, sorted and de-duplicated.
 *
 * Checks the first argument of any `.color("x")`, `.note("x")` and
 * `.sound("x")` call against that category, and every string literal inside
 * a `.play([...])` list against all three, and a `.color("x", "part")`
 * second argument against "inner" / "outer". The receiver is not checked, so
 * `net.splat(i).color("x")`, `net.local.unit(0)` and an alias such as
 * `s = net.splat(i); s.color("x")` are all covered; `buz.play(name)` takes no
 * list and is not matched. Names built at run time (a
 * variable, a table lookup) cannot be checked here; the device prints
 * `[ERR]` for those.
 */
export function unknownSplatActionsIn(code) {
    if (!code) return [];
    const bad = new Set();
    for (const m of code.matchAll(/\.(color|note|sound)\s*\(\s*["']([^"']*)["']/g)) {
        if (!BY_METHOD[m[1]].has(m[2])) bad.add(m[2]);
    }
    for (const m of code.matchAll(/\.color\s*\(\s*["'][^"']*["']\s*,\s*(?:part\s*=\s*)?["']([^"']*)["']/g)) {
        if (m[1] !== 'inner' && m[1] !== 'outer') bad.add(m[1]);
    }
    for (const m of code.matchAll(/\.play\s*\(\s*\[([^\]]*)\]/g)) {
        for (const s of m[1].matchAll(/["']([^"']*)["']/g)) {
            if (!ALL.has(s[1])) bad.add(s[1]);
        }
    }
    return [...bad].sort();
}
