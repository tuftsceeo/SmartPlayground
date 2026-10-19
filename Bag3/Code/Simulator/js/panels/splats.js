/**
 * Splat panel for <sim-room>: every Splat in the room.
 *
 * The wand's own Splats come first; in a party game the virtual peers'
 * Splats follow, each with an owner badge in that peer's identity color.
 * A tile shows the Splat's color, its last sound or note as text, a
 * press button (held while the pointer is down) and a link checkbox (off =
 * the Splat drops, splat_lost). Sounds and notes also play a short tone once
 * the page has had a click.
 *
 * The panel draws models (js/splats.js); the room wires them up:
 *   setGroups([{ owner, label, rgb, splats, onButton(i, down), onReady(i, up) }])
 *   refresh()   redraw after a model change
 */

import { noteFreq } from "../splats.js";

export const SPLAT_STYLE = `
.splat-panel { display: flex; flex-direction: column; gap: 10px; }
.splat-group { display: flex; flex-direction: column; gap: 6px; }
.splat-owner { font: 700 0.78rem 'Nunito', system-ui, sans-serif; color: #8b859a;
  display: flex; align-items: center; gap: 6px; }
.splat-owner .badge { width: 12px; height: 12px; border-radius: 50%; border: 1px solid #0002; }
.splat-tiles { display: flex; flex-wrap: wrap; gap: 8px; }
.splat-tile { display: flex; flex-direction: column; align-items: center; gap: 4px;
  width: 92px; padding: 6px; border-radius: 12px; background: #f7f7fb; }
.splat-tile .disc { width: 48px; height: 48px; border-radius: 50%; border: 2px solid #0003;
  background: #222; transition: background 80ms; }
.splat-tile.down .disc { transform: scale(0.92); }
.splat-tile.lost { opacity: 0.45; }
.splat-tile .what { font: 12px/1.2 ui-monospace, monospace; min-height: 2.4em; text-align: center;
  word-break: break-word; }
.splat-tile button { font: 700 0.75rem 'Nunito', system-ui, sans-serif; padding: 4px 10px;
  border-radius: 10px; border: 1.5px solid #6c4cd1; background: #6c4cd1; color: #fff; cursor: pointer;
  touch-action: none; }
.splat-tile label { font-size: 0.72rem; color: #8b859a; }
.splat-panel .empty { font-size: 0.8rem; color: #8b859a; }
`;

const css = (rgb) => `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;

export function createSplatPanel({ mount }) {
  const root = document.createElement("div");
  root.className = "splat-panel";
  root.dataset.el = "splat-panel";
  mount.appendChild(root);
  let groups = [];
  let audio = null;
  const heard = new WeakMap(); // splat -> last "sound|note" played

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

  function unlockAudio() {
    if (audio) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) audio = new AC();
  }

  function sounds(splat) {
    const key = `${splat.sound}|${splat.note}`;
    if (heard.get(splat) === key) return;
    heard.set(splat, key);
    if (splat.note) tone(noteFreq(splat.note) || 262, 250);
    else if (splat.sound) tone(330, 120);
  }

  function render() {
    root.textContent = "";
    if (!groups.length) {
      root.innerHTML = `<div class="empty">no Splats</div>`;
      return;
    }
    for (const g of groups) {
      const box = document.createElement("div");
      box.className = "splat-group";
      box.dataset.owner = g.owner;
      const head = document.createElement("div");
      head.className = "splat-owner";
      head.innerHTML = `<span class="badge"></span><span></span>`;
      head.querySelector(".badge").style.background = css(g.rgb);
      head.lastChild.textContent = g.label;
      box.appendChild(head);
      const tiles = document.createElement("div");
      tiles.className = "splat-tiles";
      g.splats.forEach((s, i) => {
        const tile = document.createElement("div");
        tile.className = "splat-tile";
        tile.dataset.splat = s.mac;
        tile.innerHTML = `<div class="disc"></div><div class="what"></div>
          <button type="button">press</button>
          <label><input type="checkbox"> link</label>`;
        const btn = tile.querySelector("button");
        btn.addEventListener("pointerdown", (e) => {
          unlockAudio();
          btn.setPointerCapture?.(e.pointerId);
          g.onButton(i, true);
        });
        const up = () => { if (s.pressed) g.onButton(i, false); };
        btn.addEventListener("pointerup", up);
        btn.addEventListener("pointercancel", up);
        tile.querySelector("input").addEventListener("change", (e) => g.onReady(i, e.target.checked));
        tiles.appendChild(tile);
      });
      box.appendChild(tiles);
      root.appendChild(box);
    }
    refresh();
  }

  function refresh() {
    for (const g of groups) {
      g.splats.forEach((s) => {
        const tile = root.querySelector(`[data-splat="${s.mac}"]`);
        if (!tile) return;
        tile.querySelector(".disc").style.background = css(s.rgb);
        const what = [s.color, s.sound, s.note].filter(Boolean).join(" · ");
        tile.querySelector(".what").textContent = what || "off";
        tile.querySelector("input").checked = s.ready;
        tile.classList.toggle("lost", !s.ready);
        tile.classList.toggle("down", s.pressed);
        sounds(s);
      });
    }
  }

  return {
    root,
    setGroups(next) {
      groups = next;
      render();
    },
    refresh,
  };
}
