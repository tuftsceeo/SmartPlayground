/**
 * JS mirror of the 5x5 LED shape/letter/icon glyphs and color palette
 * defined in Bag3/Code/lib/leds.py, used to give the wand simulation a
 * best-effort per-pixel preview of what leds.show_shape()/.solid()/.fill()
 * calls will actually draw (see also Live_Page/wand_icons.html, which
 * renders the same tables for the printed teacher guide).
 *
 * Grid layout (row-major, index = row*5 + col):
 *    0  1  2  3  4
 *    5  6  7  8  9
 *   10 11 12 13 14
 *   15 16 17 18 19
 *   20 21 22 23 24
 */

// Palette values below are copied verbatim from leds.py. They are tuned
// for real NeoPixel hardware at low brightness, so on a screen they read
// as muddy/dim — apply the same display gain wand_icons.html uses
// (255/140) so on-screen colors are legible while staying true to hue.
const RAW_PALETTE = {
    OFF: [0, 0, 0],
    BLACK: [0, 0, 0],
    RED: [130, 0, 0],
    ROSE: [120, 10, 20],
    ORANGE: [120, 40, 0],
    AMBER: [120, 80, 0],
    YELLOW: [110, 120, 0],
    LIME: [50, 210, 0],
    GREEN: [0, 230, 0],
    TEAL: [0, 180, 100],
    CYAN: [0, 180, 240],
    BLUE: [0, 20, 255],
    INDIGO: [30, 0, 255],
    PURPLE: [50, 0, 250],
    MAGENTA: [120, 0, 160],
    WHITE: [140, 150, 150],
    PINK: [200, 80, 120],
    PEACH: [180, 120, 30],
    MINT: [30, 190, 50],
    SKY: [60, 150, 250],
    RED_DIM: [65, 0, 0],
    GREEN_DIM: [0, 115, 0],
    BLUE_DIM: [0, 20, 127],
    YELLOW_DIM: [55, 60, 0],
    WHITE_DIM: [70, 75, 75],
    ORANGE_DIM: [60, 20, 0],
    AMBER_DIM: [60, 40, 0],
    PINK_DIM: [100, 40, 60],
    PURPLE_DIM: [25, 0, 125],
};

const DISPLAY_GAIN = 255 / 140;

function scaleForDisplay(rgb) {
    return rgb.map((c) => Math.min(255, Math.round(c * DISPLAY_GAIN)));
}

export const PALETTE = Object.fromEntries(
    Object.entries(RAW_PALETTE).map(([name, rgb]) => [name, scaleForDisplay(rgb)])
);

