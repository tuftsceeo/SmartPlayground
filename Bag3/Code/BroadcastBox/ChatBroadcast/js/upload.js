/**
 * Check a role file before it is written to a device.
 *
 * A game file is `def play(dev)` and nothing else: main.py builds the Device
 * and passes it in. This catches the one mistake that makes a game fail at
 * launch rather than at a tap.
 *
 * @param {string} code the file's source
 * @returns {[boolean, string|null]} ok, and why not
 */
export function validateRoleFile(code) {
    for (const line of code.split('\n')) {
        const stripped = line.trim();
        if (!stripped.startsWith('def play(') && !stripped.startsWith('def play (')) continue;
        const params = stripped
            .slice(stripped.indexOf('(') + 1, stripped.lastIndexOf(')'))
            .split(',')
            .map((p) => p.trim())
            .filter(Boolean);
        if (params.length === 1 && params[0] === 'dev') return [true, null];
        return [false, `play() takes one argument, dev — this file has (${params.join(', ')})`];
    }
    return [false, 'Missing def play(dev) — every game file defines it.'];
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
    const [valid, err] = validateRoleFile(code);
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
