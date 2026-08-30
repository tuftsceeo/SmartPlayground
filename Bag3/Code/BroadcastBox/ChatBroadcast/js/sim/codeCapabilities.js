/**
 * Scan generated MicroPython for wand API usage.
 * Shared by wand simulation and component checklist.
 */

function parseRgbTuple(text) {
    const m = text.match(/\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/);
    if (!m) return null;
    return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function rgbCss(rgb) {
    if (!rgb) return null;
    return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

const NAMED = {
    RED: [255, 0, 0],
    GREEN: [0, 200, 0],
    BLUE: [0, 80, 255],
    YELLOW: [255, 220, 0],
    PURPLE: [160, 0, 200],
    PINK: [255, 80, 160],
    WHITE: [255, 255, 255],
    ORANGE: [255, 140, 0],
    TEAL: [0, 180, 160],
};

export function scanCapabilities(code) {
    const src = code || "";
    const ledColors = [];

    const fillRe = /leds\.fill\s*\(\s*([^)]+)\)/g;
    let m;
    while ((m = fillRe.exec(src))) {
        const rgb = parseRgbTuple(m[1]) || NAMED[m[1].trim().toUpperCase()];
        const css = rgbCss(rgb);
        if (css) ledColors.push(css);
    }

    const assignRe = /leds(?:\.np)?\s*\[\s*\w+\s*\]\s*=\s*(\([^)]+\)|[A-Z_]+)/g;
    while ((m = assignRe.exec(src))) {
        const rgb = parseRgbTuple(m[1]) || NAMED[m[1].trim().toUpperCase()];
        const css = rgbCss(rgb);
        if (css) ledColors.push(css);
    }

    for (const name of Object.keys(NAMED)) {
        if (new RegExp("\\b" + name + "\\b").test(src) && /leds\./.test(src)) {
            const css = rgbCss(NAMED[name]);
            if (css && !ledColors.includes(css)) ledColors.push(css);
        }
    }

    const usesBuzzer = /\bbuz\.(beep|tone|play|melody)\b/.test(src) || /\bbuzzer\b/i.test(src);
    const usesAccel =
        /\baccel\.(read|get)\b/.test(src) ||
        /\bmagnitude\b/.test(src) ||
        /\bshake\b/i.test(src) ||
        /\bfreefall\b/i.test(src);
    const usesButton =
        /\bbtn\.value\b/.test(src) ||
        /\b_check_button\b/.test(src) ||
        /\bBUTTON_PIN\b/.test(src) ||
        /\bPin\(BUTTON_PIN/.test(src);
    const usesNfc =
        /\bnfc\./.test(src) ||
        /\bNfcReader\b/.test(src) ||
        /\bread_command\b/.test(src) ||
        /\b_EXIT_TAGS\b/.test(src);

    let nfcTagCount = 0;
    const noteTags = src.match(/note_[a-g](?:_high)?/gi);
    if (noteTags) nfcTagCount = new Set(noteTags.map((t) => t.toLowerCase())).size;

    return {
        ledColors: ledColors.slice(0, 8),
        usesBuzzer,
        usesAccel,
        usesButton,
        usesNfc,
        nfcTagCount,
        hasCode: src.trim().length > 0 && !src.trim().startsWith("# AI-generated"),
    };
}
