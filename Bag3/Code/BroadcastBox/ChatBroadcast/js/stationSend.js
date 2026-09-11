/**
 * stationSend.js -- write a game's station half to an Icon Display Station
 * over USB: the role file to /games, then each icon the file names.
 *
 * The Box path (js/upload.js) is unchanged and unrelated; a two-device game
 * is sent to two devices, over two connections.
 */

/** The panel's geometry. An icon of any other size is rejected, not scaled. */
const ICON_W = 16;
const ICON_H = 16;

/**
 * A module name for one role of a game, matching lib/game_store.py.
 *
 * @param {string} slug game slug, no underscore
 * @param {string} role role name, or falsy for a single-role game
 * @returns {string} "<slug>" or "<slug>_<role>"
 */
export function moduleName(slug, role) {
    return role ? `${slug}_${role}` : slug;
}

/**
 * Flatten an icon's [r,g,b] triples into the 768 bytes the station stores.
 *
 * @param {{name: string, w: number, h: number, px: number[][]}} icon
 * @returns {Uint8Array}
 */
export function iconBytes(icon) {
    if (icon.w !== ICON_W || icon.h !== ICON_H) {
        throw new Error(`icon ${icon.name}: ${icon.w}x${icon.h}, the panel is ${ICON_W}x${ICON_H}`);
    }
    const out = new Uint8Array(ICON_W * ICON_H * 3);
    for (let i = 0; i < icon.px.length; i++) {
        const p = icon.px[i];
        if (!Array.isArray(p) || p.length !== 3) {
            throw new Error(`icon ${icon.name}: pixel ${i} is not [r, g, b]`);
        }
        out[i * 3] = clampChannel(p[0]);
        out[i * 3 + 1] = clampChannel(p[1]);
        out[i * 3 + 2] = clampChannel(p[2]);
    }
    return out;
}

function clampChannel(v) {
    const n = Math.round(Number(v));
    if (!Number.isFinite(n)) throw new Error(`bad colour value ${v}`);
    return n < 0 ? 0 : n > 255 ? 255 : n;
}

/**
 * Send one role file and its icons to a connected station.
 *
 * Icons go first: the role file raises on the station if it names an icon
 * that is not there, and writing the file restarts the station, so anything
 * sent after it would land on a device that may already be playing.
 *
 * @param {object}   link        a station DeviceLink, already connected
 * @param {object}   opts
 * @param {string}   opts.slug   the game's slug
 * @param {string}   opts.role   this device's role in the game
 * @param {string}   opts.code   the role file's source
 * @param {object[]} [opts.icons] icons from the reply, as extractIcons returns
 * @param {(p: {current: number, total: number, file: string, status: string}) => void} [onProgress]
 * @returns {Promise<{module: string, path: string, icons: string[]}>}
 */
export async function sendToStation(link, { slug, role, code, icons = [] }, onProgress) {
    const module = moduleName(slug, role);
    const path = `/games/${module}.py`;
    const total = icons.length + 1;
    let done = 0;

    for (const icon of icons) {
        onProgress?.({ current: done + 1, total, file: `${icon.name}.py`, status: "uploading" });
        await link.saveIcon(icon.name, iconBytes(icon), { overwrite: true });
        done += 1;
        onProgress?.({ current: done, total, file: `${icon.name}.py`, status: "uploaded" });
    }

    onProgress?.({ current: total, total, file: `${module}.py`, status: "uploading" });
    await link.uploadFile(path, code);
    onProgress?.({ current: total, total, file: `${module}.py`, status: "uploaded" });

    return { module, path, icons: icons.map((i) => i.name) };
}
