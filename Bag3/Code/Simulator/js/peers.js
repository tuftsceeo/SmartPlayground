/**
 * Virtual peers: JS wands that take part in a lobby game beside the
 * simulated wand, speaking MockWand/lib/lobby_game.py's pw_* frames over the
 * room's bus. A peer runs no game code.
 *
 * Follower peer (mode "follower"): after tap() it broadcasts pw_find and
 * joins the first matching pw_lobby (pw_join, answered by pw_joined), sends
 * pw_hb with its ready-Splat mask every HEARTBEAT_MS in the lobby and the
 * game, starts on pw_start, runs the leader's pw_cmd on its own Splats,
 * sends a press or release on them as pw_evt, and leaves with pw_leave
 * unless the leader ended the game or went silent. Unlike a real wand it
 * never opens a lobby itself: it keeps looking (pw_find every LOBBY_MS)
 * until a leader appears, and looks again after each game.
 *
 * Leader peer (mode "leader"): opens a lobby (pw_lobby every LOBBY_MS, and
 * in answer to pw_find), admits joiners up to SPLATS_MAX, starts with
 * start() and ends with end(). In the game it heartbeats and reports
 * presses and messages as events; what it does with them is the game
 * script's business.
 *
 * pw_cmd, pw_evt and pw_msg carry a per-sender sequence number `q`; a
 * repeated q from the same sender is dropped (pwire.Dedupe).
 *
 * Game scripts (GAME_SCRIPTS, by slug) stand in for the game's code where
 * the wand's play() needs the other wands to act: lobbytest's follower
 * button, relaycolor's token passing. A game without a script gets the
 * protocol only.
 *
 * Transport: attachPeer(bus, peer) puts the peer on a js/bus.js bus.
 */

import { BROADCAST, normalizeMac } from "./bus.js";
import { createSplat, COLOR_RGB } from "./splats.js";

/** lobby_game.py timing. */
export const PW = {
  FIND_WAIT_MS: 500,
  JOIN_WAIT_MS: 1000,
  LOBBY_MS: 1000,
  HEARTBEAT_MS: 1000,
  WAND_LOST_MS: 3000,
  DEDUPE_KEEP: 16,
};

export const OPS = ["color", "color_part", "sound", "note", "play", "off"];

/** splatpair.PALETTE, and splatpair.WAND_RGB (the wand matrix's color for each). */
export const PALETTE = ["turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite"];
export const WAND_RGB = {
  turnred: [130, 0, 0], turngreen: [0, 230, 0], turnblue: [0, 20, 255],
  turnpurple: [120, 0, 160], turnyellow: [120, 80, 0], turnwhite: [140, 150, 150],
};
/** splatpair.GLOW_SCALE: a paired Splat's idle glow. */
const GLOW_SCALE = 0.5;

/** splatpair.identity_name(): palette name from the MAC's last byte. */
export function identityName(mac) {
  return PALETTE[parseInt(String(mac).slice(-2), 16) % PALETTE.length];
}

/** The MAC string lobby_game.py uses: upper-case, colon-separated. */
export function wandMac(mac) {
  return normalizeMac(mac).toUpperCase();
}

/** The Splat MACs a wand holds (same scheme as runtime.local_splat_macs()). */
export function splatMac(ownerMac, i) {
  return `5A:00:${wandMac(ownerMac).slice(-5)}:00:${i.toString(16).toUpperCase().padStart(2, "0")}`;
}

const enc = new TextEncoder();
const dec = new TextDecoder();

/** A bus payload as a pw_ message object, or null. */
export function decodePw(payload) {
  let d;
  try {
    d = JSON.parse(typeof payload === "string" ? payload : dec.decode(payload));
  } catch {
    return null;
  }
  if (!d || typeof d !== "object" || Array.isArray(d)) return null;
  return String(d.type || "").startsWith("pw_") ? d : null;
}

let gameCounter = 0;

/**
 * opts:
 *   mac       this peer's MAC
 *   clock     { nowMs() }
 *   splats    Splats this peer holds (0..2, default 1)
 *   mode      "follower" (default) | "leader"
 *   name      label for logs (default "peer")
 *   onChange  (peer) => void after any state change
 */
