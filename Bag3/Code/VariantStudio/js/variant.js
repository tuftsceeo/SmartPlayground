/**
 * Variant files: schema, validation and compilation. Pure — no DOM — so the
 * studio, the runner and tools/variant_test.mjs all share it.
 *
 * A variant (v1):
 *   { version: 1, name, mode?: "simple"|"advanced",
 *     hide: [regionId], tokens: {"--pink": "#hex"},
 *     fonts: {body?, headings?}, labels: {regionId: "text"},
 *     styles: [{region, props: {prop: value}}] }
 */
import { REGIONS, REGION_BY_ID, TOKENS, FONTS, STYLE_PROPS } from './regions.js';

export const VERSION = 1;

export function emptyVariant(name = 'My variant') {
    return { version: VERSION, name, hide: [], tokens: {}, fonts: {}, labels: {}, styles: [] };
}

/** Fill missing fields so later code can assume the full shape. */
export function normalize(v) {
    const n = emptyVariant();
    if (!v || typeof v !== 'object') return n;
    return {
        version: VERSION,
        name: typeof v.name === 'string' && v.name.trim() ? v.name.trim() : n.name,
        ...(v.mode === 'simple' || v.mode === 'advanced' ? { mode: v.mode } : {}),
        hide: Array.isArray(v.hide) ? [...new Set(v.hide)] : [],
        tokens: v.tokens && typeof v.tokens === 'object' ? { ...v.tokens } : {},
        fonts: v.fonts && typeof v.fonts === 'object' ? { ...v.fonts } : {},
        labels: v.labels && typeof v.labels === 'object' ? { ...v.labels } : {},
        styles: Array.isArray(v.styles) ? v.styles.map(s => ({ region: s?.region, props: { ...(s?.props || {}) } })) : [],
    };
}

