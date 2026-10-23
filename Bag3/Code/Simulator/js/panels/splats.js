/**
 * Splats for <sim-room>: the Splats paired to the simulated wand.
 *
 * The Splats are part of the wand's tangible interface, so they are drawn
 * as small toys in the wand's pad, below the drawn wand (wand-sim's "pad"
 * slot), with no labels: the toy's blue case and splatter window, lit LEDs
 * in the middle and out in the arms. A click on one is a press on
 * its button (held at least MIN_PRESS_MS, so a quick click registers with a
 * game that polls). There are as many as the game pairs (0-2); none = the
 * row is not there. Sounds and notes play a short tone and pulse the toy.
 *
 * Advanced mode only: a card with a -/+ count for the wand's Splats (which
 * restarts the game) and an "in reach" box per Splat (off = the Splat drops
 * out, as when its BLE link is lost).
 *
 *   createSplatPanel({ mount, overlay, onLocalCount(n) })
 *       mount: the advanced card's box; overlay: the element in the pad
 *   setGroups([{ owner, label, rgb, splats, onButton(i, down), onReady(i, up) }])
 *       only the first group (the wand's own) is drawn
 *   setLocalCount(n)
 *   refresh()   redraw after a model change
 *
 *   createSplatToy(splat, { onButton(down), label, size })   .el, .refresh()
 *       also used for another wand's Splats (js/panels/wands.js)
 */

import { noteFreq } from "../splats.js";

export const LOCAL_MAX = 2;
const MIN_PRESS_MS = 250;

export const SPLAT_STYLE = `
.pad-splats { display: flex; gap: 12px; pointer-events: auto; }
.splat-toy { display: block; padding: 0; border: 0; background: none; cursor: pointer;
  border-radius: 12px; touch-action: none; -webkit-tap-highlight-color: transparent;
  transition: transform .15s ease, opacity .15s ease; }
.splat-toy svg { display: block; width: 100%; height: 100%; overflow: visible; }
.splat-toy:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(233,78,155,.35); }
.splat-toy.down { transform: scale(0.88); }
.splat-toy.lost { opacity: .4; }
.splat-toy.chirp { animation: splat-chirp .3s ease; }
@keyframes splat-chirp { 40% { transform: scale(1.12); } }
.splat-toy .case { fill: #4491e8; }
.splat-toy .blob { fill: #d4d7de; }
.splat-toy.down .case { fill: #2f76c8; }

.splat-card { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; }
.splat-card .reach { display: flex; align-items: center; gap: 6px; min-height: 28px;
  font: 700 12px 'Nunito', system-ui, sans-serif; color: #5b5468; cursor: pointer; }
.splat-card .reach input { accent-color: #ef4d92; width: 16px; height: 16px; margin: 0; }
.splat-card .stepper { margin-left: auto; display: flex; align-items: center; gap: 6px; }
.splat-card .stepper button { width: 36px; height: 36px; border-radius: 50%; border: 1.5px solid #e8e6f0;
  background: #fff; font: 800 16px 'Nunito', system-ui, sans-serif; color: #5b5468; cursor: pointer;
  transition: all .15s ease; }
.splat-card .stepper button:hover:not(:disabled) { border-color: #6c4cd1; color: #6c4cd1; }
.splat-card .stepper button:disabled { opacity: .7; cursor: not-allowed; }
.splat-card .n { min-width: 20px; text-align: center; font: 900 16px 'Nunito', system-ui, sans-serif; color: #231f2e; }
.splat-card .hint { flex-basis: 100%; font: 700 11px 'Nunito', system-ui, sans-serif; color: #5b5468; }
`;

/** The Splat's outline (a 256 x 254.7 drawing of the toy): the case with
 * its lanyard hole, the splatter window, and the window's LEDs as
 * [x, y, inner], inner ones in the middle and outer ones out in the arms. */
