/**
 * Real controllers inside a claude.ai artifact, through the "Playground
 * Serial" Claude Desktop extension (serial-extension/). The artifact calls
 * it with the `mcp` capability as host:Playground_Serial (the desktop app
 * names a local server after its display name).
 *
 * McpSerialAdapter stands in for ChatBroadcast's SerialAdapter (same
 * methods, same readBuf / waiters / onData / onClose behaviour), so
 * ChatBroadcast's BboxDeviceLink runs unchanged on top of it.
 *
 * autoDevice() is the device the kit gets: a simulated controller until the
 * extension answers, then the real one. It keeps the kit's device API.
 */
import { SerialAdapter } from '../ChatBroadcast/js/device/serialAdapter.js';
import { BboxDeviceLink } from '../ChatBroadcast/js/device/bboxDeviceLink.js';

export const MCP_SERVER = 'host:Playground_Serial';
export const MCP_TOOLS = ['status', 'list_ports', 'open', 'write', 'read', 'close'];

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const ESPRESSIF = /^(303a|10c4|1a86)$/i; // M5/Espressif native USB first; then common USB-serial chips
const versionAtLeast = (v, min) => {
    const a = String(v || '0').split('.').map(Number), b = min.split('.').map(Number);
    for (let i = 0; i < 3; i++) { if ((a[i] || 0) !== b[i]) return (a[i] || 0) > b[i]; }
    return true;
};

/** Plain-language text for an mcp error. */
export function explainMcpError(e) {
    switch (e?.code) {
        case 'server_not_connected': return 'The Playground Serial extension is not reachable. Open this in the Claude desktop app with the extension installed and turned on.';
        case 'cancelled': return 'Not allowed. Click Connect again and choose Allow.';
        case 'approval_required': return 'This needs your approval. Click Connect again and choose Allow.';
        case 'not_in_manifest': return 'Playground Serial is turned off for this page (see the page\'s Permissions).';
        case 'rate_limited': return 'Too many requests to the extension. Wait a moment and try again.';
        case 'server_unavailable': return 'The extension did not answer in time. Try again.';
        case 'tool_error': return e.message || 'The extension reported an error.';
        default: return e?.message || String(e);
    }
}

/** Pick the controller's port from list_ports. */
export function pickPort(ports) {
    const m5 = ports.find(p => /M5Stack|Espressif/i.test(p.manufacturer || '') || /^303a$/i.test(p.vendorId || ''));
    return m5 || ports.find(p => ESPRESSIF.test(p.vendorId || '')) || null;
}

export class McpSerialAdapter extends SerialAdapter {
    /** @param mcp the `mcp` namespace (or any object with callTool(server, tool, input, opts)) */
    constructor(mcp, { server = MCP_SERVER, idleMs = 600 } = {}) {
        super();
        this.mcp = mcp;
        this.server = server;
        this.idleMs = idleMs;
        this.path = null;
        this.longPoll = false;
    }

    async _call(tool, input) {
        try {
            const r = await this.mcp.callTool(this.server, tool, input, { cache: false });
            return r?.payload ?? r;
        } catch (e) {
            const err = new Error(explainMcpError(e));
            err.code = e?.code; err.retryAfterMs = e?.retryAfterMs;
            throw err;
        }
    }

    isConnected() { return this.port !== null; }

    async connect(opts = {}) {
        const st = await this._call('status');
        this.longPoll = versionAtLeast(st?.version, '0.1.1');
        const { ports = [] } = await this._call('list_ports');
        const p = pickPort(ports);
        if (!p) throw new Error('No controller found. Plug the Dial or Box in with USB, then click Connect again.');
        await this._open(p.path, opts.baudRate ?? 115200);
    }

    async _open(path, baud) {
        await this._call('open', { path, baud });
        this.path = path;
        // A stand-in "port" so the base class's close-on-drop path can close it.
        this.port = { close: () => this._call('close').catch(() => {}) };
        this.readBuf = '';
        this._rxBytes = 0; this._txBytes = 0;
        this._startReadLoop();
    }

