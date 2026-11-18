/**
 * Brains: how the kit reaches Claude. A brain is
 *   async ({system, history, onText, format}) -> {text, stopReason, error}
 * system: Chat Broadcast's system blocks; history: [{role, content}].
 * format: an output_config.format JSON schema (interview brief); when set,
 * `text` is the JSON.
 */
import { buildRequestBody, requestHeaders } from '../ChatBroadcast/js/prompt/buildRequest.js';
import { readMessageStream } from '../ChatBroadcast/js/prompt/stream.js';

/** The shared API key (magic code). Same request as Chat Broadcast. */
export function apiKeyBrain(apiKey) {
    return async ({ system, history, onText, format = null, windowed = true }) => {
        const stream = !format;
        const resp = await fetch('https://api.anthropic.com/v1/messages', {
            method: 'POST',
            headers: requestHeaders(apiKey),
            body: JSON.stringify(buildRequestBody({ system, history, stream, windowed, format })),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            return { text: '', error: { message: err?.error?.message || `Could not reach Claude (${resp.status}).` } };
        }
        if (stream) return readMessageStream(resp, onText);
        const data = await resp.json();
        return {
            text: (data.content || []).filter(b => b.type === 'text').map(b => b.text).join(''),
            stopReason: data.stop_reason,
        };
    };
}

/** Flatten system blocks into one text. */
export function systemText(system) {
    return (system || []).map(b => b.text).join('\n\n');
}

/** The JSON object in a reply that may wrap it in prose or a fence. */
function jsonOnly(text) {
    const m = text.match(/\{[\s\S]*\}/);
    return m ? m[0] : text;
}

/**
 * A claude.ai artifact's `sample` capability: runs on the viewer's own
 * account. It has no system prompt, so the priming leads the first turn.
 */
export function sampleBrain(sample, { modelTier = 'default' } = {}) {
    return async ({ system, history, onText, format = null }) => {
        const msgs = history.map(m => ({ role: m.role, content: m.content }));
        msgs[0] = { role: 'user', content: `<instructions>\n${systemText(system)}\n</instructions>\n\n${msgs[0].content}` };
        if (format) {
            const last = msgs.length - 1;
            msgs[last] = { role: 'user', content: `${msgs[last].content}\n\nReply with only one JSON object matching this schema, nothing else:\n${JSON.stringify(format.schema)}` };
        }
        try {
            const r = await sample(msgs, { cache: false, modelTier, onText: format ? undefined : ({ text }) => onText?.(text) });
            return { text: format ? jsonOnly(r.text) : r.text, stopReason: r.truncated ? 'max_tokens' : 'end_turn' };
        } catch (e) {
            return { text: '', error: { message: e?.message || e?.code || 'Claude did not answer.' } };
        }
    };
}
