/**
 * Headless room: the simulated wand (Pyodide, js/pyboot.js), its Splats and
 * virtual peers (js/party.js) on one bus and clock, with no DOM. Used by
 * tools/sim_run.mjs; runs anywhere Pyodide does.
 *
 *   createHeadlessRoom({ pyodide, readText, scale })
 *     scale: virtual ms per real ms (the clock and time_patch share it)
 *
 *   simRunWith(room, { game | code, seconds, seed }) runs a party game
 *   through the scenarios below and returns
 *     { ok, exceptions[], unhandled[], warnings[], scenarios[], prints[] }
 *
 * Scenarios, each on a fresh start of the game:
 *   lead    the wand leads, follower peers fill the lobby to SPLATS_MIN, the
 *           wand's button starts it; `seconds` of random Splat presses and
 *           button presses; then the stop card, which must end play() on
 *           the wand (a warning if not).
 *   follow  a leader peer leads and starts with the wand in its lobby;
 *           seconds/2 of play; the leader ends the game, and play() must
 *           return ("end" unhandled if it does not).
 *   lost    as follow, but the leader goes silent: play() must return
 *           after WAND_LOST_MS ("leader_lost" unhandled if it does not).
 */

import { createBus, BROADCAST } from "./bus.js";
import { createClock } from "./clock.js";
import { hexToBytes } from "./radio.js";
import { bootWand, wireCallbacks, attachWand } from "./pyboot.js";
import { createPartyHost } from "./party.js";
import { PW } from "./peers.js";

export const WAND_MAC = "02:00:00:00:0a:01";
const RETURN_MS = 3000;     // how long play() may take to return after the end
const PLAY_MAX_LINES = 2000;

export async function createHeadlessRoom({ pyodide, readText, scale = 4 }) {
  const clock = createClock({ scale });
  const bus = createBus({ clock });
  await bootWand(pyodide, readText);
  const out = { prints: [], errors: [] };
  await wireCallbacks(pyodide, {
    set_print_callback: (t) => {
      out.prints.push(String(t));
      if (out.prints.length > PLAY_MAX_LINES) out.prints.shift();
    },
    set_error_callback: (t) => out.errors.push(String(t)),
    set_log_callback: () => {},
    set_led_callback: () => {},
    set_pwm_callback: () => {},
    set_motor_callback: () => {},
    set_enow_sent_callback: () => {},
  });
  const wandLink = attachWand(pyodide, {
    bus, clock, mac: WAND_MAC,
    tx: (src, dst, hex) => {
      bus.send(src, dst, hexToBytes(hex));
      return dst === BROADCAST || bus.macs().includes(dst) ? 1 : 0;
    },
  });
  const party = createPartyHost({ bus, clock, py: pyodide, wandMac: WAND_MAC });
  const rt = pyodide.pyimport("runtime").get_runtime();
  const simState = pyodide.pyimport("sim_state");
  const room = {
    pyodide, clock, bus, party, out, rt,
    dispose() {
      party.dispose();
      wandLink.detach();
    },
    /** Wait `ms` of virtual time. */
    wait: (ms) => new Promise((r) => setTimeout(r, clock.toRealMs(ms))),
    async load(gameOrCode) {
      pyodide.globals.set("_headless_src", gameOrCode);
      await pyodide.runPythonAsync("load_game(_headless_src)");
      const proxy = await pyodide.runPythonAsync("get_capabilities()");
      const caps = proxy.toJs({ dict_converter: Object.fromEntries });
      proxy.destroy();
      return caps;
    },
    start: () => pyodide.runPythonAsync("await start()"),
    stop: () => pyodide.runPythonAsync("await stop()"),
    running: () => rt.is_running(),
    /** party.Net phase of the running game ("game", "ended", ...) or null. */
    netPhase() {
      const net = rt.net;
      if (net === undefined || net === null) return null;
      const phase = String(net.phase);
      net.destroy?.();
      return phase;
    },
    async button(ms = 120) {
      simState.set_button(true);
      await room.wait(ms);
      simState.set_button(false);
    },
    tapNfc: (cmd) => simState.tap_nfc(cmd),
  };
  return room;
}

