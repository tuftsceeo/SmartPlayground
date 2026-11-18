/**
 * "Describe it": turn a plain-words request into an updated variant.
 * Direct browser call with the shared key, the same way Chat Broadcast does.
 */
import { requestHeaders } from '../../ChatBroadcast/js/prompt/buildRequest.js';
import { validate } from './variant.js';
import { systemPrompt, outputFormat, toWire, fromWire } from './prompt.js';

export { toWire, fromWire };
export const MODEL = 'claude-opus-5-5';
const API = 'https://api.anthropic.com/v1/messages';

async function call(apiKey, messages, signal) {
    const resp = await fetch(API, {
        method: 'POST',
        headers: requestHeaders(apiKey),
        signal,
        body: JSON.stringify({
            model: MODEL,
            max_tokens: 16000,
            output_config: { effort: 'low', format: outputFormat() },
            fallbacks: 'default',
            system: systemPrompt(),
            messages,
        }),
    });
    if (!resp.ok) {
        let msg = `HTTP ${resp.status}`;
        try { msg = (await resp.json()).error?.message || msg; } catch (_) {}
        throw new Error(msg);
    }
    const data = await resp.json();
    if (data.stop_reason === 'refusal') throw new Error("Claude declined that request — try wording it differently.");
    if (data.stop_reason === 'max_tokens') throw new Error('The reply was cut off — try a smaller change.');
    const text = (data.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
    return JSON.parse(text);
}

/**
 * Ask Claude to change `current` per `request`.
 * @param {string} apiKey
 * @param {object} current   current variant
 * @param {string} request   the person's words
 * @param {{role, content}[]} history  earlier turns (plain text), oldest first
 * @returns {Promise<{variant, summary}>}
 */
export async function describeChange(apiKey, current, request, history = [], signal) {
    const turn = `Current variant:\n${JSON.stringify(toWire(current))}\n\nRequest: ${request}`;
    const messages = [...history.slice(-8), { role: 'user', content: turn }];
    let out = await call(apiKey, messages, signal);
    let variant = fromWire(out.variant);
    let errors = validate(variant);
    if (errors.length) {
        // One retry with the problems spelled out.
        messages.push({ role: 'assistant', content: JSON.stringify(out) });
        messages.push({ role: 'user', content: `That variant breaks these rules:\n- ${errors.join('\n- ')}\nReturn a corrected full variant.` });
        out = await call(apiKey, messages, signal);
        variant = fromWire(out.variant);
        errors = validate(variant);
        if (errors.length) throw new Error(errors.join(' '));
    }
    return { variant, summary: out.summary || 'Updated.' };
}
