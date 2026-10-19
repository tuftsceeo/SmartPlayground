/**
 * Splat panel for <sim-room>: the Splats paired to the simulated wand.
 *
 * One tile per Splat: a dome in the Splat's current color and a caption for
 * what it last did (a color, an animal sound, a note, "ready" for the
 * pairing glow, "out of reach" when its link is off). Pressing and holding
 * the tile is a press on the Splat's button (pointer or Space/Enter). Below,
 * a -/+ count sets how many Splats the wand holds (0-2), which restarts the
 * game. Sounds and notes also play a short tone once the page has had a
 * press.
 *
 * Advanced mode (:host([advanced]) on the room) adds an "In reach" checkbox
 * under each tile; off = the Splat drops out, as when its BLE link is lost.
 *
 * A peer wand's Splats are drawn by the peer strip (js/panels/peers.js) with
 * the same tile, from createSplatTile().
 *
 *   createSplatPanel({ mount, onLocalCount(n) })   n: Splats on this wand
 *   setGroups([{ owner, label, rgb, splats, onButton(i, down), onReady(i, up) }])
 *       only the first group (the wand's own) is drawn
 *   setLocalCount(n)
 *   refresh()   redraw after a model change
 *
 *   createSplatTile(splat, { onButton(down), onReady(up), mini, label })
 *     .el, .refresh()
 */

import { noteFreq } from "../splats.js";
import { icon } from "../icons.js";

export const LOCAL_MAX = 2;

export const SPLAT_STYLE = `
.splat-panel { display: flex; flex-direction: column; gap: 12px; }
.splat-row { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 12px; }
.splat-slot { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.splat-tile { display: flex; flex-direction: column; align-items: center; gap: 10px;
  width: 108px; padding: 14px 8px 12px; box-sizing: border-box; border-radius: 16px;
  border: 1.5px solid #e8e6f0; background: #fff; color: inherit; font: inherit; cursor: pointer;
  touch-action: none; user-select: none; -webkit-user-select: none; transition: all .15s ease; }
.splat-tile:hover { border-color: #ef4d92; }
.splat-tile:focus-visible { outline: none; border-color: #ef4d92; box-shadow: 0 0 0 3px rgba(233,78,155,.14); }
.splat-tile.down { border-color: #ef4d92; background: #fff0f6; }
.splat-tile.lost { background: #f7f7fb; }
.splat-tile .dome { display: flex; align-items: center; justify-content: center; width: 68px; height: 68px;
  border-radius: 50%; background: #3a3345; color: #8b859a; transition: transform .15s ease, background 80ms; }
.splat-tile.down .dome { transform: scale(0.88); }
.splat-tile .what { font: 400 18px/1 'Patrick Hand', 'Nunito', system-ui, sans-serif; color: #3a3345;
  text-align: center; overflow-wrap: anywhere; }
.splat-tile.lost .what { color: #5b5468; }
.splat-tile.mini { flex-direction: row; width: auto; min-height: 44px; gap: 8px; padding: 4px 12px 4px 6px;
  border-radius: 22px; }
.splat-tile.mini .dome { width: 30px; height: 30px; }
.splat-tile.mini .what { font-size: 16px; }
.splat-reach { display: none; align-items: center; gap: 6px; min-height: 28px;
  font: 700 11px 'Nunito', system-ui, sans-serif; color: #5b5468; cursor: pointer; }
.splat-reach input { accent-color: #ef4d92; width: 16px; height: 16px; margin: 0; }
:host([advanced]) .splat-reach { display: flex; }
.splat-count { margin-left: auto; display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.splat-count .stepper { display: flex; align-items: center; gap: 6px; }
.splat-count .stepper button { width: 44px; height: 44px; border-radius: 50%; border: 1.5px solid #e8e6f0;
  background: #fff; font: 800 18px 'Nunito', system-ui, sans-serif; color: #5b5468; cursor: pointer;
  transition: all .15s ease; }
.splat-count .stepper button:hover:not(:disabled) { border-color: #6c4cd1; color: #6c4cd1; }
.splat-count .stepper button:disabled { opacity: .7; cursor: not-allowed; }
.splat-count .n { min-width: 24px; text-align: center; font: 900 18px 'Nunito', system-ui, sans-serif; color: #231f2e; }
.splat-count .hint, .splat-panel .empty { font: 400 16px 'Patrick Hand', 'Nunito', system-ui, sans-serif; color: #5b5468; }
.splat-panel .empty { align-self: center; padding: 6px 0; }
`;

