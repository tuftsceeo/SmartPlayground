/**
 * Other wands for <sim-room>: the wands a party game is played with beside
 * the simulated one. Advanced mode only (sim-room's style hides it
 * otherwise); simple mode is the one wand.
 *
 * The room starts a party game with `wands - 1` other wands from its
 * settings (none by default), and "+ Add a wand" adds one, up to MAX_WANDS
 * in all. Wands have no names or colors here: the bar says only how many
 * more there are.
 *
 * Another wand starts as a placeholder: an outline of a wand with "?" on
 * its screen that runs nothing and is not on the radio. Clicking it starts
 * a real <wand-sim> running the room's game, on the room's bus and clock
 * with its own MAC and Splats, so party.py on each wand plays the real
 * protocol. Each one boots its own Pyodide, which is why they wait for a
 * click.
 *
 * "See all N wands" opens a near-full-screen <dialog> with every wand side
 * by side: the room's own wand is moved into it while it is open (a
 * <wand-sim> survives the move) and back when it closes. Live other wands
 * live in the dialog and keep running while it is closed. The radio
 * message log is at the bottom of the dialog.
 *
 *   createWandsPanel({ mount, room })
 *     .setFor(n)         a game for n wands loaded: n - 1 placeholders
 *     .setGame(caps)     the room loaded a party game (caps); live wands follow
 *     .pushSource()      the room's source or game changed; live wands reload
 *     .setGameSplats(n)  Splats each live wand starts the next load with
 *     .restart()         restart every live other wand
 *     .clear()           drop every other wand (a non-party game loaded)
 *     .pushLog(line, frame) / .clearLog()
 */

import { icon } from "../icons.js";
import { attachWand } from "../pyboot.js";
import { createPartyHost } from "../party.js";
import { createSplatToy, CASE, BLOB } from "./splats.js";

export const MAX_WANDS = 4;
const LOG_LIMIT = 120;

/** The other wands' MACs follow the room's wand (…:0a:01), so it leads a tie. */
function otherMac(i) {
  return `02:00:00:00:0a:${(i + 2).toString(16).padStart(2, "0")}`;
}

/** A Splat drawn in outline only, for a placeholder wand. */
const SPLAT_OUTLINE = `<svg viewBox="-6 -6 268 267" width="44" height="44" aria-hidden="true">
  <path d="${CASE}"/><path d="${BLOB}"/></svg>`;

