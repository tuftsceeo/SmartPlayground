/**
 * Game-code validation and the push to the Broadcast Box.
 *
 * A game's play() signature is fixed per device role: a wand game only ever
 * runs on wands and an icon display game only ever runs on icon displays, so
 * each role names its own hardware. ROLE_SIGNATURES is the client-side copy
 * of what each device's main.py actually calls; keep it in step with
 * MockWand/main.py's _launch_game() and IconDisplay/main.py's.
 */

/** Required play() parameter names, in order, keyed by device role. */
export const ROLE_SIGNATURES = {
    wand: ['nfc', 'leds', 'buz', 'accel', 'i2c', 'enow', 'batt'],
    icon: ['nfc', 'panel', 'enow'],
};

/** Human-readable `def play(...)` line for a role, used in error text. */
export function signatureFor(role) {
    const names = ROLE_SIGNATURES[role];
    if (!names) return null;
    // batt is the one parameter main.py tolerates a default on.
    const shown = names.map(n => (n === 'batt' ? 'batt=None' : n));
    return `def play(${shown.join(', ')})`;
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
 * Check a game file against its role's signature.
 * @param {string} code
 * @param {string} role  a key of ROLE_SIGNATURES
 * @returns {[boolean, string|null]} [ok, error message]
 */
export function validateGameCode(code, role) {
    const expected = ROLE_SIGNATURES[role];
    if (!expected) {
        return [false, `Unknown device role "${role}".`];
    }
    const sig = signatureFor(role);
    const params = playParams(code);
    if (params === null) {
        return [false, `Missing ${sig} function.`];
    }
    const missing = expected.filter(p => !params.has(p));
    if (missing.length > 0) {
        return [false, `play() is missing parameters: ${missing.join(', ')}\nExpected: ${sig}`];
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