    async reopenLastPort(opts = {}) {
        if (!this.path) return false;
        try { await this._open(this.path, opts.baudRate ?? 115200); return true; } catch { return false; }
    }

    async logSignals() { return null; }
    async setSignals() { /* not offered by the extension */ }

    async disconnect() {
        this._closeFired = true;
        this.readLoopActive = false;
        const p = this.port;
        this.port = null;
        this.readBuf = '';
        this._releaseWaiters('port disconnected');
        if (p) await this._call('close').catch(() => {});
    }

    async write(data) {
        if (!this.port) throw new Error('Not connected to serial port');
        const text = typeof data === 'string' ? data : new TextDecoder().decode(data);
        await this._call('write', { text });
        this._txBytes += text.length;
    }

    // The extension paces in 256-byte chunks itself; one call per write.
    async writeChunked(data) { return this.write(data); }

    _startReadLoop() {
        this.readLoopActive = true;
        this._closeFired = false;
        this._readLoopPromise = (async () => {
            let reason = null, quietErrors = 0;
            while (this.readLoopActive) {
                let delay = this.longPoll ? 50 : this.idleMs;
                try {
                    const r = await this._call('read', this.longPoll ? { wait_ms: 1000 } : undefined);
                    quietErrors = 0;
                    if (!this.readLoopActive) break;
                    if (r?.lines?.length) {
                        const chunk = r.lines.join('\n') + '\n';
                        this._rxBytes += chunk.length;
                        this.readBuf += chunk;
                        this._resolveWaiters();
                        this.onData?.(chunk);
                    }
                    if (r && r.open === false) { reason = r.lastError || 'port closed'; break; }
                } catch (e) {
                    if (!this.readLoopActive) break;
                    if (/rate_limited|server_unavailable/.test(e.code || '') && ++quietErrors < 6) {
                        delay = e.retryAfterMs || 2000 * quietErrors;
                    } else { reason = e.message; break; }
                }
                await sleep(delay);
            }
            if (reason && this.readLoopActive) this._fireClose(reason);
        })();
    }
}

/** ChatBroadcast's Box/Dial link, running over the extension. */
export function createMcpDeviceLink(mcp, opts) {
    const link = new BboxDeviceLink();
    const adapter = new McpSerialAdapter(mcp, opts);
    adapter.onClose = link.adapter.onClose;
    link.adapter = adapter;
    if (link.repl) link.repl.adapter = adapter;
    return link;
}

/** Does the extension answer here? Resolves the mcp namespace or null. */
export async function probeMcpSerial(useMcp, { server = MCP_SERVER } = {}) {
    try {
        const mcp = await useMcp();
        if (!mcp) return null;
        const r = await mcp.callTool(server, 'status', undefined, { cache: false });
        return r ? mcp : null;
    } catch { return null; }
}

const METHODS = ['connect', 'reconnect', 'disconnect', 'nudgeIdentify', 'isConnected', 'isRunning', 'sendCmd', 'sendGame'];

/**
 * A device for the kit that starts as `fallback` (the simulated controller)
 * and becomes the real one when `probe()` resolves an mcp namespace. The
 * switch happens only while not connected; listeners registered with on()
 * hear both. Emits {type: 'realdevice', real} when it switches.
 */
export function autoDevice({ fallback, probe, makeReal = createMcpDeviceLink }) {
    const listeners = [];
    let current = fallback, real = null;
    const dev = {
        get simulated() { return current === fallback; },
        on(t, f) { listeners.push([t, f]); fallback.on?.(t, f); real?.on?.(t, f); return () => {}; },
        ready: Promise.resolve(probe?.()).then((mcp) => {
            if (!mcp) return false;
            real = makeReal(mcp);
            for (const [t, f] of listeners) real.on?.(t, f);
            if (!fallback.isConnected?.()) current = real;
            for (const [t, f] of listeners) if (t === 'realdevice') f({ type: 'realdevice', real: current === real });
            return current === real;
        }).catch(() => false),
    };
    for (const m of METHODS) dev[m] = (...a) => current[m]?.(...a);
    return dev;
}
