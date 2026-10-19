/**
 * Send-time checks for a wand game's Splat declarations and its use of
 * `net` (MockWand/lib/solo.py, lib/party.py; SPEC section 6).
 *
 * The device reads SPLATS_LOCAL / SPLATS_MIN / SPLATS_MAX with getattr()
 * and int() after the module loads, and passes `net` only to a play() that
 * takes 8 parameters. Each problem listed here is one the wand would hit
 * only when a child taps the card: a load failure, a refusal, or a None
 * `net`.
 */

/** Pairing slots per wand: MockWand/lib/pairing.py MAX_SPLATS. */
export const MAX_SPLATS = 2;

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
    // The name `net` anywhere outside play()'s def line, comments and
    // string literals; this covers aliases such as `n = net`.
    const body = code.replace(/^def\s+play\s*\([^)]*\)/m, '')
        .replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, '""')
        .replace(/#[^\n]*/g, '')
        .replace(/"[^"\n]*"|'[^'\n]*'/g, '""');
    const usesNet = /(^|[^\w.])net\b/.test(body);

    if (usesNet && !hasNet) {
        out.push('The game uses `net` but play() has no `net=None` parameter.');
    }
    if ((local !== undefined || min !== undefined) && !hasNet) {
        out.push('A Splat game (SPLATS_LOCAL or SPLATS_MIN) needs `net=None` as play()\'s last parameter.');
    }
    if (local !== undefined && min !== undefined) {
        out.push('The game declares both SPLATS_LOCAL and SPLATS_MIN; a game is either solo or party.');
    }
    if (local !== undefined) {
        const n = intLiteral(local);
        if (n === null || n < 1 || n > MAX_SPLATS) {
            out.push(`SPLATS_LOCAL must be a whole number from 1 to ${MAX_SPLATS} (a wand pairs with at most ${MAX_SPLATS} Splats); it is ${local || 'empty'}.`);
        }
        if (/\bnet\s*\.\s*send\s*\(/.test(code)) {
            out.push('A solo game (SPLATS_LOCAL) cannot call net.send(): there are no other wands.');
        }
    }
    if (max !== undefined && min === undefined) {
        out.push('SPLATS_MAX is set without SPLATS_MIN.');
    }
    if (min !== undefined) {
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
