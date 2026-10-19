/**
 * Party side of a room, without DOM: the simulated wand's own Splats, the
 * virtual peer wands (js/peers.js) and the pw_* traffic between them. Used
 * by <sim-room> (browser) and js/headless.js (Node).
 *
 * The wand's Splats are py/shims/splat_hub.py links inside its Pyodide;
 * their writes arrive here and are drawn on js/splats.js models, and a
 * press here goes back as splat_hub.press(). Peers are plain JS on the bus.
 *
 *   createPartyHost({ bus, clock, py, wandMac })
 *     .wandSplats              Splat models, in local order
 *     .peers                   [{ peer, link }]
 *     .setLocalSplats(n)       0..2; takes effect at the wand's next start
 *     .wandSplatButton(i, down) / .wandSplatReady(i, up)
 *     .addPeer({ mode, splats }) / .removePeer(peer)
 *     .setGame(slug, caps)     tap every peer into a party game, or untap
 *     .peerDropped(peer, on)
 *     .onChange(fn)            any model change (for redraws)
 *     .onPwLog(fn)             one line per pw_* frame sent on the bus
 *     .dispose()
 */

import { createSplat } from "./splats.js";
import { createPeer, attachPeer, decodePw, wandMac as upperMac } from "./peers.js";

/** Follower peers sit above the wand's MAC (they never lead); leader peers below it, so a wand leading at the same time yields to them. */
const FOLLOWER_BASE = 0x0b;
const LEADER_BASE = 0x01;

export function createPartyHost({ bus, clock, py, wandMac }) {
  const listeners = new Set();
  const logListeners = new Set();
  const host = {
    wandMac: upperMac(wandMac),
    wandSplats: [],
    peers: [],
    slug: null,
    caps: null,
  };
  const changed = () => { for (const fn of listeners) fn(host); };
  const names = new Map([[host.wandMac, "wand"]]);

  const runtime = py.pyimport("runtime").get_runtime();
  const splatHub = py.pyimport("splat_hub");

  py.globals.set("_js_splat_write", (mac, op, args) => {
    const s = host.wandSplats.find((x) => x.mac === String(mac));
    if (!s) return;
    try {
      s.applyWrite(String(op), JSON.parse(String(args)));
    } catch (err) {
      console.warn("splat write", err);
    }
  });
  splatHub.set_write_callback(py.globals.get("_js_splat_write"));

  function syncWandSplats() {
    const proxy = runtime.local_splat_macs();
    const macs = proxy.toJs();
    proxy.destroy?.();
    const keep = new Map(host.wandSplats.map((s) => [s.mac, s]));
    host.wandSplats = macs.map((m) => keep.get(m) || createSplat({ mac: m, owner: host.wandMac, onChange: changed }));
    for (const s of host.wandSplats) s.onChange = changed;
  }
  syncWandSplats();

  host.setLocalSplats = (n) => {
    runtime.set_local_splats(n);
    syncWandSplats();
    changed();
  };

  host.wandSplatButton = (i, down) => {
    const s = host.wandSplats[i];
    if (!s) return;
    s.setPressed(down);
    try {
      if (down) splatHub.press(s.mac);
      else splatHub.release(s.mac);
    } catch {
      // Not paired yet: the hub is built when the game starts.
    }
  };

  host.wandSplatReady = (i, up) => {
    const s = host.wandSplats[i];
    if (!s) return;
    s.setReady(up);
    try {
      splatHub.set_ready(s.mac, up);
    } catch {
      // Not paired yet.
    }
  };

  function nextMac(base) {
    for (let n = 1; n < 0xff; n++) {
      const mac = `02:00:00:00:${base.toString(16).padStart(2, "0")}:${n.toString(16).padStart(2, "0")}`.toUpperCase();
      if (!host.peers.some((e) => e.peer.mac === mac)) return mac;
    }
    throw new Error("out of peer MACs");
  }

  host.addPeer = ({ mode = "follower", splats = 1 } = {}) => {
    const mac = nextMac(mode === "leader" ? LEADER_BASE : FOLLOWER_BASE);
    const n = host.peers.filter((e) => e.peer.mode === mode).length + 1;
    const peer = createPeer({
      mac, clock, splats, mode,
      name: mode === "leader" ? `leader ${n}` : `peer ${n}`,
      onChange: changed,
    });
    names.set(peer.mac, peer.name);
    const link = attachPeer(bus, peer);
    host.peers.push({ peer, link });
    if (host.caps?.party) tap(peer);
    changed();
    return peer;
  };

  host.removePeer = (peer) => {
    const i = host.peers.findIndex((e) => e.peer === peer);
    if (i < 0) return;
    peer.untap();
    host.peers[i].link.detach();
    host.peers.splice(i, 1);
    changed();
  };

  host.peerDropped = (peer, on) => {
    host.peers.find((e) => e.peer === peer)?.link.setDropped(on);
    changed();
  };

  function tap(peer) {
    peer.tap(host.slug, { smin: host.caps.splats_min ?? 1, smax: host.caps.splats_max ?? null });
  }

  /** A game was loaded: peers tap its card if it is a party game. */
  host.setGame = (slug, caps) => {
    host.slug = slug;
    host.caps = caps;
    syncWandSplats();
    for (const { peer } of host.peers) {
      if (caps?.party) tap(peer);
      else peer.untap();
    }
    changed();
  };

  /** Re-tap every peer (the room restarted the game). */
  host.retap = () => {
    if (!host.caps?.party) return;
    for (const { peer } of host.peers) tap(peer);
    changed();
  };

  host.nameOf = (mac) => names.get(upperMac(mac)) || upperMac(mac);

  const offLog = bus.onLog((e) => {
    if (e.event !== "send") return;
    const d = decodePw(e.payload);
    if (!d) return;
    const to = e.dst === "ff:ff:ff:ff:ff:ff" ? "all" : host.nameOf(e.dst);
    const { type, ...rest } = d;
    const line = `${(e.t / 1000).toFixed(2)}s ${host.nameOf(e.src)} → ${to}: ${type} ${JSON.stringify(rest)}`;
    for (const fn of logListeners) fn(line, d, e);
  });

  host.onChange = (fn) => {
    listeners.add(fn);
    return () => listeners.delete(fn);
  };
  host.onPwLog = (fn) => {
    logListeners.add(fn);
    return () => logListeners.delete(fn);
  };

  host.dispose = () => {
    offLog();
    for (const { link } of host.peers) link.detach();
    host.peers = [];
    splatHub.set_write_callback(null);
  };

  return host;
}
