/**
 * Game-code validation and the push to the Broadcast Box.
 *
 * A game's play() signature is fixed per device role: a wand game only ever
 * runs on wands and an icon display game only ever runs on icon displays, so
 * each role names its own hardware. roles.js is the client-side copy of
 * what each device's main.py actually calls; keep it in step with
 * MockWand/main.py's _launch_game(), IconDisplay/main.py's and
 * SplatCompanion/Companion/main.py's.
 */
import { ROLES as ROLE_TABLE, signatureFor } from './roles.js';

/** Required play() parameter names, in order, keyed by device role. */
export const ROLE_SIGNATURES = Object.fromEntries(
    ROLE_TABLE.map(r => [r.key, r.signature]));

/**
 * Parameters a role's play() may omit and still run.
 *
 * `batt` became a real wand parameter long after games had been written
 * against six, and MockWand/main.py's _start_play() still calls those the way
 * they were written. Refusing to SEND one would strand every game a teacher
 * generated before the change, on a device that can run it perfectly well.
 * New code should still declare it -- the knowledge files ask for it -- but a
 * missing one is not a reason to block a send.
 */
const OPTIONAL_PARAMS = Object.fromEntries(
    ROLE_TABLE.map(r => [r.key, r.optional]));

export { signatureFor };

/**
 * Largest wand game file, in UTF-8 bytes, that ChatBroadcast will send.
 *
 * The wand compiles a pulled game in its running heap, which needs one
 * contiguous block. Measured on the MockWand (2026-09-26, see
 * docs_and_design/2026-09-26-eum-bench-results.md): 33,004 B compiles,
 * 56,926 B fails. The threshold between them has not been narrowed, so
 * this sits just under the largest size known to work.
 */
export const MAX_WAND_GAME_BYTES = 32000;

/** Size of `code` in UTF-8 bytes, as it is written to the device. */
export function codeBytes(code) {
    return new TextEncoder().encode(code || '').length;
}

/**
 * Parse the parameter names out of a `def play(...)` line.
 * Defaults are stripped, so `batt=None` reads as `batt`.
 * @returns {Set<string>|null} null when the code has no play() at all.
 */
function playParams(code) {
    for (const line of code.split('\n')) {
        const stripped = line.trim();
        if (!stripped.startsWith('def play(') && !stripped.startsWith('def play (')) continue;
        const paramsStr = stripped.slice(stripped.indexOf('(') + 1, stripped.lastIndexOf(')'));
        return new Set(
            paramsStr
                .split(',')
                .map(p => p.split('=')[0].trim())
                .filter(Boolean)
        );
    }
    return null;
}

/**
 * Check a game file against its role's play() signature only.
 * @param {string} code
 * @param {string} role  a key of ROLE_SIGNATURES
 * @returns {[boolean, string|null]} [ok, error message]
 */
export function validateGameSignature(code, role) {
    const expected = ROLE_SIGNATURES[role];
    if (!expected) {
        return [false, `Unknown device role "${role}".`];
    }
    const sig = signatureFor(role);
    const params = playParams(code);
    if (params === null) {
        return [false, `Missing ${sig} function.`];
    }
    const optional = OPTIONAL_PARAMS[role] || [];
    const missing = expected.filter(p => !params.has(p) && !optional.includes(p));
    if (missing.length > 0) {
        return [false, `play() is missing parameters: ${missing.join(', ')}\nExpected: ${sig}`];
    }
    return [true, null];
}

/**
 * Check a game file before sending: its role's signature, and for the
 * wand the size the wand can load.
 * @param {string} code
 * @param {string} role  a key of ROLE_SIGNATURES
 * @returns {[boolean, string|null]} [ok, error message]
 */
export function validateGameCode(code, role) {
    const sigCheck = validateGameSignature(code, role);
    if (!sigCheck[0]) return sigCheck;
    if (role === 'wand') {
        const size = codeBytes(code);
        if (size > MAX_WAND_GAME_BYTES) {
            return [false, `This wand game is too big for the wand's memory `
                + `(${Math.round(size / 1000)} KB; the limit is ${MAX_WAND_GAME_BYTES / 1000} KB). `
                + `Ask the assistant to make it shorter.`];
        }
    }
    return [true, null];
}

/** Wand-role shorthand, kept for callers that only ever send wand code. */
export function validateJumpin(code) {
    return validateGameCode(code, 'wand');
}

export async function uploadPayload(device, code, onProgress, opts = {}) {
    // App passes link.state; only live/sending may push.
    const product = opts.deviceProduct || "Broadcast Box";
    if (opts.linkState) {
        if (opts.linkState !== "live" && opts.linkState !== "sending") {
            return { ok: false, error: `Connect your ${product} first.` };
        }
    } else if (!device?.isConnected()) {
        return { ok: false, error: `Connect your ${product} first.` };
    }
    const [valid, err] = validateGameCode(code, opts.role || 'wand');
    if (!valid) {
        return { ok: false, error: err };
    }
    try {
        const meta = { ...(opts.meta || {}) };
        if (!meta.deviceLabel) {
            meta.deviceLabel = opts.deviceShort || "Box";
        }
        return await device.sendGame(code, meta, onProgress);
    } catch (e) {
        return { ok: false, error: e.message || String(e) };
    }
}