export function createPeer(opts) {
  const mac = wandMac(opts.mac);
  const clock = opts.clock;
  const ident = identityName(mac);
  const p = {
    mac,
    name: opts.name || "peer",
    mode: opts.mode || "follower",
    ident,
    rgb: WAND_RGB[ident],
    /** idle, find, join, lobby, game (follower); lead, lead_game (leader). */
    state: "idle",
    slug: null,
    id: null,
    leader: null,
    smin: 1,
    smax: null,
    /** In the game: [[mac, ident, count], ...], leader first; me = own index. */
    wands: [],
    me: null,
    first: 0,
    /** Leader in its lobby: [{mac, ident, count, seen}], itself first. */
    members: [],
    /** Leader in the game: [wand index, local index] per pool Splat. */
    pool: [],
    /** Game events, oldest first, shaped like lobby_game.Net.poll()'s. */
    events: [],
    /** What lobby_game.py would print, and what the scripts do. */
    log: [],
    dropped: false,
    transport: null,
    onChange: opts.onChange || null,
    script: null,
    scriptState: {},
    lastEnd: null,
  };
  p.splats = [];
  for (let i = 0; i < (opts.splats ?? 1); i++) {
    p.splats.push(createSplat({ mac: splatMac(mac, i), owner: mac, onChange: () => changed() }));
  }

  let q = 0;
  let seen = new Map(); // sender -> recent q values
  let t = 0; // find/join timer
  let hbAt = 0;
  let lobbyAt = 0;
  let seenLeader = 0;

  const now = () => clock.nowMs();
  const since = (at) => now() - at;
  function changed() { p.onChange?.(p); }
  function note(line) {
    p.log.push(line);
    if (p.log.length > 200) p.log.splice(0, p.log.length - 200);
  }

  function out(dst, msg) {
    if (p.dropped || !p.transport) return false;
    return p.transport(dst, msg);
  }
  const broadcast = (msg) => out("*", msg);
  function sendQ(dst, msg) {
    q += 1;
    return out(dst, { ...msg, q });
  }

  function fresh(sender, qv) {
    if (qv === undefined || qv === null) return true;
    const list = seen.get(sender) || [];
    if (list.includes(qv)) return false;
    list.push(qv);
    if (list.length > PW.DEDUPE_KEEP) list.shift();
    seen.set(sender, list);
    return true;
  }

  function event(ev) {
    p.events.push(ev);
    if (p.events.length > 200) p.events.splice(0, p.events.length - 200);
    p.script?.onEvent?.(p, ev);
  }

  function mask() {
    let bits = 0;
    p.splats.forEach((s, i) => { if (s.ready) bits |= 1 << i; });
    return bits;
  }

  function glow() {
    const [r, g, b] = COLOR_RGB[ident];
    for (const s of p.splats) {
      s.applyAction("off");
      s.applyWrite("leds", [Math.trunc(r * GLOW_SCALE), Math.trunc(g * GLOW_SCALE), Math.trunc(b * GLOW_SCALE)]);
    }
  }
  glow();

  function sendHb() {
    hbAt = now();
    broadcast({ type: "pw_hb", id: p.id, l: mask() });
  }

  function gameOver(reason) {
    p.lastEnd = reason;
    p.state = "idle";
    p.script?.onEnd?.(p, reason);
    glow();
    note(`game over (${reason})`);
    if (p.mode === "follower" && p.slug) find();
  }

  // ── follower ────────────────────────────────

  function find() {
    p.state = "find";
    p.id = null;
    p.leader = null;
    p.wands = [];
    p.me = null;
    seen = new Map();
    t = now();
    broadcast({ type: "pw_find", g: p.slug });
  }

  function join(leader, gid) {
    p.state = "join";
    p.leader = leader;
    p.id = gid;
    t = now();
    out(leader, { type: "pw_join", id: gid, splats: p.splats.length });
  }

  function onStart(d) {
    const wands = Array.isArray(d.wands) ? d.wands : [];
    const me = wands.findIndex((w) => String(w[0]).toUpperCase() === mac);
    if (me < 0) {
      note(`[ERR] pw_start without this wand in its roster: ${JSON.stringify(wands)}`);
      gameOver("ended");
      return;
    }
    p.wands = wands.map((w) => [String(w[0]).toUpperCase(), w[1], Number(w[2]) || 0]);
    p.me = me;
    p.first = p.wands.slice(0, me).reduce((n, w) => n + w[2], 0);
    p.state = "game";
    p.events = [];
    seenLeader = now();
    hbAt = now() - PW.HEARTBEAT_MS;
    note(`game started: wand ${me} of ${p.wands.length}`);
    p.script?.onStart?.(p);
  }

  function runCmd(d) {
    const s = d.s;
    if (!Number.isInteger(s) || s < 0 || s >= p.splats.length) {
      note(`[WARN] pw_cmd for local Splat ${JSON.stringify(s)}; this wand holds ${p.splats.length}`);
      return;
    }
    if (!OPS.includes(d.op)) {
      note(`[WARN] unknown pw_cmd op ${JSON.stringify(d.op)}`);
      return;
    }
    const splat = p.splats[s];
    if (!splat.ready) return;
    try {
      splat.applyAction(d.op, d.v);
    } catch (err) {
      note(`[ERR] ${d.op} ${JSON.stringify(d.v)}: ${err.message}`);
    }
  }

  function followerReceive(d, src) {
    const ty = d.type;
    if (p.state === "find") {
      if (ty === "pw_lobby" && d.g === p.slug && src !== mac) join(src, d.id);
      return;
    }
    if (p.state === "join" || p.state === "lobby") {
      if (src !== p.leader || d.id !== p.id) return;
      seenLeader = now();
      if (ty === "pw_joined" && p.state === "join") {
        p.state = "lobby";
        sendHb();
      } else if (ty === "pw_start") {
        onStart(d);
      } else if (ty === "pw_end") {
        if (d.r === "yield") find();
        else gameOver(d.r === "full" ? "full" : "ended");
      }
      return;
    }
    if (p.state !== "game" || d.id !== p.id) return;
    const w = p.wands.findIndex((x) => x[0] === src);
    if (w < 0) return;
    if (w === 0) seenLeader = now();
    if (ty === "pw_cmd" && w === 0) {
      if (fresh(src, d.q)) runCmd(d);
    } else if (ty === "pw_msg") {
      if (fresh(src, d.q)) event(["msg", w, d.d]);
    } else if (ty === "pw_end" && w === 0) {
      event(["end"]);
      gameOver("ended");
    }
  }

  function followerTick() {
    if (p.state === "find" && since(t) >= PW.LOBBY_MS) {
      t = now();
      broadcast({ type: "pw_find", g: p.slug });
    } else if (p.state === "join" && since(t) >= PW.JOIN_WAIT_MS) {
      find();
    } else if (p.state === "lobby" || p.state === "game") {
      if (since(hbAt) >= PW.HEARTBEAT_MS) sendHb();
      if (since(seenLeader) >= PW.WAND_LOST_MS) {
        if (p.state === "game") event(["leader_lost"]);
        gameOver("leader_lost");
      }
    }
  }

  // ── leader ──────────────────────────────────

  function lobbySplats() {
    return p.members.reduce((n, m) => n + m.count, 0);
  }

  function sendLobby() {
    lobbyAt = now();
    broadcast({ type: "pw_lobby", g: p.slug, id: p.id, n: lobbySplats(), min: p.smin, max: p.smax });
  }

  function roster() {
    return p.members.map((m) => [m.mac, m.ident, m.count]);
  }

  function onJoin(src, splats) {
    if (!Number.isInteger(splats) || splats < 0) {
      note(`[WARN] bad pw_join from ${src}: splats=${JSON.stringify(splats)}`);
      return;
    }
    const have = p.members.find((m) => m.mac === src);
    const total = lobbySplats() - (have ? have.count : 0);
    if (p.smax !== null && total + splats > p.smax) {
      out(src, { type: "pw_end", id: p.id, r: "full" });
      return;
    }
    if (have) {
      have.count = splats;
      have.seen = now();
    } else {
      p.members.push({ mac: src, ident: identityName(src), count: splats, seen: now() });
    }
    let first = 0;
    for (const m of p.members) {
      if (m.mac === src) break;
      first += m.count;
    }
    out(src, { type: "pw_joined", id: p.id, first, wands: roster() });
  }

  function leaderReceive(d, src) {
    const ty = d.type;
    if (p.state === "lead") {
      if (ty === "pw_find") {
        if (d.g === p.slug) sendLobby();
      } else if (d.id === p.id) {
        const m = p.members.find((x) => x.mac === src);
        if (ty === "pw_join") onJoin(src, d.splats);
        else if (ty === "pw_leave") p.members = p.members.filter((x) => x.mac !== src || x === p.members[0]);
        else if (ty === "pw_hb" && m) m.seen = now();
      }
      return;
    }
    if (p.state !== "lead_game" || d.id !== p.id) return;
    const w = p.wands.findIndex((x) => x[0] === src);
    if (w < 0) return;
    const m = p.members[w];
    m.seen = now();
    if (m.lost && ty === "pw_hb") {
      m.lost = false;
      event(["wand_back", w]);
    }
    if (ty === "pw_evt") {
      const s = d.s;
      if (fresh(src, d.q) && Number.isInteger(s) && p.pool[s] && p.pool[s][0] === w) {
        event([d.e === 1 ? "press" : "release", s]);
      }
    } else if (ty === "pw_msg") {
      if (fresh(src, d.q)) event(["msg", w, d.d]);
    } else if (ty === "pw_leave" && !m.lost) {
      m.lost = true;
      event(["wand_lost", w]);
    }
  }

  function leaderTick() {
    if (p.state === "lead") {
      if (since(lobbyAt) >= PW.LOBBY_MS) sendLobby();
      if (since(hbAt) >= PW.HEARTBEAT_MS) sendHb();
      for (const m of p.members.slice(1)) {
        if (since(m.seen) >= PW.WAND_LOST_MS) {
          note(`${m.mac} silent in the lobby; removed`);
          p.members = p.members.filter((x) => x !== m);
        }
      }
      if (p.smax !== null && lobbySplats() >= p.smax && lobbySplats() >= p.smin) p.start();
    } else if (p.state === "lead_game") {
      if (since(hbAt) >= PW.HEARTBEAT_MS) sendHb();
      p.members.forEach((m, w) => {
        if (w > 0 && !m.lost && since(m.seen) >= PW.WAND_LOST_MS) {
          m.lost = true;
          event(["wand_lost", w]);
        }
      });
    }
  }

  // ── public ──────────────────────────────────

  /** A tap of the game's card. smin/smax matter to a leader only. */
  p.tap = (slug, { smin = 1, smax = null } = {}) => {
    p.slug = slug;
    p.script = GAME_SCRIPTS[slug] || null;
    p.scriptState = {};
    p.events = [];
    p.lastEnd = null;
    seen = new Map();
    if (p.mode === "leader") {
      gameCounter = (gameCounter + 1) & 0xff;
      const b = mac.split(":").map((x) => parseInt(x, 16));
      p.id = (b[4] << 16) | (b[5] << 8) | gameCounter;
      p.smin = smin;
      p.smax = smax;
      p.members = [{ mac, ident, count: p.splats.length, seen: now() }];
      p.wands = [];
      p.leader = mac;
      p.state = "lead";
      sendLobby();
      sendHb();
    } else {
      find();
    }
    changed();
  };

  /** Stop playing: no more finding, leave any lobby or game. */
  p.untap = () => {
    if (p.state === "lobby" || p.state === "join" || (p.state === "game" && p.lastEnd === null)) {
      if (p.leader) out(p.leader, { type: "pw_leave", id: p.id });
    } else if (p.state === "lead" || p.state === "lead_game") {
      for (const m of p.members.slice(1)) out(m.mac, { type: "pw_end", id: p.id });
    }
    p.slug = null;
    p.state = "idle";
    glow();
    changed();
  };

  /** Bus input: src MAC (any form), payload bytes or text. */
  p.receive = (src, payload) => {
    if (p.dropped) return;
    const d = decodePw(payload);
    if (!d) return;
    const from = wandMac(src);
    if (p.mode === "leader") leaderReceive(d, from);
    else followerReceive(d, from);
    changed();
  };

  p.tick = () => {
    if (p.dropped) return;
    const before = p.state;
    if (p.mode === "leader") leaderTick();
    else followerTick();
    p.script?.onTick?.(p);
    if (p.state !== before) changed();
  };

  p.canStart = () => p.state === "lead" && lobbySplats() >= p.smin;

  /** Leader: close the lobby and start the game. */
  p.start = () => {
    if (!p.canStart()) throw new Error(`start(): ${p.state === "lead" ? "not enough Splats" : "no open lobby"}`);
    p.wands = roster();
    p.pool = [];
    p.wands.forEach((w, wi) => { for (let k = 0; k < w[2]; k++) p.pool.push([wi, k]); });
    p.me = 0;
    p.first = 0;
    for (const m of p.members) {
      m.seen = now();
      m.lost = false;
    }
    for (const [m] of p.wands.slice(1)) {
      out(m, { type: "pw_start", id: p.id, wands: p.wands, pool: p.pool.length });
    }
    p.state = "lead_game";
    p.events = [];
    hbAt = now() - PW.HEARTBEAT_MS;
    note(`game started with ${p.wands.length} wands, ${p.pool.length} Splats`);
    p.script?.onStart?.(p);
    changed();
  };

  /** Leader: end the lobby or the game for everyone. */
  p.end = () => {
    if (p.state !== "lead" && p.state !== "lead_game") return;
    for (const m of p.members.slice(1)) out(m.mac, { type: "pw_end", id: p.id });
    gameOver("ended");
    changed();
  };

  /** Follower: leave the game (the wand's stop card). */
  p.leave = () => {
    if (p.state !== "game" && p.state !== "lobby" && p.state !== "join") return;
    out(p.leader, { type: "pw_leave", id: p.id });
    gameOver("left");
    changed();
  };

  /** Pool size in the game (leader) or this wand's share of it (follower). */
  p.poolSize = () => (p.wands || []).reduce((n, w) => n + w[2], 0);

  /** Owner wand index of pool Splat i. */
  p.owner = (i) => {
    let n = 0;
    for (let w = 0; w < p.wands.length; w++) {
      n += p.wands[w][2];
      if (i < n) return w;
    }
    return -1;
  };

  /** Leader: run op on pool Splat i, locally or as pw_cmd to its owner. */
  p.cmd = (i, op, v = null) => {
    const w = p.owner(i);
    if (w < 0) return false;
    const k = i - p.wands.slice(0, w).reduce((n, x) => n + x[2], 0);
    if (w === p.me) {
      const s = p.splats[k];
      if (!s.ready) return false;
      s.applyAction(op, v);
      return true;
    }
    return sendQ(p.wands[w][0], { type: "pw_cmd", id: p.id, s: k, op, v });
  };

  /** net.send(): a game message to wand index `to`, or every other wand with null. */
  p.send = (to, data) => {
    if (p.state !== "game" && p.state !== "lead_game") return false;
    const targets = to === null ? p.wands.map((_, i) => i).filter((i) => i !== p.me) : [to];
    let ok = true;
    for (const w of targets) ok = !!sendQ(p.wands[w][0], { type: "pw_msg", id: p.id, d: data }) && ok;
    return ok;
  };

  /** A press (down = true) or release on this peer's Splat s. */
  p.splatButton = (s, down) => {
    const splat = p.splats[s];
    splat.setPressed(down);
    if (!splat.ready) return;
    if (p.state === "game") {
      sendQ(p.leader, { type: "pw_evt", id: p.id, s: p.first + s, e: down ? 1 : 0 });
      event([down ? "press" : "release", s]);
    } else if (p.state === "lead_game") {
      event([down ? "press" : "release", s]);
    }
  };

  /** Unplug (false) or reconnect a Splat: it drops out of the heartbeat mask. */
  p.setSplatReady = (s, up) => p.splats[s].setReady(up);

  /** The peer wand's own button: what it does is the game script's. */
  p.button = () => {
    p.script?.onButton?.(p);
    changed();
  };

  /** Silence the peer: it sends and hears nothing (attachPeer also stops its ACKs). */
  p.drop = (on) => {
    p.dropped = !!on;
    if (!on) {
      seenLeader = now();
      for (const m of p.members) m.seen = now();
    }
    changed();
  };

  p.note = note;
  return p;
}

