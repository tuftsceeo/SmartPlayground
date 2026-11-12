/**
 * Other wands for <sim-room>: the wands a lobby game, or any game whose
 * settings give `wands` > 1, is played with beside the simulated one.
 * Shown in simple and advanced mode. Adding wands and displays happens only
 * in the overlay.
 *
 * The room sets a lobby game up with `wands - 1` other wands from its
 * settings (none by default), and the overlay's "+ Add a wand" adds one, up to MAX_WANDS
 * in all, or the game's `wands` when that is more. Each card is named
 * Wand 1, Wand 2, ... on a purple bar.
 *
 * Each other wand is a real <wand-sim> running the room's game, on the
 * room's bus and clock with its own MAC and Splats, so lobby_game.py on each
 * wand plays the real protocol. Each one boots its own Pyodide, so the
 * wands the settings call for wait as slots until the dialog opens, and
 * then all start; "+ Add a wand" starts one at once.
 *
 * "View Multiple Device Simulation" opens a near-full-screen <dialog> with every wand side
 * by side (drag a card by its name bar to reorder them): the room's own wand is moved into it while it is open (a
 * <wand-sim> survives the move) and back when it closes. Live other wands
 * live in the dialog and are stopped while it is closed; opening and
 * closing it restart the game on every wand that is left running. The room's icon
 * displays (js/panels/display.js) move in after the wands the same way.
 *
 *   createWandsPanel({ mount, room })
 *     .setFor(n)         a game for n wands loaded: n - 1 slots, started when the dialog opens
 *     .setGame(caps)     the room loaded a lobby game (caps); live wands follow
 *     .pushSource()      the room's source or game changed; live wands reload
 *     .setGameSplats(n)  Splats each live wand starts the next load with
 *     .restart()         restart every live other wand
 *     .stop()            stop every live other wand
 *     .clear()           drop every other wand (a non-lobby game loaded)
 *     .redraw()          recount (the room's displays changed)
 *
 * "+ Add a Splat controller" adds a mock-up card of a dedicated Splat
 * companion wand (js/panels/splatController.js); it runs nothing.
 */

import { icon } from "../icons.js";
import { addMinimize, setMinimized } from "./minimize.js";
import { attachWand } from "../pyboot.js";
import { createLobbyGameHost } from "../lobby_game.js";
import { createSplatToy, splatDev, splatCard } from "./splats.js";
import { createSplatController, SPLAT_CONTROLLER_STYLE } from "./splatController.js";

export const MAX_WANDS = 4;

/** The other wands' MACs follow the room's wand (…:0a:01), so it leads a tie. */
function otherMac(i) {
  return `02:00:00:00:0a:${(i + 2).toString(16).padStart(2, "0")}`;
}


export const WANDS_STYLE = `
.wbtn { min-height: 44px; padding: 0 14px; border-radius: 12px; border: 1.5px solid #e8e6f0;
  background: #fff; color: #5b5468; font: 800 12px 'Nunito', system-ui, sans-serif; cursor: pointer; }
.wbtn:hover { border-color: #6c4cd1; color: #6c4cd1; }
.wbtn.go { border-color: #14806b; background: #14806b; color: #fff; }
.wbtn.go:hover { border-color: #0f6655; background: #0f6655; color: #fff; }
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
/* Simple mode: a wand card is as wide as the drawn wand needs. */
:host(:not([advanced])) .aw-grid { grid-template-columns: repeat(auto-fill, 300px); justify-content: start; }
.wand-card { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.wand-card .chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-height: 36px; }
.wand-card .chip { font: 800 11px 'Nunito', system-ui, sans-serif; padding: 3px 9px; border-radius: 20px; }
/* A card's device name: a full-width bar in the device's color (wand
   purple, icon display ink, Splat blue), so each column reads as one
   device; the card's buttons wrap under it. */
.wand-card .chip.device-name { flex: 1 1 100%; box-sizing: border-box;
  cursor: grab; touch-action: none; user-select: none; }
/* Lets the card under the pointer be found while this one is dragged. */
.aw-grid > .dragging { opacity: .5; pointer-events: none; }
.wand-card .chip.wand-name { background: #f2eefc; color: #6c4cd1; }
.wand-card .chip.playing { background: #e9fbf6; color: #14806b; }
.wand-card .chips .wbtn { margin-left: auto; }
.wand-card .chips .min-btn ~ .wbtn { margin-left: 0; }
.wand-card .min-name { display: none; font: 800 13px 'Nunito', system-ui, sans-serif; color: #231f2e; }
.wand-card.min .min-name { display: inline; }
.wand-card.min .chip, .wand-card.min .chips .wbtn:not(.min-btn),
.wand-card.min .display-status { display: none; }
.wand-card.min .chips { min-height: 0; }
.wand-card wand-sim { display: block; width: 100%; --wand-bg: transparent; --wand-shadow: none; }


${SPLAT_CONTROLLER_STYLE}
`;

