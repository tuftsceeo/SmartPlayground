/**
 * editor.js -- the icon editor overlay: pick an icon, paint it, take it away.
 *
 * Paints one pixel at a time on a 16x16 grid, beside the same simulated-panel
 * preview the station tab shows, so an edit is judged the way the panel will
 * show it rather than as flat swatches. Edits change the icons the game will
 * send; nothing reaches a device until the game is sent.
 */

import { renderIcon } from "./panel.js";
import { iconText, iconJson } from "./emit.js";
import { W, H, DEFAULT_INTENSITY } from "./constants.js";

/** A small palette that survives the panel's truncation at low intensity. */
const SWATCHES = [
    [0, 0, 0], [255, 255, 255], [255, 0, 0], [255, 120, 0],
    [255, 230, 0], [0, 255, 0], [0, 200, 160], [0, 120, 255],
    [140, 0, 255], [255, 0, 160], [120, 60, 0], [90, 90, 90],
];

const toHex = ([r, g, b]) =>
    "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");

function fromHex(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/**
 * Open the editor on a game's icons.
 *
 * @param {object}   opts
 * @param {object[]} opts.icons    the game's icons; edited in place
 * @param {string}   [opts.selected] which to open on
 * @param {() => void} [opts.onChange] called after every edit
 */
export function openIconEditor({ icons, selected, onChange }) {
    const overlay = document.getElementById("icon-editor-overlay");
    const body = document.getElementById("icon-editor-body");
    if (!overlay || !body) throw new Error("icon editor markup is missing from index.html");
    if (!icons.length) {
        body.innerHTML = '<p class="icon-editor-empty">This game ships no icons yet.</p>';
        overlay.classList.remove("hidden");
        return;
    }

    let icon = icons.find((i) => i.name === selected) || icons[0];
    let pen = [255, 255, 255];

    function draw() {
        body.innerHTML = "";
        body.appendChild(buildPicker());
        const work = document.createElement("div");
        work.className = "icon-editor-work";
        work.appendChild(buildGrid());
        work.appendChild(buildPreview());
        body.appendChild(work);
        body.appendChild(buildPalette());
        body.appendChild(buildActions());
    }

    function buildPicker() {
        const row = document.createElement("div");
        row.className = "icon-editor-picker";
        for (const i of icons) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "icon-editor-tab" + (i === icon ? " active" : "");
            btn.textContent = i.name;
            btn.addEventListener("click", () => { icon = i; draw(); });
            row.appendChild(btn);
        }
        return row;
    }

    function buildGrid() {
        const grid = document.createElement("div");
        grid.className = "icon-editor-grid";
        grid.style.gridTemplateColumns = `repeat(${W}, 1fr)`;
        let painting = false;
        const paint = (idx, cell) => {
            icon.px[idx] = [...pen];
            cell.style.background = toHex(pen);
            refreshPreview();
            onChange?.();
        };
        for (let idx = 0; idx < W * H; idx++) {
            const cell = document.createElement("div");
            cell.className = "icon-editor-cell";
            cell.style.background = toHex(icon.px[idx]);
            cell.addEventListener("pointerdown", (e) => {
                painting = true;
                e.target.releasePointerCapture?.(e.pointerId);
                paint(idx, cell);
            });
            cell.addEventListener("pointerenter", () => { if (painting) paint(idx, cell); });
            grid.appendChild(cell);
        }
        // Release anywhere: a drag that ends off the grid must not leave the
        // pen down, or the next hover would paint without a click.
        window.addEventListener("pointerup", () => { painting = false; });
        return grid;
    }

    let previewHost = null;
    function buildPreview() {
        previewHost = document.createElement("div");
        previewHost.className = "icon-editor-preview";
        refreshPreview();
        return previewHost;
    }

    function refreshPreview() {
        if (!previewHost) return;
        previewHost.innerHTML = "";
        previewHost.appendChild(renderIcon(icon, DEFAULT_INTENSITY));
    }

    function buildPalette() {
        const row = document.createElement("div");
        row.className = "icon-editor-palette";
        const mark = () => {
            row.querySelectorAll(".icon-editor-swatch").forEach((el) => {
                el.classList.toggle("active", el.dataset.hex === toHex(pen));
            });
        };
        for (const rgb of SWATCHES) {
            const sw = document.createElement("button");
            sw.type = "button";
            sw.className = "icon-editor-swatch";
            sw.dataset.hex = toHex(rgb);
            sw.style.background = toHex(rgb);
            sw.title = rgb.join(", ");
            sw.addEventListener("click", () => { pen = [...rgb]; mark(); });
            row.appendChild(sw);
        }
        const custom = document.createElement("input");
        custom.type = "color";
        custom.className = "icon-editor-custom";
        custom.title = "Any other colour";
        custom.value = toHex(pen);
        custom.addEventListener("input", () => { pen = fromHex(custom.value); mark(); });
        row.appendChild(custom);
        mark();
        return row;
    }

    function buildActions() {
        const row = document.createElement("div");
        row.className = "icon-editor-actions";
        row.appendChild(button("Clear", () => {
            icon.px = icon.px.map(() => [0, 0, 0]);
            onChange?.();
            draw();
        }));
        row.appendChild(button("Download .py", () =>
            download(`${icon.name}.py`, iconText(icon.px, icon.name))));
        row.appendChild(button("Download .json", () =>
            download(`${icon.name}.json`, iconJson(icon))));
        return row;
    }

    function button(label, fn) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "btn-secondary icon-editor-btn";
        b.textContent = label;
        b.addEventListener("click", fn);
        return b;
    }

    draw();
    overlay.classList.remove("hidden");
}

function download(filename, text) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