export const CASE = "M238.5,0H17.5C7.8,0,0,7.8,0,17.5v219.7c0,9.7,7.8,17.5,17.5,17.5h221c9.7,0,17.5-7.8,17.5-17.5V17.5c0-9.7-7.8-17.5-17.5-17.5ZM45.6,67.4c-12.4,0-22.5-10.1-22.5-22.5s10.1-22.5,22.5-22.5,22.5,10.1,22.5,22.5-10.1,22.5-22.5,22.5Z";
export const BLOB = "M232.2,111.7c-9.1-12.7-26.6-1.9-39.2-5.2-4-1.2-7.3-4.5-9.8-7.8-14.6-19.5,32.1-29.9,38.2-48.4,1.2-3.5-.1-7.6-2.6-10.4-7.5-8.5-20-5.4-28.2,2.4-2.9,2.7-5.5,5.8-8.5,8.4-6.6,5.8-14.5,10.3-21.3,14.3-7,4.6-13.5,7.7-21.8,4.1-11.2-5.3-14.5-18.9-18.4-29.8-1.5-4.4-3.1-9.2-6.3-12.7-5.5-6.3-15.2-8-22.6-5.2-9,3.1-12.2,12-10.2,20.8,2,13.1,16.8,25,12.4,37.8-8.8,14.7-31.9-10.1-40.2,5.7-2.5,5-1.9,11.3,3.2,14.4,4.7,2.9,10,5.4,14.1,9.5,15.1,14.7-25.5,19.9-34.8,36-1.3,3.4-.4,7.5,1,10.7,2.6,5.7,7.3,7,13.1,6.2,7.8-1.2,16.8-6.1,24.3-9.7,5.7-2.3,11.4-6.9,17.6-4.5,12.1,5.9,6.6,23.5,6.7,35,.1,4.7-.8,9.4-1.4,14.1-.7,7.1.2,12.5,7.3,13.7,5.4.6,12.7-.6,17.5-3.7,10.1-7.9,6.6-22.9,9.6-33.9,4.1-15.1,12.5-15,22.7-2.8,6,7,11.8,17,15.8,25,1.6,3.3,3.2,6.9,5.6,9.9,15.7,18.5,47.4-13.8,25.9-29.5-4.4-3.7-10.1-6.9-13.4-11.5-2.8-4-3.9-10.1-2.7-14.7,5.3-21.2,59-12.3,46.3-38.2v-.2Z";
const LEDS = [
  [125, 118, 1], [148, 104, 1], [105, 108, 1], [128, 142, 1],
  [107, 35, 0], [206, 49, 0], [212, 113, 0], [190, 196, 0], [118, 205, 0], [48, 158, 0], [46, 89, 0],
];

/** The window's diffuser: an unlit LED is the same gray, so an off Splat
 * reads as one solid shape and a white LED reads as lit against it. */
const WINDOW_GRAY = "#d4d7de";

const rgbCss = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const mix = (c, k) => c.map((v) => Math.round(v + (255 - v) * k));

let audio = null;
let toyCount = 0;

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

/** What the Splat is doing, for its accessible name. */
function describe(s) {
  if (!s.ready) return "out of reach";
  if (s.note) return s.note.replace(/_/g, " ");
  if (s.sound) return s.sound.replace(/_/g, " ");
  if (s.color && s.color !== "turnoff") return s.color.replace(/^turn/, "");
  if (s.rgb.some(Boolean)) return "ready";
  return "off";
}