// ── game scripts ──────────────────────────────

/** lobbytest: a follower's button asks the leader to light the next Splat. */
const lobbytest = {
  onStart(p) {
    p.scriptState = { next: 0, prev: null };
  },
  lightNext(p, presser) {
    const st = p.scriptState;
    const n = p.poolSize();
    if (!n) return;
    const i = st.next % n;
    st.next++;
    p.cmd(i, "color", p.wands[presser][1]);
    if (st.prev !== null && st.prev !== i) p.cmd(st.prev, "color", "turnoff");
    st.prev = i;
    p.note(`lobbytest: wand ${presser} lit pool Splat ${i}`);
  },
  onButton(p) {
    if (p.state === "game") {
      p.send(0, { btn: 1 });
      p.note("lobbytest: button -> leader");
    } else if (p.state === "lead_game") {
      lobbytest.lightNext(p, 0);
    }
  },
  onEvent(p, ev) {
    if (p.state !== "lead_game") return;
    if (ev[0] === "msg" && ev[2] && ev[2].btn === 1) lobbytest.lightNext(p, ev[1]);
    else if (ev[0] === "press") p.cmd(ev[1], "color", p.wands[p.owner(ev[1])][1]);
  },
};

/** relaycolor: whoever holds the token shows its color; a button or Splat press passes it on. */
const RELAY_COLORS = ["turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite"];
const relaycolor = {
  onStart(p) {
    p.scriptState = { holding: null };
    for (const s of p.splats) s.applyAction("color", "turnoff");
    if (p.state === "lead_game") relaycolor.take(p, 0);
  },
  take(p, c) {
    p.scriptState.holding = c;
    for (const s of p.splats) if (s.ready) s.applyAction("color", RELAY_COLORS[c]);
    p.note(`relaycolor: holding ${RELAY_COLORS[c]}`);
  },
  give(p) {
    const st = p.scriptState;
    if (st.holding === null || p.wands.length < 2) return;
    const c = (st.holding + 1) % RELAY_COLORS.length;
    const to = (p.me + 1) % p.wands.length;
    if (p.send(to, { relay: c })) {
      st.holding = null;
      for (const s of p.splats) if (s.ready) s.applyAction("color", "turnoff");
      if (p.state === "game") p.send(0, { holder: to, c });
      p.note(`relaycolor: passed ${RELAY_COLORS[c]} to wand ${to}`);
    }
  },
  onButton(p) {
    relaycolor.give(p);
  },
  onEvent(p, ev) {
    if (ev[0] === "msg" && ev[2] && Number.isInteger(ev[2].relay)) relaycolor.take(p, ev[2].relay);
    else if (ev[0] === "press") relaycolor.give(p);
  },
  onEnd(p) {
    p.scriptState = { holding: null };
  },
};

