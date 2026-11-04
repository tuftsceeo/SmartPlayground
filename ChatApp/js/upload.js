export function validateJumpin(code) {
    const expectedParams = new Set(['nfc', 'leds', 'buz', 'accel', 'i2c']);
    let hasPlay = false;

    for (const line of code.split('\n')) {
        const stripped = line.trim();
        if (stripped.startsWith('def play(') || stripped.startsWith('def play (')) {
            hasPlay = true;
            try {
                const paramsStr = stripped.split('(')[1].split(')')[0];
                const params = new Set(paramsStr.split(',').map(p => p.trim()));
                const missing = [...expectedParams].filter(p => !params.has(p));
                if (missing.length > 0) {
                    return [false, `play() is missing parameters: ${missing.join(', ')}\nExpected: def play(nfc, leds, buz, accel, i2c)`];
                }
            } catch {
                return [false, "Could not parse play() parameters."];
            }
            break;
        }
    }

    if (!hasPlay) {
        return [false, "Missing def play(nfc, leds, buz, accel, i2c) function.\nmain.py imports: from jumpin import play"];
    }
    return [true, null];
}

export async function uploadToSlot(uboard, code, slot, addMsg) {
    const filename = `jumpin${slot}.py`;
    const encoder = new TextEncoder();
    const codeBytes = encoder.encode(code);

    // base64 encode
    let binary = '';
    codeBytes.forEach(b => binary += String.fromCharCode(b));
    const encoded = btoa(binary);

    const CHUNK_SIZE = 512;
    const chunks = [];
    for (let i = 0; i < encoded.length; i += CHUNK_SIZE) {
        chunks.push(encoded.slice(i, i + CHUNK_SIZE));
    }

    if (chunks.length <= 1) {
        const cmd =
            `import ubinascii\n` +
            `_d=ubinascii.a2b_base64('${encoded}')\n` +
            `f=open('${filename}','wb')\n` +
            `f.write(_d)\n` +
            `f.close()\n` +
            `print('${filename} uploaded:',len(_d),'bytes')\n` +
            `del _d\n`;
        await uboard.paste(cmd);
    } else {
        await uboard.paste(`import ubinascii\nf=open('${filename}','wb')\n`);
        await sleep(200);
        for (const chunk of chunks) {
            await uboard.paste(`f.write(ubinascii.a2b_base64('${chunk}'))\n`);
            await sleep(100);
        }
        await uboard.paste(`f.close()\nprint('${filename} uploaded: ${codeBytes.length} bytes in ${chunks.length} chunks')\n`);
    }

    addMsg(`Uploaded as ${filename}. Resetting...`, "system");
    await sleep(500);
    await uboard.paste('import machine; machine.reset()');
    uboard.focus();
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