export function createWandsPanel({ mount, room }) {
  const bar = mount;
  bar.insertAdjacentHTML("beforeend",
    `<button type="button" class="wbtn go" data-el="open">View Multiple Device Simulation</button>`);

  const dialog = document.createElement("dialog");
  dialog.className = "all-wands";
  dialog.setAttribute("aria-label", "All wands in this game");
  dialog.innerHTML = `<div class="aw-head">
      <h2 data-el="title"></h2>
      <button type="button" class="wbtn" data-el="add">+ Add a wand</button>
      <button type="button" class="wbtn" data-el="add-display">+ Add a display</button>
      <button type="button" class="wbtn" data-el="add-controller" title="Mock-up of a dedicated Splat companion wand">+ Add a Splat controller</button>
      <button type="button" class="wbtn sq" data-el="close" aria-label="Close">${icon("close", 18)}</button>
    </div>
    <div class="aw-grid" data-el="grid"></div>`;
  mount.appendChild(dialog);

  const $ = (root, el) => root.querySelector(`[data-el="${el}"]`);
  const grid = $(dialog, "grid");

  /** The room's own wand card; its <wand-sim> moves in while the dialog is open. */
  const mine = document.createElement("div");
  mine.className = "wand-card";
  mine.innerHTML = `<div class="chips"><span class="chip device-name wand-name">Wand 1</span></div>`;
  addMinimize(mine, mine.firstElementChild, "Wand 1");
  grid.appendChild(mine);

  /** [{ mac, card, el, link, lobbyGame, pad, toys }] in order; el null = a slot not yet started. */
  let others = [];
  let caps = null;
  let gameSplats = 1;

  $(dialog, "add").addEventListener("click", () => add());
  $(dialog, "add-display").addEventListener("click", () => room.panel("displays")?.add());
  // Mock-up only (js/panels/splatController.js): not counted, not on the bus.
  $(dialog, "add-controller").addEventListener("click", () => {
    grid.appendChild(createSplatController({ onRemove: (card) => card.remove() }).card);
  });
  $(bar, "open").addEventListener("click", () => open());
  $(dialog, "close").addEventListener("click", () => dialog.close());

  // Drag a card by its name bar to move it elsewhere in the grid. The card
  // goes before or after the card under the pointer, by which half of it
  // the pointer is over. Only the dragged card moves.
  grid.addEventListener("pointerdown", (e) => {
    const bar = e.target.closest(".device-name");
    const card = bar && [...grid.children].find((c) => c.contains(bar));
    if (!card || e.button !== 0) return;
    e.preventDefault();
    bar.setPointerCapture(e.pointerId);
    card.classList.add("dragging");
    const root = grid.getRootNode();
    const move = (ev) => {
      const under = root.elementFromPoint(ev.clientX, ev.clientY);
      const hit = under && [...grid.children].find((c) => c !== card && c.contains(under));
      if (!hit) return;
      const r = hit.getBoundingClientRect();
      if (ev.clientX > r.left + r.width / 2) hit.after(card);
      else hit.before(card);
    };
    const end = () => {
      card.classList.remove("dragging");
      bar.removeEventListener("pointermove", move);
      bar.removeEventListener("pointerup", end);
      bar.removeEventListener("pointercancel", end);
    };
    bar.addEventListener("pointermove", move);
    bar.addEventListener("pointerup", end);
    bar.addEventListener("pointercancel", end);
  });
  // Opening and closing the dialog each restart the game, so a lobby only
  // ever counts the wands that are on screen.
  dialog.addEventListener("close", () => {
    padSize.disconnect();
    room.placeWand(null);
    room.panel("displays")?.placeIn(null);
    room.panel("splats")?.placeIn?.(null);
    for (const o of others) o.el?.stop();
    room.lobbyGame?.retap();
    room.wand?.restart();
  });

  // Icon displays and Splats in the dialog match the wand's square pad.
  function sizeDisplays() {
    const pad = room.wand?.shadowRoot?.querySelector(".pad");
    if (!pad) return;
    const box = pad.getBoundingClientRect();
    grid.style.setProperty("--wand-pad", `${box.width}px`);
    // Displays and Splats line up with the top of the wand's pad.
    grid.style.setProperty("--wand-pad-top", `${box.top - room.wand.getBoundingClientRect().top}px`);
  }
  const padSize = new ResizeObserver(sizeDisplays);

  function open() {
    room.placeWand(mine);
    setMinimized(mine, mine.classList.contains("min"));
    room.panel("splats")?.placeIn?.(mine);
    room.panel("displays")?.placeIn(grid);
    if (dialog.open) return;
    // The wands the game is set for start with the dialog.
    for (const o of others) if (!o.el) goLive(o);
    dialog.showModal();
    sizeDisplays();
    if (room.wand) padSize.observe(room.wand);
    room.restart();
  }

  function draw() {
    const n = others.length;
    const full = n + 1 >= maxWands();
    $(dialog, "add").hidden = full;
    const displays = room.panel("displays");
    const k = displays ? displays.displays.length : 0;
    $(dialog, "add-display").hidden = !displays || displays.full;
    const shown = k === 0 ? "" : k === 1 ? "1 display" : `${k} displays`;
    $(dialog, "title").textContent = `${n + 1} wand${n ? "s" : ""}${shown ? ` and ${shown}` : ""} in this game`;
  }

  /** MAX_WANDS, or more when the game's settings ask for more wands. */
  function maxWands() {
    return Math.max(MAX_WANDS, room.gameWands);
  }

  function freeMac() {
    for (let i = 0; ; i++) {
      const mac = otherMac(i);
      if (!others.some((o) => o.mac === mac)) return mac;
    }
  }

  /**
   * Another wand. `live`: start it now ("+ Add a wand", or opening the
   * dialog); otherwise it is a slot that starts when the dialog opens, so a
   * game loading with the dialog closed boots no extra Pyodide.
   */
  function add(live = true) {
    if (others.length + 1 >= maxWands()) return;
    const o = { mac: freeMac(), card: document.createElement("div"), el: null };
    o.card.className = "wand-card";
    others.push(o);
    grid.appendChild(o.card);
    if (live) goLive(o);
    draw();
  }

  function remove(o) {
    stopLive(o);
    o.card.remove();
    others = others.filter((x) => x !== o);
    draw();
  }

  /** Draw a started wand's card (o.el set); slots are drawn by goLive. */
  function drawCard(o) {
    o.card.textContent = "";
    const chips = document.createElement("div");
    chips.className = "chips";
    // Every wand card is named, as Wand 1 is; "Playing" once it runs.
    const name = `Wand ${others.indexOf(o) + 2}`;
    chips.innerHTML = `<span class="chip device-name wand-name">${name}</span>`
      + (o.el ? `<span class="chip playing">Playing</span>` : "");
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "wbtn small sq";
    rm.setAttribute("aria-label", "Take this wand away");
    rm.innerHTML = icon("close", 15);
    rm.addEventListener("click", () => remove(o));
    chips.appendChild(rm);
    o.card.appendChild(chips);
    addMinimize(o.card, chips, name);
    o.card.appendChild(o.el);
    setMinimized(o.card, o.card.classList.contains("min"));
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
    o.el = w;
    o.splatCards = [];
    o.toys = [];
    w.addEventListener("sim-ready", () => {
      if (o.el !== w) return;
      const py = w.pyodide;
      o.link = attachWand(py, { bus: room.bus, clock: room.clock, mac: o.mac, tx: (s, d, h) => room._tx(s, d, h) });
      py.pyimport("runtime").set_game_splats(gameSplats);
      o.lobbyGame = createLobbyGameHost({ bus: room.bus, clock: room.clock, py, wandMac: o.mac });
      let queued = false;
      o.lobbyGame.onChange(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          drawToys(o);
        });
      });
    });
    w.addEventListener("sim-loaded", (e) => {
      if (o.el !== w || !o.lobbyGame) return;
      o.lobbyGame.setGame(slug(), e.detail?.capabilities || caps);
      drawToys(o);
    });
    loadInto(w);
    drawCard(o);
  }

  function drawToys(o) {
    // A redraw queued before the wand was taken away.
    if (!o.el) return;
    const splats = (o.lobbyGame?.caps?.lobby_game && o.lobbyGame.wandSplats) || [];
    const key = splats.map((s) => s.mac).join("+");
    if (key !== o.toysKey) {
      o.toysKey = key;
      for (const c of o.splatCards) c.remove();
      o.toys = splats.map((s, i) => createSplatToy(s, {
        label: `Splat ${i + 1}`,
        onButton: (down) => o.lobbyGame.wandSplatButton(i, down),
      }));
      // Each Splat is a card of its own, right after its wand's card.
      let at = o.card;
      o.splatCards = o.toys.map((t) => {
        const card = splatCard(splatDev(t.el));
        at.after(card);
        at = card;
        return card;
      });
    }
    for (const t of o.toys) t.refresh();
  }

  function stopLive(o) {
    if (!o.el) return;
    o.link?.detach();
    o.lobbyGame?.dispose();
    o.el.remove();
    for (const c of o.splatCards || []) c.remove();
    o.splatCards = [];
    o.el = o.link = o.lobbyGame = null;
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

  draw();
  return {
    setFor(n) {
      clear();
      for (let i = 1; i < n; i++) add(false);
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
    // Started wands pick n up on their next load (goLive, pushSource);
    // slots not yet started have no card to redraw.
    setGameSplats(n) {
      gameSplats = n;
    },
    restart() {
      for (const o of others) o.el?.restart();
    },
    stop() {
      for (const o of others) o.el?.stop();
    },
    clear,
    redraw: draw,
  };
}