const css = (rgb) => `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
const glow = (rgb) => `0 0 0 6px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.25)`;

let audio = null;

function unlockAudio() {
  if (audio) return;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (AC) audio = new AC();
}

function tone(freq, ms) {
  if (!audio) return;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.frequency.value = freq;
  gain.gain.value = 0.08;
  osc.connect(gain).connect(audio.destination);
  osc.start();
  osc.stop(audio.currentTime + ms / 1000);
}

function noteText(name) {
  if (name === "note_c_high") return "high C";
  if (name === "playnote") return "a note";
  const m = /^note_([a-g])$/.exec(name);
  return m ? `note ${m[1].toUpperCase()}` : name;
}

/** What the caption says, and the glyph on the dome (or null). */
function describe(s) {
  if (!s.ready) return { what: "out of reach", glyph: "unplug" };
  if (s.note) return { what: noteText(s.note), glyph: "music" };
  if (s.sound) return { what: s.sound.replace(/_/g, " "), glyph: "volume-2" };
  if (s.color && s.color !== "turnoff") return { what: s.color.replace(/^turn/, ""), glyph: null };
  if (s.rgb.some(Boolean)) return { what: "ready", glyph: null };
  return { what: "off", glyph: null };
}

export function createSplatTile(splat, { onButton, onReady = null, mini = false, label = "Splat" }) {
  const slot = document.createElement("div");
  slot.className = "splat-slot";
  slot.innerHTML = `<button type="button" class="splat-tile${mini ? " mini" : ""}">
      <span class="dome"></span><span class="what"></span></button>`;
  const btn = slot.querySelector("button");
  btn.dataset.splat = splat.mac;
  const dome = btn.querySelector(".dome");
  const what = btn.querySelector(".what");
  let shownGlyph = null;
  let heard = splat.sounds;

  const down = () => {
    unlockAudio();
    if (!splat.pressed) onButton(true);
  };
  const up = () => { if (splat.pressed) onButton(false); };
  btn.addEventListener("pointerdown", (e) => {
    btn.setPointerCapture?.(e.pointerId);
    down();
  });
  btn.addEventListener("pointerup", up);
  btn.addEventListener("pointercancel", up);
  btn.addEventListener("keydown", (e) => {
    if ((e.key === " " || e.key === "Enter") && !e.repeat) {
      e.preventDefault();
      down();
    }
  });
  btn.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") up(); });
  btn.addEventListener("blur", up);

  let reach = null;
  if (onReady && !mini) {
    const lab = document.createElement("label");
    lab.className = "splat-reach";
    lab.innerHTML = `<input type="checkbox"> In reach`;
    reach = lab.querySelector("input");
    reach.addEventListener("change", () => onReady(reach.checked));
    slot.appendChild(lab);
  }

  function refresh() {
    const d = describe(splat);
    const lit = splat.ready && splat.rgb.some(Boolean);
    dome.style.background = !splat.ready ? "#e8e6f0" : lit ? css(splat.rgb) : "";
    dome.style.boxShadow = lit && !mini ? glow(splat.rgb) : "";
    // A dark dome (asleep, or a deep blue/purple) needs a light glyph.
    const bright = lit && splat.rgb[0] * 0.3 + splat.rgb[1] * 0.59 + splat.rgb[2] * 0.11 > 140;
    dome.style.color = !splat.ready ? "#8b859a" : bright ? "#3a3345" : "#ffffff";
    if (d.glyph !== shownGlyph) {
      shownGlyph = d.glyph;
      dome.innerHTML = d.glyph && !mini ? icon(d.glyph, 22) : "";
    }
    what.textContent = d.what;
    btn.setAttribute("aria-label", `${label}: ${d.what}. Press and hold to squish it.`);
    btn.classList.toggle("down", splat.pressed);
    btn.classList.toggle("lost", !splat.ready);
    if (reach) reach.checked = splat.ready;
    if (heard !== splat.sounds) {
      heard = splat.sounds;
      if (splat.note) tone(noteFreq(splat.note) || 262, 250);
      else if (splat.sound) tone(330, 120);
    }
  }

  refresh();
  return { el: slot, refresh };
}

export function createSplatPanel({ mount, onLocalCount = null }) {
  const root = document.createElement("div");
  root.className = "splat-panel";
  root.dataset.el = "splat-panel";
  root.innerHTML = `<div class="splat-row">
      <div class="splat-tiles" style="display: contents"></div>
      <div class="splat-count">
        <div class="stepper">
          <button type="button" data-step="-1" aria-label="One fewer Splat">−</button>
          <span class="n" data-el="local-count">1</span>
          <button type="button" data-step="1" aria-label="One more Splat">+</button>
        </div>
        <span class="hint">changing this starts the game over</span>
      </div>
    </div>`;
  mount.appendChild(root);
  const tilesEl = root.querySelector(".splat-tiles");
  const countEl = root.querySelector('[data-el="local-count"]');
  const lessBtn = root.querySelector('[data-step="-1"]');
  const moreBtn = root.querySelector('[data-step="1"]');
  let count = 1;
  let tiles = [];

  function showCount() {
    countEl.textContent = String(count);
    lessBtn.disabled = count <= 0;
    moreBtn.disabled = count >= LOCAL_MAX;
  }
  for (const b of [lessBtn, moreBtn]) {
    b.addEventListener("click", () => {
      const n = Math.max(0, Math.min(LOCAL_MAX, count + Number(b.dataset.step)));
      if (n === count) return;
      count = n;
      showCount();
      onLocalCount?.(n);
    });
  }

  function render(group) {
    tilesEl.textContent = "";
    tiles = [];
    if (!group || !group.splats.length) {
      tilesEl.innerHTML = `<div class="empty">no Splats on this wand yet</div>`;
      return;
    }
    group.splats.forEach((s, i) => {
      const t = createSplatTile(s, {
        label: `Splat ${i + 1} on this wand`,
        onButton: (down) => group.onButton(i, down),
        onReady: (up) => group.onReady(i, up),
      });
      tiles.push(t);
      tilesEl.appendChild(t.el);
    });
  }

  function refresh() {
    for (const t of tiles) t.refresh();
  }

  showCount();
  return {
    root,
    setLocalCount(n) {
      count = n;
      showCount();
    },
    setGroups(groups) {
      render(groups[0]);
    },
    refresh,
  };
}