export const GAME_SCRIPTS = { lobbytest, relaycolor };

/**
 * Put a peer on a bus (js/bus.js): frames go out as JSON, and the bus
 * delivers to receive(). With tickMs, tick() runs on a real-time interval.
 * Returns { detach(), setDropped(on) }; a dropped peer is off the bus, so
 * unicasts to it go unacknowledged, as with a wand out of range.
 */
export function attachPeer(bus, peer, { tickMs = 10 } = {}) {
  let detachBus = bus.attach(peer.mac, (src, payload) => peer.receive(src, payload));
  peer.transport = (dst, msg) => {
    const to = dst === "*" ? BROADCAST : normalizeMac(dst);
    bus.send(peer.mac, to, enc.encode(JSON.stringify(msg)));
    // The ACK: a unicast counts only if the destination is on the bus.
    return to === BROADCAST || bus.macs().includes(to);
  };
  const timer = tickMs ? setInterval(() => peer.tick(), tickMs) : null;
  return {
    detach() {
      if (timer !== null) clearInterval(timer);
      peer.transport = null;
      detachBus?.();
      detachBus = null;
    },
    setDropped(on) {
      peer.drop(on);
      if (on && detachBus) {
        detachBus();
        detachBus = null;
      } else if (!on && !detachBus) {
        detachBus = bus.attach(peer.mac, (src, payload) => peer.receive(src, payload));
      }
    },
  };
}
