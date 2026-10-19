// Run: node --test tests/js/*.test.mjs
//
// Virtual peers (js/peers.js) against each other on a manual bus and clock:
// a leader peer and follower peers through lobby, game and end, in the
// frames MockWand/lib/party.py sends. The wand's own side of the protocol
// is tests/test_party.py; tools/sim_run.mjs runs the two together.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createClock } from "../../js/clock.js";
import { createBus } from "../../js/bus.js";
import { createPeer, attachPeer, identityName, splatMac, PALETTE, PW } from "../../js/peers.js";
import { COLOR_RGB, NOTE_VALUES, ANIMAL_SOUNDS } from "../../js/splats.js";

const SIM = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function room(settings = {}) {
  const clock = createClock({ manual: true });
  const bus = createBus({ clock, autoRun: false, settings, rng: () => 0.5 });
  const peers = [];
  const add = (opts) => {
    const p = createPeer({ clock, ...opts });
    attachPeer(bus, p, { tickMs: 0 });
    peers.push(p);
    return p;
  };
  /** Advance `ms` in 10 ms steps, delivering and ticking as the room would. */
  const run = (ms) => {
    for (let t = 0; t < ms; t += 10) {
      clock.advance(10);
      bus.pump();
      for (const p of peers) p.tick();
    }
  };
  const sent = (type) => bus.log.filter((e) => e.event === "send")
    .map((e) => ({ src: e.src, dst: e.dst, d: JSON.parse(new TextDecoder().decode(e.payload)) }))
    .filter((f) => f.d.type === type);
  return { clock, bus, add, run, sent };
}

/** A lobby with a leader peer (1 Splat) and a follower (1 Splat), started. */
function started(slug = "partytest") {
  const r = room();
  const leader = r.add({ mac: "02:00:00:00:01:01", mode: "leader", name: "leader" });
  const follower = r.add({ mac: "02:00:00:00:0b:02", name: "follower" });
  leader.tap(slug, { smin: 2 });
  follower.tap(slug);
  r.run(1500);
  assert.equal(follower.state, "lobby");
  leader.start();
  r.run(50);
  return { ...r, leader, follower };
}

test("identity and Splat MACs follow splatpair and runtime", () => {
  assert.equal(identityName("02:00:00:00:0A:01"), "turngreen");   // 0x01 % 6
  assert.equal(identityName("02:00:00:00:0B:06"), "turnred");     // 0x06 % 6
  assert.deepEqual(PALETTE, ["turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite"]);
  assert.equal(splatMac("02:00:00:00:0a:01", 1), "5A:00:0A:01:00:01");
});

test("splats.js action names match splat_api.py", () => {
  const src = readFileSync(join(SIM, "vendor/lib/splat_api.py"), "utf8");
  const block = (name) => src.slice(src.indexOf(`${name} = {`), src.indexOf("}", src.indexOf(`${name} = {`)));
  const keys = (name) => [...block(name).matchAll(/"([a-z_]+)":/g)].map((m) => m[1]).sort();
  assert.deepEqual(Object.keys(COLOR_RGB).sort(), keys("COLOR_RGB"));
  assert.deepEqual(Object.keys(NOTE_VALUES).sort(), keys("NOTE_VALUES"));
  assert.deepEqual(Object.keys(ANIMAL_SOUNDS).sort(), keys("ANIMAL_SOUNDS"));
  assert.match(block("COLOR_RGB"), /"turnpurple": \(160, 0, 200\)/);
  assert.deepEqual(COLOR_RGB.turnpurple, [160, 0, 200]);
});

test("party.py timing", () => {
  const src = readFileSync(join(SIM, "vendor/lib/party.py"), "utf8");
  const val = (name) => Number(new RegExp(`^${name} = (\\d+)`, "m").exec(src)[1]);
  assert.equal(PW.FIND_WAIT_MS, val("FIND_WAIT_MS"));
  assert.equal(PW.JOIN_WAIT_MS, val("JOIN_WAIT_MS"));
  assert.equal(PW.LOBBY_MS, val("LOBBY_MS"));
  assert.equal(PW.HEARTBEAT_MS, val("HEARTBEAT_MS"));
  assert.equal(PW.WAND_LOST_MS, val("WAND_LOST_MS"));
});

test("a follower finds the lobby, joins and starts", () => {
  const { leader, follower, sent } = started();
  const join = sent("pw_join")[0];
  assert.deepEqual(join.d, { type: "pw_join", id: leader.id, splats: 1 });
  const joined = sent("pw_joined")[0].d;
  assert.equal(joined.first, 1);
  assert.deepEqual(joined.wands.map((w) => w[2]), [1, 1]);
  const start = sent("pw_start")[0].d;
  assert.equal(start.pool, 2);
  assert.deepEqual(start.wands.map((w) => w[0]), ["02:00:00:00:01:01", "02:00:00:00:0B:02"]);
  assert.equal(follower.state, "game");
  assert.equal(follower.me, 1);
  assert.equal(leader.state, "lead_game");
});

