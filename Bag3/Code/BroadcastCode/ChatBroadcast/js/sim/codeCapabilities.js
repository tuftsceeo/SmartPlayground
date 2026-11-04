/**
 * Scan generated MicroPython for wand API usage.
 * Used to build the plain-language "you'll need" hardware checklist shown
 * at the connect / send-confirm stage (see checklist.js).
 */

export function scanCapabilities(code) {
    const src = code || "";

    const usesLeds = /\bleds\.(off|solid|fill|show_shape|show_pattern)\s*\(/.test(src);
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
        usesLeds,
        usesBuzzer,
        usesAccel,
        usesButton,
        usesNfc,
        nfcTagCount,
        hasCode: src.trim().length > 0 && !src.trim().startsWith("# AI-generated"),
    };
}
