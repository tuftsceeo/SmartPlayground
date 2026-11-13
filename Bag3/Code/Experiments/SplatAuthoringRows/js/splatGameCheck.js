/**
 * Send-time checks for a wand game's Splat declarations and its use of
 * `net` and `splats` (SplatAuthoringRows/wand/lib/lobby_game.py and
 * splatpair.py; SPEC section 6).
 *
 * Three Splat shapes, one per declaration:
 *   SPLATS_LOCAL = 1 or 2  a solo wand driving its own paired Splats; play() takes splats=None last.
 *   SPLAT_HOST = True      a Splat host group game; SPLATS_MIN (1..4), optional SPLATS_MAX; play() takes net=None.
 *   SPLATS_MIN alone       a plain wand lobby with no Splats; play() takes net=None.
 *
 * The device reads the declarations with getattr() and int() after the
 * module loads, and passes `net` or `splats` only to a play() that names
 * them. Each problem listed here is one the wand would hit only when a
 * child taps the card: a load failure, a refusal, or a None `net` or `splats`.
 */

/** Pairing slots on a Splat host wand: Wand Module/lib/pairing.py HOST_MAX_SPLATS. */
export const HOST_MAX_SPLATS = 4;

/** Top-level `NAME = value` (comment stripped), or undefined. */
function constant(code, name) {
    const m = code.match(new RegExp(`^${name}\\s*=\\s*([^#\\n]*?)\\s*(?:#.*)?$`, 'm'));
    return m ? m[1] : undefined;
}

/** Integer value of a literal, or null when it is not a plain int literal. */
function intLiteral(v) {
    return /^\d+$/.test(v) ? Number(v) : null;
}

/** Parameter names of `def play(...)`, defaults stripped; null if absent. */
function playParams(code) {
    const m = code.match(/^def\s+play\s*\(([^)]*)\)/m);
    if (!m) return null;
    return m[1].split(',').map(p => p.split('=')[0].trim()).filter(Boolean);
}

/**
 * The code with play()'s def line, comments and string literals removed,
 * so that a name match in what is left is a real use of the name.
 */
function codeBody(code) {
    return code.replace(/^def\s+play\s*\([^)]*\)/m, '')
        .replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, '""')
        .replace(/#[^\n]*/g, '')
        .replace(/"[^"\n]*"|'[^'\n]*'/g, '""');
}

/** True when `name` appears in `body` as a bare name (not an attribute). */
function usesName(body, name) {
    return new RegExp(`(^|[^\\w.])${name}\\b`, 'm').test(body);
}

/** `def play(..., splats=None)` as the 8th and last parameter. */
const SPLATS_LAST = /^def\s+play\s*\([^)]*\bsplats\s*=\s*None\s*\)/m;