export const WANDS_STYLE = `
.wands-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; min-height: 64px;
  padding: 10px 12px 10px 16px; box-sizing: border-box; }
.wands-bar .lead { color: #6c4cd1; display: inline-flex; }
.wands-bar .count { font: 800 14px 'Nunito', system-ui, sans-serif; }
.wands-bar .acts { margin-left: auto; display: flex; flex-wrap: wrap; gap: 8px; }
.wbtn { min-height: 44px; padding: 0 14px; border-radius: 12px; border: 1.5px solid #e8e6f0;
  background: #fff; color: #5b5468; font: 800 12px 'Nunito', system-ui, sans-serif; cursor: pointer; }
.wbtn:hover { border-color: #6c4cd1; color: #6c4cd1; }
.wbtn.primary { border-color: #6c4cd1; background: #f2eefc; color: #6c4cd1; }
.wbtn.sq { width: 44px; padding: 0; display: inline-flex; align-items: center; justify-content: center; }
.wbtn.small { min-height: 36px; }
.wbtn.small.sq { width: 36px; }
.wbtn:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(108,76,209,.2); }
.wbtn[hidden] { display: none; }

dialog.all-wands { width: calc(100vw - 64px); height: calc(100vh - 64px); max-width: none; max-height: none;
  margin: auto; padding: 20px 24px 24px; box-sizing: border-box; border: 0; border-radius: 20px;
  background: #fff; color: #231f2e; font-family: 'Nunito', system-ui, sans-serif;
  box-shadow: 0 24px 60px rgba(0,0,0,.22); }
dialog.all-wands[open] { display: flex; flex-direction: column; gap: 16px; }
dialog.all-wands::backdrop { background: rgba(35,31,46,.35); }
.aw-head { display: flex; align-items: center; gap: 10px; }
.aw-head h2 { margin: 0; font: 800 18px 'Nunito', system-ui, sans-serif; }
.aw-head .wbtn:first-of-type { margin-left: auto; }
.aw-grid { flex: 1 1 auto; min-height: 0; overflow-y: auto; display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 24px; align-content: start; }
.wand-card { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.wand-card .chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-height: 36px; }
.wand-card .chip { font: 800 11px 'Nunito', system-ui, sans-serif; padding: 3px 9px; border-radius: 20px; }
.wand-card .chip.mine { background: #fff0f6; color: #b3326b; }
.wand-card .chip.playing { background: #e9fbf6; color: #14806b; }
.wand-card .chips .wbtn { margin-left: auto; }
.wand-card wand-sim { display: block; width: 100%; }

.ghost-wand { position: relative; display: flex; align-items: center; gap: 20px; width: 100%; min-height: 320px;
  padding: 20px; box-sizing: border-box; border-radius: 24px; border: 2px solid #d8d4e6; background: #fff;
  font-family: 'Nunito', system-ui, sans-serif; color: #231f2e; text-align: left; cursor: pointer; }
.ghost-wand:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(108,76,209,.2); }
.ghost-wand .pad { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 14px;
  padding: 18px 22px; border-radius: 20px; border: 2px solid #e8e6f0; }
.ghost-wand .body { position: relative; width: 120px; height: 190px; box-sizing: border-box; border-radius: 22px;
  border: 3px solid #c2b8d6; display: flex; flex-direction: column; align-items: center; padding-top: 36px; gap: 16px; }
.ghost-wand .body .led { position: absolute; top: 10px; left: 12px; width: 8px; height: 8px; box-sizing: border-box;
  border-radius: 50%; border: 2px solid #c2b8d6; }
.ghost-wand .body .nfc { position: absolute; top: 8px; right: 9px; width: 24px; height: 24px; box-sizing: border-box;
  border-radius: 50%; border: 2px solid #c2b8d6; }
.ghost-wand .screen { width: 82px; height: 82px; box-sizing: border-box; border-radius: 10px; border: 2px solid #c2b8d6;
  display: flex; align-items: center; justify-content: center; font: 900 44px/1 'Nunito', system-ui, sans-serif; color: #8b859a; }
.ghost-wand .btn { width: 48px; height: 48px; box-sizing: border-box; border-radius: 50%; border: 3px solid #c2b8d6; }
.ghost-wand .splats { display: flex; gap: 10px; }
.ghost-wand .splats svg { display: block; fill: none; stroke: #c2b8d6; stroke-width: 8; }
.ghost-wand .text { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.ghost-wand .text b { font: 800 20px 'Nunito', system-ui, sans-serif; }
.ghost-wand .text span { font: 700 13px/1.45 'Nunito', system-ui, sans-serif; color: #5b5468; }

.aw-radio { border-top: 1px solid #f4f2fa; padding-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.aw-radio .radio-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  font: 700 11px 'Nunito', system-ui, sans-serif; color: #5b5468; }
.aw-radio .radio-head > span { font: 800 10px 'Nunito', system-ui, sans-serif; letter-spacing: .06em; }
.aw-radio .radio-head label { display: flex; align-items: center; gap: 6px; }
.aw-radio .radio-head input { accent-color: #ef4d92; margin: 0; }
.aw-radio .radio-head button { margin-left: auto; font: 700 11px 'Nunito', system-ui, sans-serif; padding: 6px 11px;
  border-radius: 12px; border: 1.5px solid #e8e6f0; background: #fff; color: #5b5468; cursor: pointer; }
.aw-radio .buslog { margin: 0; height: 72px; overflow-y: auto; background: #f7f7fb; border-radius: 10px; padding: 8px 10px;
  font: 400 11px/1.5 ui-monospace, monospace; color: #3a3345; white-space: pre-wrap; word-break: break-all; }
.aw-radio .buslog:empty::before { content: "no radio messages yet"; color: #5b5468; }
`;

