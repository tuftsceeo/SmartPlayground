/**
 * emit.js -- turn a grid of pixels into the file the station stores.
 *
 * The device artefact is icons/<name>.py holding SIZE and ICON; this is the
 * same text iconText() produces in the station's own webapp
 * (Stations/Icon Display Station/webapp/js/pipeline/emit.js), kept here so
 * an icon edited in ChatBroadcast can be downloaded in the form the station
 * reads. icon_store.py is what parses it.
 */

import { W, H } from "./constants.js";

/**
 * @param {number[][]} pixels W*H [r, g, b] triples, row-major from top-left
 * @param {string} [nameComment] a first-line comment, usually the icon's name
 * @returns {string} the contents of icons/<name>.py
 */
export function iconText(pixels, nameComment) {
    const lines = [];
    if (nameComment) lines.push(`# ${nameComment}`);
    // Self-describing size, so a smaller glyph can be recognised and scaled
    // rather than rejected as the wrong length (icon_store.py reads this;
    // files without it are assumed panel-native).
    lines.push(`SIZE = (${W}, ${H})`);
    lines.push("ICON = (");
    for (let row = 0; row < H; row++) {
        const tuples = pixels
            .slice(row * W, (row + 1) * W)
            .map(([r, g, b]) => `(${r}, ${g}, ${b})`);
        lines.push(`    ${tuples.join(", ")},`);
    }
    lines.push(")");
    return lines.join("\n") + "\n";
}

/**
 * The JSON block form, as a reply ships an icon and as extractIcons() reads it.
 *
 * @param {{name: string, px: number[][]}} icon
 * @returns {string}
 */
export function iconJson(icon) {
    const rows = [];
    for (let row = 0; row < H; row++) {
        rows.push(
            "  " + icon.px.slice(row * W, (row + 1) * W).map((p) => `[${p.join(",")}]`).join(", ")
        );
    }
    return `{"w": ${W}, "h": ${H}, "px": [\n${rows.join(",\n")}\n]}\n`;
}