export function createSplatToy(splat, { onButton, label = "Splat", size = 56 }) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "splat-toy";
  btn.dataset.splat = splat.mac;
  btn.style.width = `${size}px`;
  btn.style.height = `${size}px`;
  const clip = `splat-clip-${++toyCount}`;
  btn.innerHTML = `<svg viewBox="0 0 256 254.7" aria-hidden="true">
      <path class="case" fill-rule="evenodd" d="${CASE}"/>
      <clipPath id="${clip}"><path d="${BLOB}"/></clipPath>
      <path class="blob" d="${BLOB}"/>
      <g clip-path="url(#${clip})">
        <g class="glow">${LEDS.map(([x, y, inner]) => `<circle cx="${x}" cy="${y}" r="${inner ? 26 : 20}"/>`).join("")}</g>
        <g class="leds">${LEDS.map(([x, y, inner]) => `<circle cx="${x}" cy="${y}" r="${inner ? 11 : 10}"/>`).join("")}</g>
      </g>
    </svg>`;
  const glows = [...btn.querySelectorAll(".glow circle")];
  const leds = [...btn.querySelectorAll(".leds circle")];
  let heard = splat.sounds;
  let releaseAt = 0;
  let held = false;
  let timer = null;

  // A press holds at least MIN_PRESS_MS, then lets go once the pointer is up.
  function down() {
    unlockAudio();
    held = true;
    releaseAt = performance.now() + MIN_PRESS_MS;
    clearTimeout(timer);
    if (!splat.pressed) onButton(true);
  }
  function up() {
    if (!held) return;
    held = false;
    clearTimeout(timer);
    timer = setTimeout(() => { if (!held && splat.pressed) onButton(false); },
      Math.max(0, releaseAt - performance.now()));
  }
  // Stop here: the pad around the toy would take the event as a tilt or a
  // press on the wand's own button.
  for (const type of ["pointerdown", "pointermove", "pointerup", "click"]) {
    btn.addEventListener(type, (e) => e.stopPropagation());
  }
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
  btn.addEventListener("animationend", () => btn.classList.remove("chirp"));

  function refresh() {
    // An LED value is a brightness; lift it so a dim pairing glow still
    // reads as its color on screen.
    const ring = (rgb) => {
      if (!splat.ready || !rgb.some(Boolean)) return null;
      const peak = Math.max(...rgb, 1);
      return rgb.map((v) => Math.round((v / peak) * 255));
    };
    const inner = ring(splat.inner);
    const outer = ring(splat.outer);
    leds.forEach((el, i) => {
      const c = LEDS[i][2] ? inner : outer;
      el.style.fill = c ? rgbCss(LEDS[i][2] ? mix(c, 0.35) : c) : WINDOW_GRAY;
      glows[i].style.fill = c ? rgbCss(c, LEDS[i][2] ? 0.5 : 0.35) : "transparent";
    });
    btn.setAttribute("aria-label", `${label}, ${describe(splat)}`);
    btn.classList.toggle("down", splat.pressed);
    btn.classList.toggle("lost", !splat.ready);
    if (heard !== splat.sounds) {
      heard = splat.sounds;
      btn.classList.remove("chirp");
      void btn.offsetWidth;
      btn.classList.add("chirp");
      if (splat.note) tone(noteFreq(splat.note) || 262, 250);
      else if (splat.sound) tone(330, 120);
    }
  }

  refresh();
  return { el: btn, refresh };
}

export function createSplatPanel({ mount, overlay, onLocalCount = null }) {
  const root = document.createElement("div");
  root.className = "splat-card";
  root.dataset.el = "splat-panel";
  root.innerHTML = `<div class="reaches" style="display: contents"></div>
    <div class="stepper">
      <button type="button" data-step="-1" aria-label="One fewer Splat">−</button>
      <span class="n" data-el="local-count">1</span>
      <button type="button" data-step="1" aria-label="One more Splat">+</button>
    </div>
    <span class="hint">Changing the count starts the game over.</span>`;
  mount.appendChild(root);
  const reachesEl = root.querySelector(".reaches");
  const countEl = root.querySelector('[data-el="local-count"]');
  const lessBtn = root.querySelector('[data-step="-1"]');
  const moreBtn = root.querySelector('[data-step="1"]');
  let count = 1;
  let toys = [];
  let reaches = [];
  let splats = [];

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
    overlay.textContent = "";
    reachesEl.textContent = "";
    splats = group ? group.splats : [];
    toys = splats.map((s, i) => createSplatToy(s, {
      label: `Splat ${i + 1}`,
      onButton: (down) => group.onButton(i, down),
    }));
    for (const t of toys) overlay.appendChild(t.el);
    reaches = splats.map((s, i) => {
      const lab = document.createElement("label");
      lab.className = "reach";
      lab.innerHTML = `<input type="checkbox"> Splat ${i + 1} in reach`;
      const box = lab.querySelector("input");
      box.addEventListener("change", () => group.onReady(i, box.checked));
      reachesEl.appendChild(lab);
      return box;
    });
    refresh();
  }

  function refresh() {
    for (const t of toys) t.refresh();
    reaches.forEach((box, i) => { box.checked = splats[i].ready; });
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