/** Why a CSS value is unsafe, or '' when it is fine. */
export function badValue(value) {
    if (typeof value !== 'string') return 'is not text';
    if (value.length > 300) return 'is too long';
    if (/[;{}<>\\]/.test(value)) return 'contains ; { } < > or \\';
    if (/@import|expression\s*\(|javascript:/i.test(value)) return 'is not allowed';
    if (/!important/i.test(value)) return 'must not use !important';
    const urls = value.match(/url\s*\(\s*['"]?([^'")]*)/gi) || [];
    for (const u of urls) {
        if (!/url\s*\(\s*['"]?data:image\//i.test(u)) return 'may only use url(data:image/…)';
    }
    return '';
}

/**
 * Check a variant against the rules. Returns a list of plain-words problems
 * (empty = valid). The rules keep Chat Broadcast fully usable.
 */
export function validate(input) {
    const errors = [];
    if (!input || typeof input !== 'object') return ['The variant is not an object.'];
    const v = normalize(input);
    if (v.name.length > 60) errors.push('The name is longer than 60 characters.');
    if (input.mode !== undefined && !v.mode) errors.push('mode must be "simple" or "advanced".');

    for (const id of v.hide) {
        const r = REGION_BY_ID[id];
        if (!r) errors.push(`"${id}" is not a known part.`);
        else if (!r.canHide) errors.push(`"${r.name}" can't be hidden — people would get stuck without it.`);
    }
    const cards = REGIONS.filter(r => r.splashCard).map(r => r.id);
    if (cards.every(id => v.hide.includes(id))) {
        errors.push('At least one start screen card must stay visible.');
    }

    for (const [name, value] of Object.entries(v.tokens)) {
        if (!TOKENS.includes(name)) errors.push(`"${name}" is not a known color token.`);
        const bad = badValue(value);
        if (bad) errors.push(`Token ${name} ${bad}.`);
    }

    for (const [slot, font] of Object.entries(v.fonts)) {
        if (slot !== 'body' && slot !== 'headings') errors.push(`Font slot "${slot}" must be body or headings.`);
        else if (font && !FONTS.includes(font)) errors.push(`Font "${font}" is not in the allowed list.`);
    }

    for (const [id, text] of Object.entries(v.labels)) {
        const r = REGION_BY_ID[id];
        if (!r) errors.push(`"${id}" is not a known part.`);
        else if (!r.label && !r.attr) errors.push(`"${r.name}" has no label to change.`);
        if (typeof text !== 'string' || !text.trim()) errors.push(`The label for "${id}" is empty.`);
        else if (text.length > 80) errors.push(`The label for "${id}" is longer than 80 characters.`);
    }

    for (const s of v.styles) {
        const r = REGION_BY_ID[s.region];
        if (!r) { errors.push(`Style part "${s.region}" is not a known part.`); continue; }
        for (const [prop, value] of Object.entries(s.props)) {
            if (!STYLE_PROPS.includes(prop)) errors.push(`Style "${prop}" is not allowed (on ${r.name}).`);
            const bad = badValue(value);
            if (bad) errors.push(`Style ${prop} on ${r.name} ${bad}.`);
        }
    }
    return errors;
}

const PREFIX = 'html[data-variant]';
const NOT_CODE = ':not(#code-editor *):not(pre):not(pre *):not(code)';

function scoped(sel) {
    return sel.split(',').map(s => `${PREFIX} ${s.trim()}`).join(',\n');
}

function fontStack(font) {
    return `'${font}', 'Nunito', ui-rounded, system-ui, sans-serif`;
}

/** Google Fonts stylesheet URL for the variant's fonts, or ''. */
export function fontUrl(v) {
    const fonts = [...new Set(Object.values(v.fonts || {}).filter(Boolean))];
    if (!fonts.length) return '';
    const fam = fonts.map(f => 'family=' + f.replace(/ /g, '+') + ':wght@400;600;700;800').join('&');
    return `https://fonts.googleapis.com/css2?${fam}&display=swap`;
}

/**
 * Turn a valid variant into what apply.js injects.
 * @returns {{css: string, labels: {sel, attr, text}[], fontUrl: string, mode?: string, name: string}}
 */
export function compile(input) {
    const v = normalize(input);
    const out = [];

    const tokens = Object.entries(v.tokens);
    if (tokens.length) {
        out.push(`${PREFIX}:root {\n${tokens.map(([k, val]) => `    ${k}: ${val};`).join('\n')}\n}`);
        if (v.tokens['--bg']) {
            // The body background stacks hardcoded tints over --bg; a new --bg
            // should read as the page color.
            out.push(`${PREFIX} body { background: var(--bg) !important; }`);
        }
    }

    if (v.fonts.body) {
        out.push(`${PREFIX} body,\n${PREFIX} body :is(button, input, textarea, select, h1, h2, h3, h4, p, span, div, label, a)${NOT_CODE} {\n    font-family: ${fontStack(v.fonts.body)} !important;\n}`);
    }
    if (v.fonts.headings) {
        out.push(`${PREFIX} body :is(.splash-title, h1, h2, h3, .detail-title)${NOT_CODE} {\n    font-family: ${fontStack(v.fonts.headings)} !important;\n}`);
    }

    for (const s of v.styles) {
        const r = REGION_BY_ID[s.region];
        if (!r) continue;
        const decls = Object.entries(s.props).map(([p, val]) => `    ${p}: ${val} !important;`);
        if (decls.length) out.push(`${scoped(r.sel)} {\n${decls.join('\n')}\n}`);
    }

    // Hiding last, so nothing above can bring a hidden part back.
    const hidden = v.hide.map(id => REGION_BY_ID[id]).filter(r => r && r.canHide);
    if (hidden.length) {
        out.push(`${hidden.map(r => scoped(r.sel)).join(',\n')} {\n    display: none !important;\n}`);
    }

    const labels = Object.entries(v.labels)
        .map(([id, text]) => ({ r: REGION_BY_ID[id], text }))
        .filter(({ r }) => r && (r.label || r.attr))
        .map(({ r, text }) => ({ id: r.id, sel: r.sel, attr: r.attr || null, text }));

    return { name: v.name, mode: v.mode, css: out.join('\n\n'), labels, fontUrl: fontUrl(v) };
}

/** Variant -> URL-safe base64 (UTF-8). */
export function encodeVariant(v) {
    const bytes = new TextEncoder().encode(JSON.stringify(normalize(v)));
    let bin = '';
    for (const b of bytes) bin += String.fromCharCode(b);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** URL-safe base64 -> variant (throws on garbage). */
export function decodeVariant(s) {
    const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(b64 + '='.repeat((4 - b64.length % 4) % 4));
    const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
    return normalize(JSON.parse(new TextDecoder().decode(bytes)));
}

/** One line per difference from an empty variant, for the changes list. */
export function describe(input) {
    const v = normalize(input);
    const lines = [];
    if (v.mode) lines.push(`Opens in ${v.mode} mode`);
    for (const id of v.hide) lines.push(`Hide ${REGION_BY_ID[id]?.name || id}`);
    for (const [id, t] of Object.entries(v.labels)) lines.push(`${REGION_BY_ID[id]?.name || id} → "${t}"`);
    for (const [k, val] of Object.entries(v.tokens)) lines.push(`Color ${k} = ${val}`);
    for (const [slot, f] of Object.entries(v.fonts)) if (f) lines.push(`${slot === 'body' ? 'Text' : 'Heading'} font: ${f}`);
    for (const s of v.styles) {
        const n = Object.keys(s.props).length;
        if (n) lines.push(`Restyle ${REGION_BY_ID[s.region]?.name || s.region} (${Object.keys(s.props).join(', ')})`);
    }
    return lines;
}
