/**
 * Reader for a streamed /v1/messages response (server-sent events).
 *
 * Works on any fetch Response with a readable body, in the browser and in
 * Node, so the app and tools/prompt_eval.mjs parse replies the same way.
 */

/**
 * Consume the event stream, calling onText with the accumulated reply text
 * after every text delta.
 *
 * @param {Response} resp  a successful fetch Response with stream: true
 * @param {(text: string) => void} [onText]
 * @returns {Promise<{text: string, stopReason: string|null, stopDetails: object|null,
 *     usage: object, error: object|null, firstTextMs: number|null}>}
 *     `error` is the stream's own error event, if one arrived.
 */
export async function readMessageStream(resp, onText = () => {}) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    const started = Date.now();
    let buf = '';
    let text = '';
    let stopReason = null;
    let stopDetails = null;
    let error = null;
    let firstTextMs = null;
    const usage = {};

    const handle = (evt) => {
        switch (evt.type) {
        case 'message_start':
            Object.assign(usage, evt.message?.usage || {});
            break;
        case 'content_block_delta':
            if (evt.delta?.type === 'text_delta') {
                if (firstTextMs === null) firstTextMs = Date.now() - started;
                text += evt.delta.text;
                onText(text);
            }
            break;
        case 'message_delta':
            if (evt.delta?.stop_reason) stopReason = evt.delta.stop_reason;
            if (evt.delta?.stop_details) stopDetails = evt.delta.stop_details;
            Object.assign(usage, evt.usage || {});
            break;
        case 'error':
            error = evt.error || { message: 'stream error' };
            break;
        default:
            break;
        }
    };

    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buf.indexOf('\n\n')) !== -1) {
            const raw = buf.slice(0, sep);
            buf = buf.slice(sep + 2);
            const data = raw.split('\n')
                .filter(l => l.startsWith('data:'))
                .map(l => l.slice(5).trimStart())
                .join('\n');
            if (!data) continue;
            handle(JSON.parse(data));
        }
    }
    return { text, stopReason, stopDetails, usage, error, firstTextMs };
}