/** A `return` on, or within two lines after, a `("end",)` comparison or value. */
const RETURNS_ON_END = /\(\s*["']end["']\s*,\s*\)[^\n]*(?:\n[^\n]*){0,2}?\breturn\b/;

/**
 * Problems with a wand game's Splat declarations, as teacher-readable
 * sentences; empty when there are none.
 * @param {string} code  the wand file
 * @returns {string[]}
 */
export function splatGameProblems(code) {
    if (!code) return [];
    const out = [];
    const params = playParams(code) || [];
    const hasNet = params.includes('net');
    const local = constant(code, 'SPLATS_LOCAL');
    const min = constant(code, 'SPLATS_MIN');
    const max = constant(code, 'SPLATS_MAX');
    const host = constant(code, 'SPLAT_HOST');
    const playersMin = constant(code, 'PLAYERS_MIN');
    const body = codeBody(code);
    const usesNet = usesName(body, 'net');
    const usesSplats = usesName(body, 'splats');
    const usesNetSplat = /(^|[^\w.])net\s*\.\s*splat\s*\(/m.test(body);
    const isHost = host === 'True';
    const declared = local !== undefined || min !== undefined || isHost;

    // A game with no Splat declaration gets net and splats as None.
    if (usesNet && !hasNet && local === undefined) {
        out.push('The game uses `net` but play() has no `net=None` parameter.');
    }
    if (!declared && usesNet && hasNet) {
        out.push('The game uses `net` but declares no Splats (SPLATS_LOCAL, SPLATS_MIN or SPLAT_HOST), so net is None.');
    }
    if (!declared && usesSplats) {
        out.push('The game uses `splats` but declares no SPLATS_LOCAL, so splats is None.');
    }

    // Solo wand: SPLATS_LOCAL, driven through the splats argument.
    if (local !== undefined) {
        const n = intLiteral(local);
        if (n !== 1 && n !== 2) {
            out.push(`SPLATS_LOCAL must be 1 or 2; it is ${local || 'empty'}.`);
        }
        for (const [name, v] of [['SPLATS_MIN', min], ['SPLATS_MAX', max], ['SPLAT_HOST', host]]) {
            if (v !== undefined) out.push(`A solo Splat game (SPLATS_LOCAL) must not declare ${name}.`);
        }
        if (!(params.length === 8 && params[7] === 'splats' && SPLATS_LAST.test(code))) {
            out.push('A solo Splat game (SPLATS_LOCAL) needs `splats=None` as play()\'s last (8th) parameter.');
        }
        if (usesNet) {
            out.push('A solo Splat game (SPLATS_LOCAL) must not use `net`; it has no lobby.');
        }
    }

    if (host !== undefined && host !== 'True' && host !== 'False') {
        out.push(`SPLAT_HOST must be True or False; it is ${host || 'empty'}.`);
    }
    if (isHost && min === undefined) {
        out.push('A Splat host game (SPLAT_HOST = True) needs SPLATS_MIN.');
    }
    if ((min !== undefined || isHost) && !hasNet) {
        out.push('A Splat game (SPLATS_MIN or SPLAT_HOST) needs `net=None` as play()\'s last parameter.');
    }
    if (playersMin !== undefined) {
        if (!isHost) {
            out.push('PLAYERS_MIN is only read in a Splat host game (SPLAT_HOST = True).');
        } else {
            const p = intLiteral(playersMin);
            if (p === null || p < 1) {
                out.push(`PLAYERS_MIN must be a whole number of at least 1; it is ${playersMin || 'empty'}.`);
            }
        }
    }

    // Splat host games (Wand Module/lib/splat_host.py): the host holds
    // every Splat, up to HOST_MAX_SPLATS, and only the host drives them.
    if (isHost) {
        for (const [name, v] of [['SPLATS_MIN', min], ['SPLATS_MAX', max]]) {
            const n = v === undefined ? null : intLiteral(v);
            if (n !== null && n > HOST_MAX_SPLATS) {
                out.push(`${name} (${n}) is more than a Splat host holds (${HOST_MAX_SPLATS}).`);
            }
        }
        if (params.includes('splats')) {
            out.push('A Splat host game takes `net`, not `splats`; splats is only for SPLATS_LOCAL games.');
        }
        if (!RETURNS_ON_END.test(code)) {
            out.push('A Splat host game must return when net.poll() reports ("end",).');
        }
        if (usesNetSplat && !code.includes('is_host')) {
            out.push('net.splat() is used but the game never checks is_host; only the host wand may drive the Splats.');
        }
    }
    if (usesNetSplat && min !== undefined && !isHost) {
        out.push('net.splat() is not available in a plain wand lobby (SPLATS_MIN without SPLAT_HOST = True), which has no Splats.');
    }

    if (max !== undefined && min === undefined) {
        out.push('SPLATS_MAX is set without SPLATS_MIN.');
    }
    if (min !== undefined) {
        // net.poll() reads the radio itself (lobby_game.py): an
        // enow.poll() in a Splat host or lobby game takes lobby frames away from it.
        if (/(^|[^\w.])enow\s*\.\s*poll\s*\(/m.test(body)) {
            out.push('A Splat game must not call enow.poll(): net.poll() reads the radio and returns ("end",) on stop.');
        }
        const n = intLiteral(min);
        if (n === null || n < 1) {
            out.push(`SPLATS_MIN must be a whole number of at least 1; it is ${min || 'empty'}.`);
        }
        if (max !== undefined && max !== 'None') {
            const x = intLiteral(max);
            if (x === null || x < 1) {
                out.push(`SPLATS_MAX must be a whole number or None; it is ${max || 'empty'}.`);
            } else if (n !== null && x < n) {
                out.push(`SPLATS_MAX (${x}) is smaller than SPLATS_MIN (${n}).`);
            }
        }
    }
    return out;
}
