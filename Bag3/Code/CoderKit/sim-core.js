/**
 * The real simulator (Simulator/sim-room.js) as a kit `simulator` option,
 * fed the way app.js pushSimSource() does. `load` imports sim-room.js: the
 * runner imports it from ../Simulator (run-sim.js); artifacts import their
 * published copy (artifact-entry.js).
 */
import { iconNamesIn, getIcon } from '../ChatBroadcast/js/ledicons/iconLibrary.js';

function displayIcons(code) {
    const out = {};
    for (const name of iconNamesIn(code)) { const d = getIcon(name); if (d) out[name] = d; }
    return out;
}

export const makeSimRoomSimulator = (load) => function simRoomSimulator(el, kit) {
    const room = document.createElement('sim-room');
    room.style.display = 'block';
    room.style.width = '100%';
    room.style.height = '100%';
    el.textContent = '';
    el.appendChild(room);
    let ready = load().then(() => { room.autostart = true; });
    room.addEventListener('sim-error', (e) => kit.simError(`${e.detail?.phase || 'run'}: ${e.detail?.message}`));
    room.addEventListener('sim-log', (e) => kit.log(`wand: ${e.detail.text}`, 'device'));
    room.addEventListener('display-print', (e) => kit.log(`display: ${e.detail.text}`, 'device'));
    return {
        async update(code, example) {
            await ready;
            const wand = code.wand || '';
            if (!wand.trim()) return;
            const display = code.icon || null;
            room.hideOverlay?.();
            room.displayIcons = display ? displayIcons(display) : null;
            room.displaySource = display;
            room.profile = example?.simProfile || null;
            room.settings = null;
            room.source = wand;
        },
        destroy() { try { room.stop?.(); } catch (_) {} room.remove(); },
    };
};
