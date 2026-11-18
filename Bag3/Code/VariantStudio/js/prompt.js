/**
 * The instructions and wire shape for "describe it". No network code, so
 * both the local studio (claude.js) and the claude.ai artifact can use it.
 */
import { REGIONS, TOKENS, FONTS, STYLE_PROPS } from './regions.js';
import { normalize } from './variant.js';

/** Current values of the color tokens (ChatBroadcast/css/app.css :root). */
const TOKEN_DEFAULTS = {
    '--pink': '#ef4d92', '--pink-dark': '#d13a7c', '--purple': '#6c4cd1',
    '--teal': '#22c3a6', '--teal-dark': '#1c9a82', '--yellow': '#ffd23f',
    '--ink': '#231f2e', '--muted': '#8b859a', '--border': '#e8e6f0', '--bg': '#f7f7fb',
    '--icon-ink': '#5b5468', '--serve-bg': '#e9fbf6', '--serve-fg': '#1c9a82',
    '--write-bg': '#f2eefc', '--write-fg': '#6c4cd1', '--disabled-fill': '#d8d4e6',
    '--scrim': 'rgba(35, 31, 46, 0.35)', '--overlay-shadow': '0 24px 60px rgba(0, 0, 0, 0.22)',
    '--shell-shadow': '0 18px 40px rgba(108, 76, 209, 0.18)',
    '--tab-active-bg': '#fff0f6', '--tab-active-fg': '#d13a7c',
};

const REGION_IDS = REGIONS.map(r => r.id);

export function systemPrompt() {
    const parts = REGIONS.map(r => {
        const can = [r.canHide ? 'hide' : 'LOCKED (never hide)', (r.label || r.attr) ? 'relabel' : null, 'restyle']
            .filter(Boolean).join(', ');
        return `- ${r.id} — ${r.name} [${r.view}] (${can})`;
    }).join('\n');
    const tokens = TOKENS.map(t => `- ${t}: ${TOKEN_DEFAULTS[t] || ''}`).join('\n');
    return `You help the Playground team design interface variants of Playground Coder (the Chat Broadcast app), a web app where teachers chat with an AI to make games for wands and other playground devices. A variant changes only how the app looks: which parts show, colors, fonts, borders and wording. It never changes what the app does.

You receive the current variant and a request. Return the FULL updated variant (keep everything the request doesn't touch) and a one-sentence summary of what you changed, in plain words for a non-technical person. If part of a request isn't possible (for example hiding a locked part, moving things around, adding new buttons or features), do what you can and say in the summary what you couldn't do and why.

Parts of the app (id — description [screen] (what a variant may do)):
${parts}

Rules:
- hide: only parts marked "hide". At least one of splash-scratch, splash-gallery, splash-saved must stay visible.
- labels: only parts marked "relabel". Keep labels short; sentence case; US spelling. The send-box label replaces the "Send to Box →" text.
- tokens: only these color tokens (current values shown). Changing them recolors much but not all of the app; use styles for specific parts.
${tokens}
- fonts: body (all text) and headings, from: ${FONTS.join(', ')}. Use "" for no change.
- styles: per part, only these properties: ${STYLE_PROPS.join(', ')}. Values are plain CSS values: no semicolons, braces, !important, or url() other than url(data:image/...). Gradients are fine.
- mode: "simple" (the teacher-friendly view, default) or "advanced"; "none" keeps whatever the device had.
- Keep good contrast between text and its background so everything stays readable.`;
}

function enumOrString(list) { return { type: 'string', enum: list }; }

export function outputFormat() {
    return {
        type: 'json_schema',
        schema: {
            type: 'object',
            additionalProperties: false,
            required: ['summary', 'variant'],
            properties: {
                summary: { type: 'string' },
                variant: {
                    type: 'object',
                    additionalProperties: false,
                    required: ['name', 'mode', 'hide', 'tokens', 'fonts', 'labels', 'styles'],
                    properties: {
                        name: { type: 'string' },
                        mode: enumOrString(['simple', 'advanced', 'none']),
                        hide: { type: 'array', items: enumOrString(REGION_IDS) },
                        tokens: {
                            type: 'array',
                            items: {
                                type: 'object', additionalProperties: false, required: ['name', 'value'],
                                properties: { name: enumOrString(TOKENS), value: { type: 'string' } },
                            },
                        },
                        fonts: {
                            type: 'object', additionalProperties: false, required: ['body', 'headings'],
                            properties: { body: enumOrString(['', ...FONTS]), headings: enumOrString(['', ...FONTS]) },
                        },
                        labels: {
                            type: 'array',
                            items: {
                                type: 'object', additionalProperties: false, required: ['region', 'text'],
                                properties: { region: enumOrString(REGION_IDS), text: { type: 'string' } },
                            },
                        },
                        styles: {
                            type: 'array',
                            items: {
                                type: 'object', additionalProperties: false, required: ['region', 'props'],
                                properties: {
                                    region: enumOrString(REGION_IDS),
                                    props: {
                                        type: 'array',
                                        items: {
                                            type: 'object', additionalProperties: false, required: ['prop', 'value'],
                                            properties: { prop: enumOrString(STYLE_PROPS), value: { type: 'string' } },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    };
}

/** Variant (object maps) -> the array shape the schema uses. */
export function toWire(v) {
    v = normalize(v);
    return {
        name: v.name,
        mode: v.mode || 'none',
        hide: v.hide,
        tokens: Object.entries(v.tokens).map(([name, value]) => ({ name, value })),
        fonts: { body: v.fonts.body || '', headings: v.fonts.headings || '' },
        labels: Object.entries(v.labels).map(([region, text]) => ({ region, text })),
        styles: v.styles.map(s => ({ region: s.region, props: Object.entries(s.props).map(([prop, value]) => ({ prop, value })) })),
    };
}

/** Schema array shape -> variant (object maps). */
export function fromWire(w) {
    const styles = new Map();
    for (const s of w.styles || []) {
        const props = styles.get(s.region) || {};
        for (const p of s.props || []) props[p.prop] = p.value;
        styles.set(s.region, props);
    }
    const fonts = {};
    if (w.fonts?.body) fonts.body = w.fonts.body;
    if (w.fonts?.headings) fonts.headings = w.fonts.headings;
    return normalize({
        name: w.name,
        ...(w.mode === 'simple' || w.mode === 'advanced' ? { mode: w.mode } : {}),
        hide: w.hide,
        tokens: Object.fromEntries((w.tokens || []).map(t => [t.name, t.value])),
        fonts,
        labels: Object.fromEntries((w.labels || []).map(l => [l.region, l.text])),
        styles: [...styles].map(([region, props]) => ({ region, props })),
    });
}

