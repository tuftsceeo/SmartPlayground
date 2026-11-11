/**
 * 5x5 LED thumbnail for a saved game's [GAME_ICON:] start signature.
 */
import { SHAPES5, LED_COLORS } from "./shapes5.js";

/** LED duty -> a screen color: brightest channel scaled to full. */
function screenRgb(duty) {
    const peak = Math.max(...duty) || 1;
    return duty.map((c) => Math.round((c * 255) / peak));
}

/**
 * @param {{shape: string, color: string}|null} gameIcon  stored start signature
 * @returns {string} HTML for a 5x5 grid, or "" when the shape or color is unknown
 */
export function gameIconThumb(gameIcon) {
    const lit = SHAPES5[gameIcon?.shape];
    const duty = LED_COLORS[gameIcon?.color];
    if (!lit || !duty) return "";
    const on = new Set(lit);
    const color = `rgb(${screenRgb(duty).join(",")})`;
    let cells = "";
    for (let i = 0; i < 25; i++) {
        cells += on.has(i) ? `<i style="background:${color}"></i>` : "<i></i>";
    }
    return `<span class="thumb5" role="img" aria-label="Game icon">${cells}</span>`;
}
