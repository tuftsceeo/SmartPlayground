/**
 * The icon display simulator: what the 16x16 panel would actually show.
 *
 * The renderer is the Icon Maker's, reached through iconmaker/js/pipeline/
 * rather than reimplemented -- it models the device's truncating LUT and the
 * additive bloom of real LEDs, and a second implementation would drift from
 * it. This module only decides WHAT to draw: it reads the display game's
 * source for the icon it starts on and lets the teacher step through the
 * others it can reach.
 */
import { renderPreview } from '../../iconmaker/js/pipeline/preview.js';
import { getIcon, iconNamesIn, missingIconsIn, W, H } from './iconLibrary.js';

/** Library flat duty -> the 256 [r,g,b] triples renderPreview wants. */
function toTriples(flat) {
    const out = new Array(W * H);
    for (let i = 0; i < W * H; i++) {
        out[i] = [flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]];
    }
    return out;
}

const BLANK = new Array(W * H).fill(null).map(() => [0, 0, 0]);

/**
 * The icon a display game shows first.
 *
 * Games name their resting picture in a module constant -- IDLE_ICON or
 * ICON_READY by convention -- so that is preferred; otherwise the first icon
 * the file mentions at all. Returns null when the game names none.
 */
export function startingIcon(code) {
    if (!code) return null;
    const named = code.match(/^\s*(?:IDLE_ICON|ICON_READY|ICON_IDLE)\s*=\s*["']([a-z0-9_]+)["']/m);
    if (named && getIcon(named[1])) return named[1];
    const all = iconNamesIn(code);
    return all.length ? all[0] : null;
}

/**
 * Draw one named icon into a canvas at a given intensity.
 * An unknown name draws a dark panel and says so, rather than silently
 * showing the last icon.
 *
 * @returns {{ok: boolean, error?: string}}
 */
export function drawIcon(canvas, name, intensity) {
    const flat = name ? getIcon(name) : null;
    if (!flat) {
        renderPreview(BLANK, intensity, canvas);
        return { ok: false, error: name ? `No icon named "${name}".` : 'This game names no icon.' };
    }
    renderPreview(toTriples(flat), intensity, canvas);
    return { ok: true };
}

/**
 * Mount the simulator into a container.
 *
 * Shows the game's starting icon and a picker for every other icon it can
 * reach, so a teacher can see each state the display will take without
 * running the game. Icons the game names but the library does not have are
 * reported here, in the same place they would be refused at send time.
 *
 * @param {HTMLElement} mount
 * @returns {{update: (code: string) => void}}
 */
export function mountIconPanel(mount) {
    mount.innerHTML = `
      <canvas class="icon-sim-canvas" width="384" height="384"></canvas>
      <div class="icon-sim-controls">
        <select class="icon-sim-pick" aria-label="Icon to preview"></select>
        <label class="icon-sim-bright">
          <input type="range" min="0.02" max="0.50" step="0.01" value="0.30" />
          <span>30%</span>
        </label>
      </div>
      <p class="icon-sim-note"></p>
    `;
    const canvas = mount.querySelector('.icon-sim-canvas');
    const pick = mount.querySelector('.icon-sim-pick');
    const slider = mount.querySelector('.icon-sim-bright input');
    const pct = mount.querySelector('.icon-sim-bright span');
    const note = mount.querySelector('.icon-sim-note');

    let intensity = Number(slider.value);

    function paint() {
        const res = drawIcon(canvas, pick.value, intensity);
        if (!res.ok) note.textContent = res.error;
    }

    slider.addEventListener('input', () => {
        intensity = Number(slider.value);
        pct.textContent = `${Math.round(intensity * 100)}%`;
        paint();
    });
    pick.addEventListener('change', paint);

    function update(code) {
        const names = iconNamesIn(code);
        const missing = missingIconsIn(code);
        pick.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join('');
        const first = startingIcon(code);
        if (first) pick.value = first;
        pick.disabled = names.length < 2;
        note.textContent = missing.length
            ? `This game asks for icons that do not exist: ${missing.join(', ')}. It cannot be sent until they do.`
            : (names.length ? '' : 'This display game names no icon.');
        paint();
    }

    return { update };
}
