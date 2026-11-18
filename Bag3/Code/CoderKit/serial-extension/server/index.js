#!/usr/bin/env node
// Playground Serial: a tiny local MCP server that lets Playground IDE
// artifacts (claude.ai, Claude desktop app) talk to a USB controller.
// stdout carries MCP protocol only; every log goes to stderr.
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { SerialPort } from 'serialport';
import { z } from 'zod';

const CHUNK = 256;          // same pacing as ChatBroadcast's serialAdapter.js
const CHUNK_DELAY_MS = 10;
const MAX_LINES = 2000;     // read buffer cap
const log = (...a) => console.error('[playground-serial]', ...a);
const sleep = ms => new Promise(r => setTimeout(r, ms));

let port = null, info = null, partial = '', lines = [], dropped = 0, lastError = null;

function push(line) {
  lines.push(line);
  waiter?.();
  if (lines.length > MAX_LINES) { dropped += lines.length - MAX_LINES; lines = lines.slice(-MAX_LINES); }
}
const ok = obj => ({ content: [{ type: 'text', text: JSON.stringify(obj) }], structuredContent: obj });
const fail = msg => ({ content: [{ type: 'text', text: msg }], isError: true });
const status = () => ({ open: !!port?.isOpen, path: info?.path ?? null, baud: info?.baud ?? null, buffered: lines.length, lastError, version: '0.1.2' });

async function closePort() {
  const p = port; port = null; info = null;
  if (p?.isOpen) await new Promise(r => p.close(() => r()));
}

const server = new McpServer({ name: 'playground-serial', version: '0.1.2' });
const RO = { readOnlyHint: true, destructiveHint: false, openWorldHint: false };

server.registerTool('status', { description: 'Whether a controller port is open, and which one.', annotations: RO }, async () => ok(status()));

server.registerTool('list_ports', { description: 'List USB serial ports on this computer.', annotations: RO }, async () => {
  const ports = await SerialPort.list();
  return ok({ ports: ports.filter(p => !/Bluetooth|debug-console/i.test(p.path)).map(p => ({ path: process.platform === 'darwin' ? p.path.replace('/dev/tty.', '/dev/cu.') : p.path, manufacturer: p.manufacturer ?? null, vendorId: p.vendorId ?? null, productId: p.productId ?? null, serialNumber: p.serialNumber ?? null })) });
});

server.registerTool('open', {
  description: 'Open a serial port (closes any port this server already has open).',
  inputSchema: { path: z.string(), baud: z.number().int().positive().optional() },
  annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false },
}, async ({ path, baud = 115200 }) => {
  await closePort();
  partial = ''; lines = []; dropped = 0; lastError = null;
  try {
    const p = new SerialPort({ path, baudRate: baud, autoOpen: false });
    await new Promise((res, rej) => p.open(e => e ? rej(e) : res()));
    // Match Web Serial: assert DTR and RTS after open. USB-CDC firmware may hold output until DTR is set.
    await new Promise(r => p.set({ dtr: true, rts: true }, e => { if (e) log('set signals', e.message); r(); }));
    p.on('data', buf => {
      partial += buf.toString('utf8');
      const parts = partial.split(/\r?\n/);
      partial = parts.pop();
      for (const l of parts) push(l);
      if (partial.length > 8192) { push(partial); partial = ''; }
    });
    p.on('error', e => { lastError = e.message; log('port error', e.message); });
    p.on('close', () => { if (port === p) { port = null; lastError = lastError || 'Port closed (unplugged?)'; } });
    port = p; info = { path, baud };
    return ok(status());
  } catch (e) {
    lastError = e.message;
    const busy = /busy|lock|access denied|resource/i.test(e.message);
    return fail(busy ? `Port ${path} is busy. Close any other tab or app using the controller (for example the ChatBroadcast web app), then try again. (${e.message})` : `Could not open ${path}: ${e.message}`);
  }
});

server.registerTool('write', {
  description: 'Send text to the open port. Pass newline: true to add "\\r\\n".',
  inputSchema: { text: z.string(), newline: z.boolean().optional() },
  annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false },
}, async ({ text, newline = false }) => {
  if (!port?.isOpen) return fail('No port is open. Call open first.');
  const bytes = Buffer.from(newline ? text + '\r\n' : text, 'utf8');
  for (let i = 0; i < bytes.length; i += CHUNK) {
    await new Promise((res, rej) => port.write(bytes.subarray(i, i + CHUNK), e => e ? rej(e) : res()));
    await new Promise(r => port.drain(r));
    if (i + CHUNK < bytes.length) await sleep(CHUNK_DELAY_MS);
  }
  return ok({ written: bytes.length });
});

let waiter = null; // resolves a pending long-poll read when data arrives
server.registerTool('read', {
  description: 'Return the complete lines received since the last read (and clear them), plus any unfinished line. wait_ms (0-5000) waits for data first, so callers can poll slowly.',
  inputSchema: { wait_ms: z.number().int().min(0).max(5000).optional() },
  annotations: RO,
}, async ({ wait_ms = 0 } = {}) => {
  if (!lines.length && wait_ms > 0 && port?.isOpen) {
    await new Promise(r => { const t = setTimeout(() => { waiter = null; r(); }, wait_ms); waiter = () => { clearTimeout(t); waiter = null; setTimeout(r, 30); }; });
  }
  const out = lines; lines = [];
  const d = dropped; dropped = 0;
  return ok({ lines: out, partial, dropped: d, open: !!port?.isOpen, lastError });
});

server.registerTool('close', { description: 'Close the open port.', annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false } }, async () => {
  await closePort();
  return ok(status());
});

const shutdown = async () => { try { await closePort(); } finally { process.exit(0); } };
process.stdin.on('close', shutdown);
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

await server.connect(new StdioServerTransport());
log('ready');