// Numbers
export const SHAPES = {
    SHAPE_0: [2, 3, 6, 9, 11, 14, 16, 19, 22, 23],
    SHAPE_1: [2, 3, 8, 13, 18, 23],
    SHAPE_2: [2, 3, 6, 9, 13, 17, 21, 22, 23, 24],
    SHAPE_3: [1, 2, 3, 4, 9, 12, 13, 14, 19, 21, 22, 23, 24],
    SHAPE_4: [1, 4, 6, 9, 11, 12, 13, 14, 19, 24],
    SHAPE_5: [2, 3, 4, 6, 11, 12, 13, 14, 19, 21, 22, 23, 24],
    SHAPE_6: [1, 2, 3, 4, 6, 11, 12, 13, 14, 16, 19, 21, 22, 23, 24],
    SHAPE_7: [1, 2, 3, 4, 9, 13, 17, 21],
    SHAPE_8: [1, 2, 3, 4, 6, 9, 12, 13, 16, 19, 21, 22, 23, 24],
    SHAPE_9: [1, 2, 3, 4, 6, 9, 11, 12, 13, 14, 19, 21, 22, 23, 24],

    // Letters
    SHAPE_A: [0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 15, 19, 20, 24],
    SHAPE_B: [0, 1, 2, 3, 5, 9, 10, 11, 12, 13, 14, 15, 19, 20, 21, 22, 23],
    SHAPE_C: [1, 2, 3, 5, 10, 15, 21, 22, 23],
    SHAPE_D: [0, 1, 2, 3, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23],
    SHAPE_E: [0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 15, 20, 21, 22, 23, 24],
    SHAPE_F: [0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 15, 20],
    SHAPE_G: [1, 2, 3, 5, 10, 13, 14, 15, 19, 21, 22, 23, 24],
    SHAPE_H: [1, 4, 6, 9, 11, 12, 13, 14, 16, 19, 21, 24],
    SHAPE_I: [1, 2, 3, 7, 12, 17, 21, 22, 23],
    SHAPE_J: [1, 2, 3, 4, 8, 13, 16, 18, 21, 22, 23],
    SHAPE_K: [0, 3, 5, 7, 10, 11, 15, 17, 20, 23],
    SHAPE_L: [0, 5, 10, 15, 20, 21, 22, 23],
    SHAPE_M: [0, 4, 5, 6, 8, 9, 10, 12, 14, 15, 19, 20, 24],
    SHAPE_N: [0, 4, 5, 6, 9, 10, 12, 14, 15, 18, 19, 20, 24],
    SHAPE_O: [0, 1, 2, 3, 4, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23, 24],
    SHAPE_P: [0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 15, 20],
    SHAPE_Q: [1, 2, 3, 5, 9, 10, 14, 15, 18, 21, 22, 24],
    SHAPE_R: [0, 1, 2, 3, 5, 9, 10, 14, 15, 16, 17, 18, 20, 24],
    SHAPE_S: [0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 19, 20, 21, 22, 23, 24],
    SHAPE_T: [0, 1, 2, 3, 4, 7, 12, 17, 22],
    SHAPE_U: [0, 4, 5, 9, 10, 14, 15, 19, 21, 22, 23],
    SHAPE_V: [0, 4, 5, 9, 11, 13, 16, 18, 22],
    SHAPE_W: [0, 4, 5, 9, 10, 12, 14, 15, 17, 19, 20, 21, 23, 24],
    SHAPE_X: [0, 4, 6, 8, 12, 16, 18, 20, 24],
    SHAPE_Y: [0, 4, 6, 8, 12, 17, 22],
    SHAPE_Z: [0, 1, 2, 3, 4, 8, 12, 16, 20, 21, 22, 23, 24],

    // Symbols
    SHAPE_QUESTION: [1, 2, 5, 8, 12, 22],
    SHAPE_EXCLAIM: [2, 7, 12, 22],
    SHAPE_PLUS: [2, 7, 10, 11, 12, 13, 14, 17, 22],
    SHAPE_DIAMOND: [2, 6, 7, 8, 10, 11, 12, 13, 14, 16, 17, 18, 22],
    SHAPE_POWER: [2, 6, 8, 10, 14, 16, 18, 22],
    SHAPE_HEART: [1, 3, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 22],
    SHAPE_CHECK: [9, 13, 15, 17, 21],
    SHAPE_LIGHTNING: [1, 6, 7, 12, 17, 18, 23],
    SHAPE_MUSIC: [2, 3, 7, 12, 15, 16, 17, 20, 21, 22],
    SHAPE_HOUSE: [2, 6, 7, 8, 10, 11, 12, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24],
    SHAPE_TREE: [2, 6, 7, 8, 11, 12, 13, 17, 22],
    SHAPE_HOURGLASS: [0, 1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 21, 22, 23, 24],
    SHAPE_MOON: [2, 3, 4, 6, 7, 11, 12, 16, 17, 22, 23, 24],
    SHAPE_STAR: [2, 5, 7, 9, 11, 12, 13, 15, 17, 19, 22],
    SHAPE_RAINDROP: [2, 6, 8, 10, 14, 15, 19, 21, 22, 23],
    SHAPE_FLAME: [2, 6, 7, 8, 10, 12, 14, 15, 17, 19, 21, 22, 23],
    SHAPE_CHECKERS: [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24],
    SHAPE_SPIRAL: [0, 1, 2, 3, 5, 8, 12, 16, 19, 21, 22, 23, 24],
    SHAPE_FISH: [2, 6, 7, 9, 10, 12, 13, 14, 16, 17, 19, 22],
    SHAPE_BIRD: [5, 6, 8, 9, 11, 12, 13, 17],
    SHAPE_PACMAN: [1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 15, 16, 17, 18, 21, 22, 23, 24],
    SHAPE_INVADER: [1, 3, 5, 6, 7, 8, 9, 11, 12, 13, 16, 18, 20, 24],
    SHAPE_GHOST: [1, 2, 3, 5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],

    // Media / UI
    SHAPE_PLAY: [1, 6, 7, 11, 12, 13, 16, 17, 21],
    SHAPE_PAUSE: [1, 3, 6, 8, 11, 13, 16, 18, 21, 23],
    SHAPE_RECTANGLE: [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
    SHAPE_FASTFORWARD: [5, 8, 10, 11, 13, 14, 15, 18],
    SHAPE_REWIND: [6, 9, 10, 11, 13, 14, 16, 19],
    SHAPE_WIFI: [1, 2, 3, 5, 6, 8, 9, 16, 17, 18, 20, 21, 23, 24],
    SHAPE_POINTER: [0, 5, 6, 10, 11, 12, 15, 16, 20],
    SHAPE_BULLSEYE: [1, 2, 3, 5, 9, 10, 12, 14, 15, 19, 21, 22, 23],
    SHAPE_BATTERY_FULL: [2, 6, 7, 8, 11, 12, 13, 16, 17, 18, 21, 22, 23],
    SHAPE_BATTERY_HALF: [2, 6, 8, 11, 13, 16, 17, 18, 21, 22, 23],
    SHAPE_BATTERY_EMPTY: [2, 6, 8, 11, 13, 16, 18, 21, 22, 23],

    // Characters
    SHAPE_DANCER1: [1, 5, 6, 7, 11, 16, 17, 20, 22],
    SHAPE_DANCER2: [2, 6, 7, 8, 12, 17, 21, 23],
    SHAPE_DANCER3: [3, 7, 8, 9, 13, 17, 18, 22, 24],
    SHAPE_SAD_FACE: [6, 8, 16, 17, 18, 20, 24],
    SHAPE_HAPPY_FACE: [6, 8, 15, 19, 21, 22, 23],
    SHAPE_NEUTRAL_FACE: [6, 8, 21, 22, 23],
    SHAPE_SL_FACE: [5, 8, 15, 21, 22, 23],
    SHAPE_ANGRY_FACE: [0, 4, 6, 8, 21, 22, 23],
    SHAPE_SLEEPY_FACE: [5, 6, 8, 9, 15, 19, 21, 22, 23],

    // Arrows
    SHAPE_ARROW_UP: [2, 6, 7, 8, 10, 11, 12, 13, 14, 17, 22],
    SHAPE_ARROW_DN: [2, 7, 10, 11, 12, 13, 14, 16, 17, 18, 22],
    SHAPE_ARROW_L: [2, 6, 7, 10, 11, 12, 13, 14, 16, 17, 22],
    SHAPE_ARROW_R: [2, 7, 8, 10, 11, 12, 13, 14, 17, 18, 22],
    SHAPE_DIAG_L: [0, 5, 6, 10, 11, 12, 15, 16, 17, 18, 20, 21, 22, 23, 24],
    SHAPE_DIAG_R: [4, 8, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24],

    // Utility
    SHAPE_BORDER: [0, 1, 2, 3, 4, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23, 24],
    SHAPE_INNER_3x3: [6, 7, 8, 11, 12, 13, 16, 17, 18],
    SHAPE_CORNERS: [0, 4, 20, 24],
    SHAPE_CENTER: [12],
    SHAPE_TOP_ROW: [0, 1, 2, 3, 4],
    SHAPE_ROW2: [5, 6, 7, 8, 9],
    SHAPE_ROW3: [10, 11, 12, 13, 14],
    SHAPE_ROW4: [15, 16, 17, 18, 19],
    SHAPE_BOT_ROW: [20, 21, 22, 23, 24],
    SHAPE_LEFT_COL: [0, 5, 10, 15, 20],
    SHAPE_COL2: [1, 6, 11, 16, 21],
    SHAPE_COL3: [2, 7, 12, 17, 22],
    SHAPE_COL4: [3, 8, 13, 18, 23],
    SHAPE_RIGHT_COL: [4, 9, 14, 19, 24],
    SHAPE_SLASH_L: [0, 6, 12, 18, 24],
    SHAPE_SLASH_R: [4, 8, 12, 16, 20],
};

export function rgbCss(rgb) {
    if (!rgb) return null;
    return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

/**
 * Resolve a Python-ish color token from generated code to a CSS rgb()
 * string: either a literal (r, g, b) tuple, or a leds.py palette name.
 */
export function resolveColorToken(token) {
    if (!token) return null;
    const t = token.trim();
    const tupleMatch = t.match(/\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)/);
    if (tupleMatch) {
        const rgb = [Number(tupleMatch[1]), Number(tupleMatch[2]), Number(tupleMatch[3])].map((v) =>
            Math.max(0, Math.min(255, v))
        );
        return rgbCss(scaleForDisplay(rgb));
    }
    const nameMatch = t.match(/([A-Z][A-Z0-9_]*)\s*$/);
    if (nameMatch && PALETTE[nameMatch[1]]) {
        return rgbCss(PALETTE[nameMatch[1]]);
    }
    return null;
}

export function resolveShapeToken(token) {
    if (!token) return null;
    const m = token.trim().match(/([A-Z][A-Z0-9_]*)\s*$/);
    if (m && SHAPES[m[1]]) return SHAPES[m[1]];
    return null;
}

/** Split a top-level argument list by commas, respecting nested parens. */
function splitArgs(argsRaw) {
    const parts = [];
    let depth = 0;
    let cur = "";
    for (const ch of argsRaw) {
        if (ch === "(") depth++;
        if (ch === ")") depth--;
        if (ch === "," && depth === 0) {
            parts.push(cur);
            cur = "";
        } else {
            cur += ch;
        }
    }
    if (cur.trim().length) parts.push(cur);
    return parts;
}

const BLACK_CSS = "rgb(0, 0, 0)";

/**
 * Locate every `leds.METHOD(...)` call in source, using balanced-paren
 * scanning (args can contain nested parens: tuples, dicts). Returns
 * { method, argsRaw, index, line } for each call, in source order.
 */
function findLedCalls(src) {
    const calls = [];
    const methodRe = /\bleds\.(off|solid|fill|show_shape|show_pattern)\s*\(/g;
    let m;
    while ((m = methodRe.exec(src))) {
        const method = m[1];
        const start = m.index + m[0].length;
        let argsRaw = "";
        if (method !== "off") {
            let depth = 1;
            let i = start;
            while (i < src.length && depth > 0) {
                if (src[i] === "(") depth++;
                else if (src[i] === ")") depth--;
                i++;
            }
            argsRaw = src.slice(start, i - 1);
        }
        calls.push({ method, argsRaw, index: m.index });
    }
    return calls;
}

/** Apply one leds.* call on top of an existing 25-pixel frame, returning a new frame. */
function applyCall(pixels, method, argsRaw) {
    const parts = splitArgs(argsRaw);
    if (method === "off") {
        return new Array(25).fill(BLACK_CSS);
    }
    if (method === "solid") {
        const nums = argsRaw.match(/-?\d+/g);
        if (nums && nums.length >= 3) {
            const css = resolveColorToken(`(${nums[0]}, ${nums[1]}, ${nums[2]})`);
            if (css) return new Array(25).fill(css);
        }
        return pixels;
    }
    if (method === "fill") {
        const css = resolveColorToken(parts[0]);
        return css ? new Array(25).fill(css) : pixels;
    }
    if (method === "show_shape") {
        const indices = resolveShapeToken(parts[0]) || [];
        const color = resolveColorToken(parts[1]);
        const bgPart = parts.find((p) => /^\s*bg\s*=/.test(p));
        const bg = bgPart ? resolveColorToken(bgPart.split("=")[1]) : BLACK_CSS;
        const next = new Array(25).fill(bg || BLACK_CSS);
        if (color) indices.forEach((idx) => {
            if (idx >= 0 && idx < 25) next[idx] = color;
        });
        return next;
    }
    if (method === "show_pattern") {
        const bgPart = parts.find((p) => /^\s*bg\s*=/.test(p));
        const bg = bgPart ? resolveColorToken(bgPart.split("=")[1]) : BLACK_CSS;
        const next = new Array(25).fill(bg || BLACK_CSS);
        const entryRe = /([A-Z][A-Z0-9_]*)\s*:\s*\(([^)]*)\)/g;
        let em;
        while ((em = entryRe.exec(parts[0] || ""))) {
            const css = resolveColorToken(em[1]);
            const idxNums = (em[2].match(/\d+/g) || []).map(Number);
            if (css) idxNums.forEach((idx) => {
                if (idx >= 0 && idx < 25) next[idx] = css;
            });
        }
        return next;
    }
    return pixels;
}

/** Layer literal-index writes (leds.np[3] = RED) found anywhere onto a frame. */
function applyLiteralIndexWrites(pixels, src) {
    const next = pixels.slice();
    const idxRe = /\.np\[\s*(\d+)\s*\]\s*=\s*(\([^)]+\)|[A-Z][A-Z0-9_]*)/g;
    let m;
    while ((m = idxRe.exec(src))) {
        const idx = Number(m[1]);
        if (idx >= 0 && idx < 25) {
            const css = resolveColorToken(m[2]);
            if (css) next[idx] = css;
        }
    }
    return next;
}

