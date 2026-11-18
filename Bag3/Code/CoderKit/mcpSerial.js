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

const PORT_KEY = 'coderkit.serialPort';
function rememberedPort(ports) {
    try { const p = localStorage.getItem(PORT_KEY); return ports.some(x => x.path === p) ? p : null; } catch { return null; }
}
function rememberPort(path) { try { localStorage.setItem(PORT_KEY, path); } catch { /* no storage */ } }

/**
 * The port chooser Connect shows (like Chrome's serial picker): every port,
 * the likely controller preselected, the last choice remembered. Without a
 * page (tests, Node) it takes the suggestion.
 */
export function defaultChoosePort(ports, suggested) {
    if (typeof document === 'undefined') return Promise.resolve(suggested);
    return new Promise((resolve) => {
        const wrap = document.createElement('div');
        wrap.setAttribute('role', 'dialog');
        wrap.setAttribute('aria-label', 'Choose the controller port');
        wrap.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.4);font:14px/1.4 system-ui,sans-serif';
        const box = document.createElement('div');
        box.style.cssText = 'background:#fff;color:#111;border-radius:12px;padding:16px;width:min(420px,calc(100vw - 32px));box-shadow:0 10px 30px rgba(0,0,0,.3)';
        const h = document.createElement('div');
        h.textContent = 'Choose the controller\'s USB port';
        h.style.cssText = 'font-weight:700;font-size:16px;margin-bottom:8px';
        const list = document.createElement('div');
        list.style.cssText = 'display:flex;flex-direction:column;gap:6px;max-height:50vh;overflow:auto';
        let chosen = suggested;
        for (const p of ports) {
            const row = document.createElement('label');
            row.style.cssText = 'display:flex;gap:8px;align-items:flex-start;padding:8px;border:1px solid #ddd;border-radius:8px;cursor:pointer';
            const r = document.createElement('input');
            r.type = 'radio'; r.name = 'coderkit-port'; r.value = p.path; r.checked = p.path === suggested;
            r.onchange = () => { chosen = p.path; };
            const t = document.createElement('span');
            const extra = [p.manufacturer, p.vendorId && `USB ${p.vendorId}:${p.productId || '?'}`].filter(Boolean).join(' · ');
            t.textContent = p.path + (extra ? '\n' + extra : '') + (p.path === suggested ? '\n(looks like a controller)' : '');
            t.style.whiteSpace = 'pre-line';
            row.append(r, t);
            row.ondblclick = () => done(p.path);
            list.appendChild(row);
        }
        const btns = document.createElement('div');
        btns.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;margin-top:12px';
        const mk = (label, primary) => { const b = document.createElement('button'); b.textContent = label; b.style.cssText = `padding:8px 14px;border-radius:8px;border:1px solid ${primary ? '#d13a7c' : '#bbb'};background:${primary ? '#d13a7c' : '#fff'};color:${primary ? '#fff' : '#111'};font-weight:600;cursor:pointer`; return b; };
        const cancel = mk('Cancel'), ok = mk('Connect', true);
        const done = (v) => { wrap.remove(); document.removeEventListener('keydown', key); resolve(v); };
        const key = (e) => { if (e.key === 'Escape') done(null); };
        cancel.onclick = () => done(null);
        ok.onclick = () => done(chosen || null);
        wrap.onclick = (e) => { if (e.target === wrap) done(null); };
        document.addEventListener('keydown', key);
        btns.append(cancel, ok);
        box.append(h, list, btns);
        wrap.appendChild(box);
        document.body.appendChild(wrap);
        ok.focus();
    });
}

export class McpSerialAdapter extends SerialAdapter {
    /** @param mcp the `mcp` namespace (or any object with callTool(server, tool, input, opts)) */
    /** choosePort(ports, suggested) resolves a path, or null when cancelled. */
    constructor(mcp, { server = MCP_SERVER, idleMs = 600, choosePort = defaultChoosePort } = {}) {
        super();
        this.choosePort = choosePort;
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
        if (!ports.length) throw new Error('No USB ports found. Plug the Dial or Box in with USB, then click Connect again.');
        const path = opts.path || await this.choosePort(ports, rememberedPort(ports) || pickPort(ports)?.path || ports[0].path);
        if (!path) throw new Error('No port selected.');
        await this._open(path, opts.baudRate ?? 115200);
        rememberPort(path);
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
