export function validateJumpin(code) {
    const expectedParams = new Set(['nfc', 'leds', 'buz', 'accel', 'i2c', 'enow']);
    let hasPlay = false;

    for (const line of code.split('\n')) {
        const stripped = line.trim();
        if (stripped.startsWith('def play(') || stripped.startsWith('def play (')) {
            hasPlay = true;
            try {
                const paramsStr = stripped.split('(')[1].split(')')[0];
                const params = new Set(paramsStr.split(',').map(p => p.trim()).filter(Boolean));
                const missing = [...expectedParams].filter(p => !params.has(p));
                if (missing.length > 0) {
                    return [false, `play() is missing parameters: ${missing.join(', ')}\nExpected: def play(nfc, leds, buz, accel, i2c, enow)`];
                }
            } catch {
                return [false, "Could not parse play() parameters."];
            }
            break;
        }
    }

    if (!hasPlay) {
        return [false, "Missing def play(nfc, leds, buz, accel, i2c, enow) function.\nmain.py imports: from jumpin import play"];
    }
    return [true, null];
}

export async function uploadPayload(device, code, onProgress) {
    if (!device?.isConnected()) {
        return { ok: false, error: "Connect your Broadcast Box first." };
    }
    const [valid, err] = validateJumpin(code);
    if (!valid) {
        return { ok: false, error: err };
    }
    try {
        return await device.sendGame(code, {}, onProgress);
    } catch (e) {
        return { ok: false, error: e.message || String(e) };
    }
}