const PRESS_RE = /\bbuttondown\b|\bpressed\s+and\b|^pressed$|\bif\s+pressed\b|\bbtn\.value\(\)\s*==\s*0\b(?!.{0,4}\bnot\b)/i;
const RELEASE_RE = /\breleas|\bbuttonup\b|\bnot\s+pressed\b|\bnot\s*\(?\s*self\.?btn\.value\(\)\s*==\s*0|\bbtn\.value\(\)\s*==\s*1\b/i;

/**
 * Indentation-aware branch classifier: for a given absolute char offset,
 * walk upward through enclosing if/elif blocks (by indentation) and
 * concatenate their condition text, then classify it as PRESS, RELEASE,
 * or null (no button-conditional signal detected) via keyword heuristics.
 * This is a heuristic, not a real parser — see computeLedFrames() docs.
 */
function classifyBranch(src, index, log) {
    const before = src.slice(0, index);
    const lines = before.split("\n");
    const callLineIndentMatch = lines[lines.length - 1].match(/^\s*/);
    let boundaryIndent = callLineIndentMatch ? callLineIndentMatch[0].length : 0;
    const conditions = [];

    for (let i = lines.length - 2; i >= 0 && boundaryIndent > 0; i--) {
        const line = lines[i];
        if (!line.trim()) continue;
        const indentMatch = line.match(/^\s*/);
        const indent = indentMatch[0].length;
        if (indent >= boundaryIndent) continue; // not an enclosing block
        const trimmed = line.trim();
        if (/^(if|elif)\s+.*:\s*$/.test(trimmed) || /^else\s*:\s*$/.test(trimmed)) {
            conditions.unshift(trimmed);
        }
        boundaryIndent = indent;
    }

    const context = conditions.join(" | ");
    let branch = null;
    if (RELEASE_RE.test(context)) branch = "release";
    else if (PRESS_RE.test(context)) branch = "press";

    if (log) log(context, branch);
    return { context, branch };
}

/**
 * Best-effort static simulation of what leds.* calls will draw. Because
 * many games change the LED matrix based on button state (press vs.
 * release), this produces TWO frames instead of one:
 *   - idle:    composite of all calls NOT classified as "press"
 *              (i.e. release-branch + unconditional calls), in source order
 *   - pressed: idle frame, then press-branch calls layered on top
 * This is a heuristic (regex + indentation), not a real Python
 * interpreter, so unusual code structures may not classify correctly —
 * see the "known limitations" note in codeCapabilities.js.
 */
export function computeLedFrames(src, opts = {}) {
    const onLog = opts.onLog || null;
    const calls = findLedCalls(src);
    const classified = calls.map((c) => {
        const { context, branch } = classifyBranch(src, c.index, onLog ? (ctx, br) => onLog("classify", { method: c.method, index: c.index, context: ctx, branch: br }) : null);
        return { ...c, context, branch };
    });

    let idle = new Array(25).fill(BLACK_CSS);
    for (const c of classified) {
        if (c.branch === "press") continue;
        idle = applyCall(idle, c.method, c.argsRaw);
    }
    idle = applyLiteralIndexWrites(idle, src);

    let pressed = idle;
    const pressCalls = classified.filter((c) => c.branch === "press");
    if (pressCalls.length) {
        pressed = idle;
        for (const c of pressCalls) {
            pressed = applyCall(pressed, c.method, c.argsRaw);
        }
    }

    if (onLog) {
        onLog("frames", {
            totalCalls: calls.length,
            pressCalls: pressCalls.length,
            hasDistinctPressedFrame: pressCalls.length > 0,
            idle,
            pressed,
        });
    }

    return { idle, pressed, pressDetected: pressCalls.length > 0 };
}

/** Backward-compatible single-frame accessor (returns the idle frame). */
export function computeLedPixels(src) {
    return computeLedFrames(src).idle;
}
