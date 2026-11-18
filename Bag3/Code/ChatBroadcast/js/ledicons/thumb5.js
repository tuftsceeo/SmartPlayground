/**
 * 5x5 LED thumbnail for a game card's [GAME_ICON:] start signature.
 */
import { SHAPES5, LED_COLORS } from "./shapes5.js";

/** LED duty -> a screen color: brightest channel scaled to full. */
function screenRgb(duty) {
    const peak = Math.max(...duty) || 1;
    return duty.map((c) => Math.round((c * 255) / peak));
}

/**
 * A pale background tinted with the game's LED color, for its saved-game card.
 * @param {{color: string}|null} gameIcon
 * @returns {string} a CSS color
 */
export function gameTint(gameIcon) {
    const duty = LED_COLORS[gameIcon?.color];
    if (!duty) return "#f7f7fb";
    const mix = screenRgb(duty).map((c) => Math.round(255 - (255 - c) * 0.1));
    return `rgb(${mix.join(",")})`;
}

/**
 * @param {{shape: string, color: string}|null} gameIcon  start signature
 * @returns {string} HTML for a 5x5 grid; every cell unlit when the shape or
 *   color is missing or unknown
 */
export function gameIconThumb(gameIcon) {
    const lit = SHAPES5[gameIcon?.shape];
    const duty = LED_COLORS[gameIcon?.color];
    const on = new Set(lit && duty ? lit : []);
    const color = duty ? `rgb(${screenRgb(duty).join(",")})` : "";
    let cells = "";
    for (let i = 0; i < 25; i++) {
        cells += on.has(i) ? `<i style="background:${color}"></i>` : "<i></i>";
    }
    return `<span class="thumb5" role="img" aria-label="Game icon">${cells}</span>`;
}