export function createWandsPanel({ mount, room }) {
  const bar = document.createElement("div");
  bar.className = "wands-bar";
  bar.innerHTML = `<span class="lead">${icon("wand", 18)}</span>
    <span class="count" data-el="count"></span>
    <span class="acts">
      <button type="button" class="wbtn" data-el="add">+ Add a wand</button>
      <button type="button" class="wbtn primary" data-el="open"></button>
    </span>`;
  mount.appendChild(bar);

  const dialog = document.createElement("dialog");
  dialog.className = "all-wands";
  dialog.setAttribute("aria-label", "All wands in this game");
  dialog.innerHTML = `<div class="aw-head">
      <h2 data-el="title"></h2>
      <button type="button" class="wbtn" data-el="add">+ Add a wand</button>
      <button type="button" class="wbtn sq" data-el="close" aria-label="Close">${icon("close", 18)}</button>
    </div>
    <div class="aw-grid" data-el="grid"></div>
    <div class="aw-radio">
      <div class="radio-head"><span>RADIO MESSAGES</span>
        <label><input type="checkbox" data-el="show-hb"> Show heartbeats and lobby beacons</label>
        <button type="button" data-el="clear-log">Clear</button></div>
      <pre class="buslog" data-el="buslog"></pre>
    </div>`;
  mount.appendChild(dialog);

  const $ = (root, el) => root.querySelector(`[data-el="${el}"]`);
  const grid = $(dialog, "grid");
  const log = $(dialog, "buslog");
  const showHb = $(dialog, "show-hb");
  const lines = [];

  /** The room's own wand card; its <wand-sim> moves in while the dialog is open. */
  const mine = document.createElement("div");
  mine.className = "wand-card";
  mine.innerHTML = `<div class="chips"><span class="chip mine">This wand</span></div>`;
  grid.appendChild(mine);

  /** [{ mac, card, el, link, party, pad, toys }] in order; el null = placeholder. */
  let others = [];
  let caps = null;
  let gameSplats = 1;

  for (const b of [$(bar, "add"), $(dialog, "add")]) b.addEventListener("click", () => add());
  $(bar, "open").addEventListener("click", () => open());
  $(dialog, "close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    room.placeWand(null);
  });
  $(dialog, "clear-log").addEventListener("click", () => clearLog());
  showHb.addEventListener("change", () => drawLog());

  function open() {
    room.placeWand(mine);
    if (!dialog.open) dialog.showModal();
  }

  function draw() {
    const n = others.length;
    $(bar, "count").textContent = n === 0 ? "No other wands are playing."
      : n === 1 ? "1 more wand is also playing" : `${n} more wands are also playing`;
    const full = n + 1 >= MAX_WANDS;
    $(bar, "add").hidden = full;
    $(dialog, "add").hidden = full;
    const openBtn = $(bar, "open");
    openBtn.hidden = n === 0;
    openBtn.textContent = `See all ${n + 1} wands →`;
    $(dialog, "title").textContent = `${n + 1} wands in this game`;
    if (n === 0 && dialog.open) dialog.close();
  }

  function freeMac() {
    for (let i = 0; ; i++) {
      const mac = otherMac(i);
      if (!others.some((o) => o.mac === mac)) return mac;
    }
  }

  function add() {
    if (others.length + 1 >= MAX_WANDS) return;
    const o = { mac: freeMac(), card: document.createElement("div"), el: null };
    o.card.className = "wand-card";
    others.push(o);
    grid.appendChild(o.card);
    drawCard(o);
    draw();
  }

  function remove(o) {
    stopLive(o);
    o.card.remove();
    others = others.filter((x) => x !== o);
    draw();
  }

  function drawCard(o) {
    o.card.textContent = "";
    const chips = document.createElement("div");
    chips.className = "chips";
    if (o.el) chips.innerHTML = `<span class="chip playing">Playing</span>`;
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "wbtn small sq";
    rm.setAttribute("aria-label", "Take this wand away");
    rm.innerHTML = icon("close", 15);
    rm.addEventListener("click", () => remove(o));
    chips.appendChild(rm);
    o.card.appendChild(chips);
    if (o.el) {
      o.card.appendChild(o.el);
      return;
    }
    const ghost = document.createElement("button");
    ghost.type = "button";
    ghost.className = "ghost-wand";
    ghost.setAttribute("aria-label", "Another wand. Click for simulation.");
    ghost.innerHTML = `<span class="pad">
        <span class="body"><span class="led"></span><span class="nfc"></span>
          <span class="screen">?</span><span class="btn"></span></span>
        <span class="splats">${SPLAT_OUTLINE.repeat(gameSplats)}</span>
      </span>
      <span class="text"><b>Click for simulation</b>
        <span>This starts another copy of the game, which can slow the page down.</span></span>`;
    ghost.addEventListener("click", () => goLive(o));
    o.card.appendChild(ghost);
  }

  function slug() {
    return room.source ? "custom" : String(room.game || "").replace(/\.py$/, "");
  }

  function loadInto(w) {
    if (room.source) w.source = room.source;
    else w.setAttribute("game", room.game);
  }

  function goLive(o) {
    if (o.el) return;
    const w = document.createElement("wand-sim");
    w.autostart = true;
    if (room.profile) w.profile = room.profile;
    const pad = document.createElement("div");
    pad.className = "pad-splats";
    pad.slot = "pad";
    o.el = w;
    o.pad = pad;
    o.toys = [];
    w.addEventListener("sim-ready", () => {
      if (o.el !== w) return;
      const py = w.pyodide;
      o.link = attachWand(py, { bus: room.bus, clock: room.clock, mac: o.mac, tx: (s, d, h) => room._tx(s, d, h) });
      py.pyimport("runtime").set_game_splats(gameSplats);
      o.party = createPartyHost({ bus: room.bus, clock: room.clock, py, wandMac: o.mac });
      let queued = false;
      o.party.onChange(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          drawToys(o);
        });
      });
    });
    w.addEventListener("sim-loaded", (e) => {
      if (o.el !== w || !o.party) return;
      o.party.setGame(slug(), e.detail?.capabilities || caps);
      drawToys(o);
    });
    loadInto(w);
    drawCard(o);
  }

  function drawToys(o) {
    const splats = o.party?.wandSplats || [];
    const key = splats.map((s) => s.mac).join("+");
    if (key !== o.toysKey) {
      o.toysKey = key;
      o.pad.textContent = "";
      o.toys = splats.map((s, i) => createSplatToy(s, {
        label: `Splat ${i + 1}`,
        onButton: (down) => o.party.wandSplatButton(i, down),
      }));
      for (const t of o.toys) o.pad.appendChild(t.el);
      if (splats.length) o.el.appendChild(o.pad);
      else o.pad.remove();
    }
    for (const t of o.toys) t.refresh();
  }

  function stopLive(o) {
    if (!o.el) return;
    o.link?.detach();
    o.party?.dispose();
    o.el.remove();
    o.el = o.link = o.party = o.pad = null;
    o.toysKey = undefined;
  }

  function clear() {
    for (const o of others) {
      stopLive(o);
      o.card.remove();
    }
    others = [];
    if (dialog.open) dialog.close();
    draw();
  }

  function drawLog() {
    log.textContent = lines.filter((l) => showHb.checked || !l.beacon).map((l) => l.text).join("\n");
    log.scrollTop = log.scrollHeight;
  }

  function pushLog(text, frame) {
    const beacon = ["pw_hb", "pw_lobby", "pw_find"].includes(frame?.type);
    lines.push({ text, beacon });
    if (lines.length > LOG_LIMIT) lines.shift();
    if (beacon && !showHb.checked) return;
    drawLog();
  }

  function clearLog() {
    lines.length = 0;
    drawLog();
  }

  draw();
  return {
    setFor(n) {
      clear();
      for (let i = 1; i < Math.min(n, MAX_WANDS); i++) add();
    },
    setGame(c) {
      caps = c;
    },
    pushSource() {
      for (const o of others) {
        if (!o.el) continue;
        if (o.el.pyodide) o.el.pyodide.pyimport("runtime").set_game_splats(gameSplats);
        loadInto(o.el);
      }
    },
    setGameSplats(n) {
      gameSplats = n;
      for (const o of others) if (!o.el) drawCard(o);
    },
    restart() {
      for (const o of others) o.el?.restart();
    },
    clear,
    pushLog,
    clearLog,
  };
}