/** Small deterministic PRNG (mulberry32). */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

async function until(room, test, ms, step = 50) {
  for (let waited = 0; waited <= ms; waited += step) {
    if (test()) return true;
    await room.wait(step);
  }
  return test();
}

/** Every Splat in the room: [{ press(down), label }]. */
function allSplats(party) {
  const list = party.wandSplats.map((s, i) => ({
    label: `wand Splat ${i}`, press: (down) => party.wandSplatButton(i, down),
  }));
  for (const { peer } of party.peers) {
    peer.splats.forEach((s, i) => list.push({
      label: `${peer.name} Splat ${i}`, press: (down) => peer.splatButton(i, down),
    }));
  }
  return list;
}

/** Random play for `ms`: Splat presses, the wand's button, peer buttons. */
async function randomPlay(room, ms, rand, actions) {
  const end = room.clock.nowMs() + ms;
  while (room.clock.nowMs() < end && room.running()) {
    await room.wait(300 + rand() * 600);
    const r = rand();
    if (r < 0.6) {
      const splats = allSplats(room.party);
      if (!splats.length) continue;
      const s = splats[Math.floor(rand() * splats.length)];
      s.press(true);
      await room.wait(150);
      s.press(false);
      actions.push(s.label);
    } else if (r < 0.8) {
      await room.button();
      actions.push("wand button");
    } else if (room.party.peers.length) {
      const { peer } = room.party.peers[Math.floor(rand() * room.party.peers.length)];
      peer.button();
      actions.push(`${peer.name} button`);
    }
  }
}

function resetPeers(party) {
  for (const { peer } of [...party.peers]) party.removePeer(peer);
}

/** Follower peers with one Splat each until the lobby (wand included) reaches `need`. */
function addFollowers(party, have, need, max) {
  while (have < need && (max === null || have < max)) {
    party.addPeer({ mode: "follower", splats: 1 });
    have += 1;
  }
  return have;
}

/** True (after noting it) when play() has already returned or raised. */
function gone(room, res) {
  if (room.running()) return false;
  if (!room.out.errors.length) res.warnings.push("play() returned before the game was over");
  return true;
}

async function scenarioLead(room, slug, caps, seconds, rand) {
  const { party } = room;
  const res = { name: "lead", problems: [], warnings: [], actions: [] };
  resetPeers(party);
  const smin = caps.splats_min ?? 1;
  const smax = caps.splats_max ?? null;
  // At least one peer, so there is a party to play with.
  addFollowers(party, party.wandSplats.length, Math.max(smin, party.wandSplats.length + 1), smax);
  party.setGame(slug, caps);
  await room.start();
  const joined = await until(room, () => {
    const lobby = party.peers.every(({ peer }) => peer.state === "lobby" || peer.state === "game");
    return lobby || room.netPhase() === "game" || !room.running();
  }, 4000);
  if (!joined) {
    res.problems.push("the peers never got into the wand's lobby");
    return res;
  }
  if (gone(room, res)) return res;
  if (room.netPhase() !== "game") await room.button();
  if (!await until(room, () => room.netPhase() === "game" || !room.running(), 3000)) {
    res.problems.push("the wand's button did not start the game");
    return res;
  }
  if (gone(room, res)) return res;
  await randomPlay(room, seconds * 1000, rand, res.actions);
  if (room.running()) {
    room.tapNfc("stop");
    if (!await until(room, () => !room.running(), RETURN_MS)) {
      res.warnings.push("the stop card did not end play() on the leading wand");
    }
  } else {
    res.warnings.push("play() returned before the time was up");
  }
  return res;
}

