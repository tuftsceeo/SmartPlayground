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
 *
 * Interview mode (buildInterviewSystemBlocks) keeps block 1, replaces block 2
 * with interview.md, and sends the question count as block 3.
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
    'knowledge/party_games.md',
    'knowledge/troubleshooting.md',
];
/** Addendum sent only in Advanced UI mode. */
export const ADVANCED_KNOWLEDGE = 'knowledge/advanced.md';
/** Addendum sent only in interview mode. */
export const INTERVIEW_KNOWLEDGE = 'knowledge/interview.md';

/** Questions an interview may ask, counting the fixed title question. */
export const INTERVIEW_MAX_QUESTIONS = 10;
/** The interview's first question, asked by the app without a model call. */
export const INTERVIEW_FIRST_QUESTION = 'What is the title of your game?';

/** Every knowledge file path the prompt needs, in order. */
export function knowledgePaths() {
    return [...SHARED_KNOWLEDGE, ...ROLES.map(r => r.knowledgeFile), ADVANCED_KNOWLEDGE,
        INTERVIEW_KNOWLEDGE];
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
    const splat = '# SPLAT ACTION NAMES\n\n' +
        'For a Splat from net.splat(i) (leader) or net.local.unit(s) ' +
        '(this wand\'s own Splat, any game role):\n\n' +
        `- colors (.color): ${splatActions.colors.join(', ')}\n` +
        `- notes (.note): ${splatActions.notes.join(', ')}\n` +
        `- sounds (.sound): ${splatActions.sounds.join(', ')}\n\n` +
        '.play([...]) takes any mix of these. Use these names only.';
    return [roleSummary(), ...paths.map(p => files[p]), splat].join('\n\n---\n\n');
}

/**
 * The per-turn block (block 3): icon names and the code in the editor.
 * @param {string[]} icons  icon names available on the display
 * @param {Object<string,string>} editorCode  role key -> current code
 * @param {string[]} [customIcons]  names the teacher drew or edited for this
 *     game; each is listed with a "(custom)" suffix
 */
export function sessionText(icons, editorCode, customIcons = []) {
    const custom = new Set(customIcons);
    const listed = icons.map(n => (custom.has(n) ? `${n} (custom)` : n));
    const parts = [
        '# ICONS CURRENTLY AVAILABLE ON THE ICON DISPLAY\n\n' + listed.join(', ') +
        '\n\nRefer to icons by these names only. If a game needs a picture that is not in this ' +
        'list, say so and suggest the closest one rather than inventing a name.' +
        (custom.size ? ' Icons marked (custom) were drawn by the teacher for this game; ' +
            'refer to them by name without the "(custom)" suffix.' : ''),
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
 *          icons:string[], customIcons?:string[], editorCode:Object<string,string>}} o
 */
export function buildSystemBlocks({ knowledge, advanced, advancedMode, icons, customIcons, editorCode }) {
    const blocks = [{ type: 'text', text: knowledge, cache_control: { type: 'ephemeral' } }];
    if (advancedMode) {
        if (typeof advanced !== 'string') throw new Error(`${ADVANCED_KNOWLEDGE} not loaded`);
        blocks.push({ type: 'text', text: advanced, cache_control: { type: 'ephemeral' } });
    }
    blocks.push({ type: 'text', text: sessionText(icons, editorCode, customIcons) });
    return blocks;
}

/**
 * The per-turn block for interview mode: how many questions have been asked,
 * and whether this turn must be the summary.
 * @param {number} asked  questions asked so far, including the title question
 * @param {boolean} finish  true when the teacher asked to stop early
 */
export function interviewStatusText(asked, finish = false) {
    const last = finish || asked >= INTERVIEW_MAX_QUESTIONS;
    const status = `# Interview status\n\nQuestions asked so far: ${asked} of ` +
        `${INTERVIEW_MAX_QUESTIONS}.`;
    if (!last) return status;
    const why = finish ? 'The teacher asked to stop the interview.' : 'No questions are left.';
    return `${status} ${why} This is the last turn: do not ask a question. ` +
        'Write the summary with the [GAME_BRIEF] block now, choosing sensible defaults for ' +
        'anything still unknown.';
}

/**
 * System blocks for one interview request.
 * @param {{knowledge:string, interview:string, asked:number, finish?:boolean}} o
 */
export function buildInterviewSystemBlocks({ knowledge, interview, asked, finish = false }) {
    if (typeof interview !== 'string') throw new Error(`${INTERVIEW_KNOWLEDGE} not loaded`);
    return [
        { type: 'text', text: knowledge, cache_control: { type: 'ephemeral' } },
        { type: 'text', text: interview, cache_control: { type: 'ephemeral' } },
        { type: 'text', text: interviewStatusText(asked, finish) },
    ];
}

/**
 * Messages for an interview request. The app asks the title question
 * itself, so the transcript opens with a fixed user turn that starts the
 * interview, followed by that question. Every turn is sent: a full
 * interview is ~22 messages, past HISTORY_WINDOW.
 * @param {{role:string, content:string}[]} turns  starting with the
 *     teacher's answer to the title question
 */
export function interviewMessages(turns) {
    return [
        { role: 'user', content: 'Interview me to design a new game.' },
        { role: 'assistant', content: INTERVIEW_FIRST_QUESTION },
        ...turns,
    ];
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

/**
 * Request body for POST /v1/messages.
 * @param {{system:object[], history:object[], stream?:boolean, windowed?:boolean}} o
 *     windowed: false sends every message instead of historyWindow(history)
 */
export function buildRequestBody({ system, history, stream = true, windowed = true }) {
    return {
        model: CLAUDE_MODEL,
        max_tokens: MAX_TOKENS,
        output_config: { effort: CLAUDE_EFFORT },
        // A safety-classifier decline is re-run server-side on the model
        // Anthropic recommends for that decline category.
        fallbacks: 'default',
        stream,
        system,
        messages: windowed ? historyWindow(history) : history,
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
