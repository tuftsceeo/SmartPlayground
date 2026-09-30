/**
 * Claude request assembly for the chat assistant.
 *
 * Pure functions with no DOM access, so the browser (js/app.js) and the
 * scripted prompt test (tools/prompt_eval.mjs) send identical requests.
 *
 * System prompt layout, stable content first so the cache prefix holds:
 *   1. knowledge base + role summary + Splat action names   (cached)
 *   2. advanced.md, Advanced UI mode only                   (cached)
 *   3. per-turn state: icon names, current editor code      (not cached)
 */
import { ROLES, signatureFor } from '../roles.js';

/** Claude model for chat replies. */
export const CLAUDE_MODEL = 'claude-sonnet-5-5';
/** output_config.effort: controls thinking depth and so reply latency.
 * One of 'low' | 'medium' | 'high' | 'xhigh' | 'max'. */
export const CLAUDE_EFFORT = 'low';
export const MAX_TOKENS = 16384;
/** Messages of chat history sent per request. */
export const HISTORY_WINDOW = 10;
/** Beta header for server-side refusal fallback (`fallbacks: 'default'`). */
export const ANTHROPIC_BETA = 'server-side-fallback-2026-07-01';

/** Knowledge files sent on every request, in prompt order, before the
 * per-device files named by roles.js. */
export const SHARED_KNOWLEDGE = [
    'knowledge/policy.md',
    'knowledge/platform.md',
    'knowledge/game_patterns.md',
    'knowledge/troubleshooting.md',
];
/** Addendum sent only in Advanced UI mode. */
export const ADVANCED_KNOWLEDGE = 'knowledge/advanced.md';

/** Every knowledge file path the prompt needs, in order. */
export function knowledgePaths() {
    return [...SHARED_KNOWLEDGE, ...ROLES.map(r => r.knowledgeFile), ADVANCED_KNOWLEDGE];
}

/** One line per device role: its marker and required play() signature. */
function roleSummary() {
    const lines = ROLES.map(r =>
        `- ${r.label}: marker \`[DEVICE: ${r.key}]\`, signature \`${signatureFor(r.key)}\``);
    return '# Devices this app writes games for\n\n' + lines.join('\n');
}

/**
 * The cached knowledge text (block 1).
 * @param {Object<string,string>} files  path -> file text, for every path
 *     in knowledgePaths() except ADVANCED_KNOWLEDGE
 * @param {{colors:string[], notes:string[], sounds:string[]}} splatActions
 */
export function knowledgeText(files, splatActions) {
    const paths = [...SHARED_KNOWLEDGE, ...ROLES.map(r => r.knowledgeFile)];
    const missing = paths.filter(p => typeof files[p] !== 'string');
    if (missing.length) throw new Error(`knowledge files not loaded: ${missing.join(', ')}`);
    const splat = '# SPLAT ACTION NAMES ON THE SPLAT COMPANION\n\n' +
        `- colors (splat.color): ${splatActions.colors.join(', ')}\n` +
        `- notes (splat.note): ${splatActions.notes.join(', ')}\n` +
        `- sounds (splat.sound): ${splatActions.sounds.join(', ')}\n\n` +
        'splat.play([...]) takes any mix of these. Use these names only.';
    return [roleSummary(), ...paths.map(p => files[p]), splat].join('\n\n---\n\n');
}

/**
 * The per-turn block (block 3): icon names and the code in the editor.
 * @param {string[]} icons  icon names available on the display
 * @param {Object<string,string>} editorCode  role key -> current code
 */
export function sessionText(icons, editorCode) {
    const parts = [
        '# ICONS CURRENTLY AVAILABLE ON THE ICON DISPLAY\n\n' + icons.join(', ') +
        '\n\nRefer to icons by these names only. If a game needs a picture that is not in this ' +
        'list, say so and suggest the closest one rather than inventing a name.',
    ];
    const withCode = ROLES.filter(r => (editorCode[r.key] || '').trim());
    if (withCode.length) {
        parts.push('# Current editor code\n\nThe teacher\'s code editor currently contains the ' +
            'files below. They may differ from code shown earlier in the conversation, because ' +
            'the teacher can edit them directly. Start from these when changing the game.');
        for (const r of withCode) {
            parts.push(`## ${r.label} — [DEVICE: ${r.key}]\n\n\`\`\`python\n${editorCode[r.key].trim()}\n\`\`\``);
        }
    } else {
        parts.push('# Current editor code\n\nThe editor is empty: there is no game yet.');
    }
    return parts.join('\n\n');
}

/**
 * System blocks for one request.
 * @param {{knowledge:string, advanced:string, advancedMode:boolean,
 *          icons:string[], editorCode:Object<string,string>}} o
 */
export function buildSystemBlocks({ knowledge, advanced, advancedMode, icons, editorCode }) {
    const blocks = [{ type: 'text', text: knowledge, cache_control: { type: 'ephemeral' } }];
    if (advancedMode) {
        if (typeof advanced !== 'string') throw new Error(`${ADVANCED_KNOWLEDGE} not loaded`);
        blocks.push({ type: 'text', text: advanced, cache_control: { type: 'ephemeral' } });
    }
    blocks.push({ type: 'text', text: sessionText(icons, editorCode) });
    return blocks;
}

/**
 * The last HISTORY_WINDOW messages, starting on a user turn.
 * @param {{role:string, content:string}[]} history
 */
export function historyWindow(history, n = HISTORY_WINDOW) {
    const recent = history.slice(-n);
    while (recent.length && recent[0].role !== 'user') recent.shift();
    return recent;
}

/** Request body for POST /v1/messages. */
export function buildRequestBody({ system, history, stream = true }) {
    return {
        model: CLAUDE_MODEL,
        max_tokens: MAX_TOKENS,
        output_config: { effort: CLAUDE_EFFORT },
        // A safety-classifier decline is re-run server-side on the model
        // Anthropic recommends for that decline category.
        fallbacks: 'default',
        stream,
        system,
        messages: historyWindow(history),
    };
}

/** Headers for a direct browser or Node call with an API key. */
export function requestHeaders(apiKey) {
    return {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
        'anthropic-beta': ANTHROPIC_BETA,
    };
}
