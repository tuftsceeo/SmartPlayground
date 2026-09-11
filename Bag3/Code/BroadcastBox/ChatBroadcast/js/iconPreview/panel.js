/**
 * panel.js -- the icon display's stand-in for the wand simulator.
 *
 * It does not run the station's role file; it shows the icons the game
 * ships, rendered the way the panel will show them, so the teacher can see
 * whether a 16x16 silhouette reads before sending anything to hardware.
 */

import { renderPreview } from "./preview.js";
import { DEFAULT_INTENSITY, MAX_INTENSITY, W, H } from "./constants.js";

/**
 * Draw one icon's pixels into a canvas.
 *
 * @param {{name: string, w: number, h: number, px: number[][]}} icon
 * @param {number} intensity 0 to MAX_INTENSITY
 * @param {HTMLCanvasElement} [canvas] reused if given
 * @returns {HTMLCanvasElement}
 */
export function renderIcon(icon, intensity, canvas) {
    if (icon.w !== W || icon.h !== H) {
        throw new Error(`icon ${icon.name} is ${icon.w}x${icon.h}, the panel is ${W}x${H}`);
    }
    return renderPreview(icon.px, Math.min(intensity, MAX_INTENSITY), canvas);
}

/**
 * Fill a container with a large preview of one icon and a strip to pick
 * between them. Replaces whatever the container held.
 *
 * @param {HTMLElement} host
 * @param {object[]} icons as extractIcons() returns them
 * @param {object} [opts]
 * @param {number} [opts.intensity] defaults to what the station boots at
 * @param {string} [opts.selected]  name of the icon to show large
 */
export function renderIconPanel(host, icons, { intensity = DEFAULT_INTENSITY, selected } = {}) {
    host.innerHTML = "";
    if (!icons.length) {
        const empty = document.createElement("div");
        empty.className = "icon-panel-empty";
        empty.textContent = "This game ships no icons yet.";
        host.appendChild(empty);
        return;
    }

    const shown = icons.find((i) => i.name === selected) || icons[0];

    const stage = document.createElement("div");
    stage.className = "icon-panel-stage";
    stage.appendChild(renderIcon(shown, intensity));
    host.appendChild(stage);

    const caption = document.createElement("div");
    caption.className = "icon-panel-name";
    caption.textContent = shown.name;
    host.appendChild(caption);

    if (icons.length > 1) {
        const strip = document.createElement("div");
        strip.className = "icon-panel-strip";
        for (const icon of icons) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "icon-panel-thumb" + (icon === shown ? " active" : "");
            btn.title = icon.name;
            const thumb = renderIcon(icon, intensity);
            thumb.style.width = "48px";
            thumb.style.height = "48px";
            btn.appendChild(thumb);
            btn.addEventListener("click", () => {
                renderIconPanel(host, icons, { intensity, selected: icon.name });
            });
            strip.appendChild(btn);
        }
        host.appendChild(strip);
    }
}