async function scenarioFollow(room, slug, caps, seconds, rand, { lose }) {
  const { party } = room;
  const res = { name: lose ? "lost" : "follow", problems: [], warnings: [], actions: [] };
  resetPeers(party);
  const smin = caps.splats_min ?? 1;
  const smax = caps.splats_max ?? null;
  const leader = party.addPeer({ mode: "leader", splats: smin > party.wandSplats.length + 1 ? 2 : 1 });
  addFollowers(party, party.wandSplats.length + leader.splats.length, smin, smax);
  party.setGame(slug, caps);
  await room.wait(100);
  await room.start();
  const all = party.peers.length + 1;
  if (!await until(room, () => (leader.members.length >= all && leader.canStart()) || !room.running(), 4000)) {
    res.problems.push(`the wand did not join the leader's lobby (${leader.members.length} of ${all} wands)`);
    return res;
  }
  if (gone(room, res)) return res;
  leader.start();
  if (!await until(room, () => room.netPhase() === "game" || !room.running(), 3000)) {
    res.problems.push("the wand did not start on the leader's pw_start");
    return res;
  }
  if (gone(room, res)) return res;
  await randomPlay(room, lose ? 2000 : (seconds * 1000) / 2, rand, res.actions);
  if (!room.running()) {
    res.warnings.push("play() returned before the time was up");
    return res;
  }
  if (lose) {
    party.peerDropped(leader, true);
    if (!await until(room, () => !room.running(), PW.WAND_LOST_MS + RETURN_MS)) {
      res.problems.push("leader_lost");
    }
  } else {
    leader.end();
    if (!await until(room, () => !room.running(), RETURN_MS)) res.problems.push("end");
  }
  return res;
}

/**
 * Run a party game through the lead, follow and lost scenarios. `game` is a
 * vendored game's name, `code` a game's source; seconds is the lead
 * scenario's play time (follow plays half of it).
 */
export async function simRunWith(room, { game = null, code = null, seconds = 20, seed = 1 }) {
  const rand = rng(seed);
  const result = { ok: false, exceptions: [], unhandled: [], warnings: [], scenarios: [], prints: [] };
  let caps;
  try {
    caps = await room.load(code ?? game);
  } catch (err) {
    result.exceptions.push(`load: ${String(err.message || err).split("\n").filter(Boolean).pop()}`);
    return result;
  }
  if (!caps.party) {
    result.warnings.push("not a party game (no SPLATS_MIN); nothing to simulate");
    result.ok = true;
    return result;
  }
  const slug = code ? "custom" : game;
  const scenarios = [
    () => scenarioLead(room, slug, caps, seconds, rand),
    () => scenarioFollow(room, slug, caps, seconds, rand, { lose: false }),
    () => scenarioFollow(room, slug, caps, seconds, rand, { lose: true }),
  ];
  for (const run of scenarios) {
    room.out.errors.length = 0;
    const printed = room.out.prints.length;
    let res;
    try {
      res = await run();
    } catch (err) {
      res = { name: "?", problems: [`harness: ${err.message || err}`], warnings: [], actions: [] };
    }
    await room.stop();
    room.party.setGame(null, null);
    await room.wait(PW.WAND_LOST_MS);  // let the last game's peers time out
    for (const e of room.out.errors) result.exceptions.push(`${res.name}: ${e}`);
    for (const p of res.problems) {
      if (p === "end" || p === "leader_lost") result.unhandled.push(`${res.name}: ${p}`);
      else result.exceptions.push(`${res.name}: ${p}`);
    }
    for (const w of res.warnings) result.warnings.push(`${res.name}: ${w}`);
    for (const line of room.out.prints.slice(printed)) {
      if (!/\[(ERR|WARN)\]/.test(line)) continue;
      // party.py's own goodbye to a leader that is gone: expected in "lost".
      if (res.name === "lost" && /pw_leave to .* failed/.test(line)) continue;
      result.warnings.push(`${res.name}: ${line.trim()}`);
    }
    result.scenarios.push({ name: res.name, problems: res.problems, warnings: res.warnings,
                            actions: res.actions.length });
  }
  result.prints = room.out.prints.slice();
  result.ok = !result.exceptions.length && !result.unhandled.length;
  return result;
}