test("pooled commands, Splat presses and messages", () => {
  const { leader, follower, run, sent } = started();
  // Pool Splat 1 is the follower's: a pw_cmd it runs on its own Splat.
  leader.cmd(1, "color", "turnblue");
  run(20);
  assert.equal(follower.splats[0].color, "turnblue");
  assert.deepEqual(sent("pw_cmd")[0].d, { type: "pw_cmd", id: leader.id, s: 0, op: "color", v: "turnblue", q: 1 });
  // A press on it reaches the leader as pool Splat 1.
  follower.splatButton(0, true);
  run(20);
  assert.deepEqual(leader.events.at(-1), ["press", 1]);
  assert.equal(sent("pw_evt")[0].d.s, 1);
  // net.send() both ways.
  follower.send(0, { btn: 1 });
  leader.send(1, { s: [1, 0] });
  run(20);
  assert.deepEqual(leader.events.at(-1), ["msg", 1, { btn: 1 }]);
  assert.deepEqual(follower.events.at(-1), ["msg", 0, { s: [1, 0] }]);
});

test("a repeated q is dropped", () => {
  const r = room({ duplicateRate: 1 });
  const leader = r.add({ mac: "02:00:00:00:01:01", mode: "leader" });
  const follower = r.add({ mac: "02:00:00:00:0b:02" });
  leader.tap("g", { smin: 2 });
  follower.tap("g");
  r.run(1500);
  leader.start();
  r.run(50);
  follower.send(0, { n: 1 });
  r.run(20);
  assert.equal(leader.events.filter((e) => e[0] === "msg").length, 1);
});

test("the leader ending sends the follower looking again", () => {
  const { leader, follower, run } = started();
  leader.end();
  run(20);
  assert.deepEqual(follower.events.at(-1), ["end"]);
  assert.equal(follower.lastEnd, "ended");
  assert.equal(follower.state, "find");
});

test("a silent leader is leader_lost after WAND_LOST_MS", () => {
  const { leader, follower, run } = started();
  leader.drop(true);
  run(PW.WAND_LOST_MS - 200);
  assert.equal(follower.state, "game");
  run(400);
  assert.ok(follower.events.some((e) => e[0] === "leader_lost"));
  assert.equal(follower.lastEnd, "leader_lost");
});

test("a silent follower is wand_lost, and wand_back when it returns", () => {
  const { leader, follower, run } = started();
  follower.drop(true);
  run(PW.WAND_LOST_MS + 100);
  assert.ok(leader.events.some((e) => e[0] === "wand_lost" && e[1] === 1));
  follower.drop(false);
  run(PW.HEARTBEAT_MS + 100);
  assert.ok(leader.events.some((e) => e[0] === "wand_back" && e[1] === 1));
});

test("a full lobby turns a joiner away", () => {
  const r = room();
  const leader = r.add({ mac: "02:00:00:00:01:01", mode: "leader", splats: 2 });
  const follower = r.add({ mac: "02:00:00:00:0b:02", splats: 2 });
  leader.tap("g", { smin: 4, smax: 3 });
  follower.tap("g");
  r.run(1500);
  assert.deepEqual(r.sent("pw_end")[0].d, { type: "pw_end", id: leader.id, r: "full" });
  assert.equal(follower.lastEnd, "full");
});

test("SPLATS_MAX reached starts the game", () => {
  const r = room();
  const leader = r.add({ mac: "02:00:00:00:01:01", mode: "leader" });
  const follower = r.add({ mac: "02:00:00:00:0b:02" });
  leader.tap("g", { smin: 2, smax: 2 });
  follower.tap("g");
  r.run(1500);
  assert.equal(leader.state, "lead_game");
  assert.equal(follower.state, "game");
});

test("relaycolor script passes the token around", () => {
  const { leader, follower, run } = started("relaycolor");
  assert.equal(leader.splats[0].color, "turnred");
  leader.button();
  run(20);
  assert.equal(follower.splats[0].color, "turngreen");
  assert.equal(leader.splats[0].color, "turnoff");
  follower.splatButton(0, true);
  follower.splatButton(0, false);
  run(20);
  assert.equal(leader.splats[0].color, "turnblue");
});

test("partytest script: a follower's button lights a pool Splat", () => {
  const { leader, follower, run } = started("partytest");
  follower.button();
  run(20);
  // Pool Splat 0 is the leader's own; lit in the presser's identity color.
  assert.equal(leader.splats[0].color, identityName(follower.mac));
});
