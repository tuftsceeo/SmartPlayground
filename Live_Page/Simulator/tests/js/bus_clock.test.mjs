// Run: node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createClock } from "../../js/clock.js";
import { createBus, normalizeMac, BROADCAST } from "../../js/bus.js";

const A = "aa:aa:aa:aa:aa:01";
const B = "aa:aa:aa:aa:aa:02";
const C = "aa:aa:aa:aa:aa:03";

function setup(settings = {}, rngValues = null) {
  const clock = createClock({ manual: true });
  let i = 0;
  const rng = rngValues ? () => rngValues[i++ % rngValues.length] : () => 0.5;
  const bus = createBus({ clock, autoRun: false, settings, rng });
  const got = { [A]: [], [B]: [], [C]: [] };
  for (const m of [A, B, C]) bus.attach(m, (src, p, meta) => got[m].push([src, p, meta.dup]));
  return { clock, bus, got };
}

test("clock: manual advance and scale rebase", () => {
  let real = 0;
  const c = createClock({ realNow: () => real });
  real = 100;
  assert.equal(c.nowMs(), 100);
  c.setScale(10);
  real = 110;
  assert.equal(c.nowMs(), 200);
  c.pause();
  real = 500;
  assert.equal(c.nowMs(), 200);
  c.advance(50);
  assert.equal(c.nowMs(), 250);
  c.resume();
  real = 501;
  assert.equal(c.nowMs(), 260);
  assert.throws(() => c.setScale(0));
});

test("normalizeMac accepts strings and bytes", () => {
  assert.equal(normalizeMac("AA-BB-CC-DD-EE-FF"), "aa:bb:cc:dd:ee:ff");
  assert.equal(normalizeMac(new Uint8Array([1, 2, 3, 4, 5, 255])), "01:02:03:04:05:ff");
  assert.throws(() => normalizeMac("abc"));
});

test("unicast routes after latency", () => {
  const { clock, bus, got } = setup({ latencyMs: 10 });
  assert.equal(bus.send(A, B, "hi"), 1);
  assert.equal(bus.pump(), 0);
  clock.advance(9);
  assert.equal(bus.pump(), 0);
  clock.advance(1);
  assert.equal(bus.pump(), 1);
  assert.deepEqual(got[B], [[A, "hi", false]]);
  assert.equal(got[C].length, 0);
});

test("broadcast skips sender", () => {
  const { bus, got } = setup({ latencyMs: 0 });
  assert.equal(bus.send(A, BROADCAST, "x"), 2);
  bus.pump();
  assert.equal(got[A].length, 0);
  assert.equal(got[B].length, 1);
  assert.equal(got[C].length, 1);
});

test("drop and duplicate are logged", () => {
  // rng order per target: drop check, then duplicate check.
  const { bus, got } = setup({ latencyMs: 0, dropRate: 0.5, duplicateRate: 0.5 }, [0.9, 0.1, 0.1]);
  bus.send(A, BROADCAST, "m"); // B: kept+dup, C: dropped
  bus.pump();
  assert.equal(got[B].length, 2);
  assert.equal(got[B][1][2], true);
  assert.equal(got[C].length, 0);
  const events = bus.log.map((e) => `${e.event}:${e.dst}`);
  assert.ok(events.includes(`duplicate:${B}`));
  assert.ok(events.includes(`drop:${C}`));
});

test("unknown unicast target is logged as unrouted", () => {
  const { bus } = setup({ latencyMs: 0 });
  bus.send(A, "11:22:33:44:55:66", "lost");
  bus.pump();
  assert.equal(bus.log.at(-1).event, "unrouted");
});

test("settings are validated", () => {
  const { bus } = setup();
  assert.throws(() => bus.setSettings({ dropRate: 2 }));
  assert.throws(() => bus.setSettings({ nope: 1 }));
  bus.setSettings({ jitterMs: 5 });
  assert.equal(bus.getSettings().jitterMs, 5);
});

test("autoRun delivers via timers on a running clock", async () => {
  const clock = createClock({ scale: 1 });
  const bus = createBus({ clock, settings: { latencyMs: 5 } });
  const got = [];
  bus.attach(B, (src, p) => got.push(p));
  bus.send(A, B, "t");
  await new Promise((r) => setTimeout(r, 30));
  assert.deepEqual(got, ["t"]);
});
