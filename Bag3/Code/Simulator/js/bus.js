/**
 * Virtual ESP-NOW bus between simulated devices.
 *
 * Devices attach by MAC. send() routes to one MAC or, for the broadcast
 * address, to every attached device except the sender. Each delivery can be
 * delayed (latencyMs + random jitterMs), dropped (dropRate) or duplicated
 * (duplicateRate). Delivery times are on the shared virtual clock.
 *
 * With autoRun (default) deliveries fire from setTimeout. With
 * autoRun: false nothing fires until pump() is called, which delivers every
 * message due at clock.nowMs(); tests use this with a manual clock.
 */

import { sharedClock } from "./clock.js";

export const BROADCAST = "ff:ff:ff:ff:ff:ff";

/** Normalize a MAC given as "AA:BB:..", "aabb..", bytes or an array. */
export function normalizeMac(mac) {
  if (mac == null) throw new TypeError("MAC is required");
  let hex;
  if (typeof mac === "string") {
    hex = mac.replace(/[:\-]/g, "").toLowerCase();
  } else if (mac instanceof Uint8Array || Array.isArray(mac)) {
    hex = Array.from(mac, (b) => (b & 0xff).toString(16).padStart(2, "0")).join("");
  } else {
    throw new TypeError(`unsupported MAC type: ${typeof mac}`);
  }
  if (!/^[0-9a-f]{12}$/.test(hex)) throw new TypeError(`bad MAC: ${String(mac)}`);
  return hex.match(/../g).join(":");
}

export function createBus(opts = {}) {
  const clock = opts.clock || sharedClock;
  const rng = opts.rng || Math.random;
  const autoRun = opts.autoRun ?? true;
  const logLimit = opts.logLimit ?? 2000;
  const settings = {
    latencyMs: 2,
    jitterMs: 0,
    dropRate: 0,
    duplicateRate: 0,
    ...(opts.settings || {}),
  };

  const devices = new Map(); // mac -> onReceive(srcMac, payload, meta)
  const queue = []; // { due, seq, src, dst, payload, dup }
  const log = [];
  const listeners = new Set();
  let seq = 0;
  let timer = null;

  function record(entry) {
    const e = { t: clock.nowMs(), ...entry };
    log.push(e);
    if (log.length > logLimit) log.splice(0, log.length - logLimit);
    for (const fn of listeners) fn(e);
  }

  function delay() {
    return Math.max(0, settings.latencyMs + rng() * settings.jitterMs);
  }

  function enqueue(src, dst, payload, dup) {
    queue.push({ due: clock.nowMs() + delay(), seq: seq++, src, dst, payload, dup });
    queue.sort((a, b) => a.due - b.due || a.seq - b.seq);
    if (autoRun) arm();
  }

  function arm() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    if (!queue.length) return;
    const wait = Math.max(0, clock.toRealMs(queue[0].due - clock.nowMs()));
    timer = setTimeout(() => {
      timer = null;
      pump();
    }, wait);
  }

  function pump() {
    const now = clock.nowMs();
    let delivered = 0;
    while (queue.length && queue[0].due <= now) {
      const m = queue.shift();
      const handler = devices.get(m.dst);
      if (!handler) {
        record({ event: "unrouted", src: m.src, dst: m.dst, payload: m.payload });
        continue;
      }
      record({ event: "deliver", src: m.src, dst: m.dst, payload: m.payload, dup: m.dup });
      handler(m.src, m.payload, { dup: m.dup });
      delivered++;
    }
    if (autoRun) arm();
    return delivered;
  }

  function send(srcMac, dstMac, payload) {
    const src = normalizeMac(srcMac);
    const dst = normalizeMac(dstMac);
    record({ event: "send", src, dst, payload });
    const targets = dst === BROADCAST ? [...devices.keys()].filter((m) => m !== src) : [dst];
    for (const t of targets) {
      if (rng() < settings.dropRate) {
        record({ event: "drop", src, dst: t, payload });
        continue;
      }
      enqueue(src, t, payload, false);
      if (rng() < settings.duplicateRate) {
        record({ event: "duplicate", src, dst: t, payload });
        enqueue(src, t, payload, true);
      }
    }
    return targets.length;
  }

  return {
    attach(mac, onReceive) {
      const m = normalizeMac(mac);
      if (devices.has(m)) throw new Error(`MAC already attached: ${m}`);
      devices.set(m, onReceive);
      return () => devices.delete(m);
    },
    send,
    pump,
    pending: () => queue.length,
    macs: () => [...devices.keys()],
    getSettings: () => ({ ...settings }),
    setSettings(next) {
      for (const k of Object.keys(next)) {
        if (!(k in settings)) throw new Error(`unknown bus setting: ${k}`);
        const v = Number(next[k]);
        if (!(v >= 0)) throw new RangeError(`${k} must be >= 0`);
        if (k.endsWith("Rate") && v > 1) throw new RangeError(`${k} must be <= 1`);
        settings[k] = v;
      }
    },
    log,
    clearLog: () => log.splice(0, log.length),
    onLog(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    reset() {
      queue.length = 0;
      if (timer !== null) clearTimeout(timer);
      timer = null;
    },
  };
}
