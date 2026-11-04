/**
 * Bridge between the Icon Maker and ChatBroadcast's named-icon library.
 *
 * The Maker's own exports write a .py to the teacher's downloads folder,
 * which is right when they are authoring for a station over USB. When it is
 * opened from ChatBroadcast the icon has to land somewhere a generated
 * display game can refer to BY NAME -- and, since icons belong to a game,
 * somewhere that game alone can see. Which store that is depends on how the
 * Maker was opened; see the backend note below.
 */
import {
    listIcons, getIcon, isValidIconName,
    saveStarterIcon, revertStarterIcon, isStarterIcon,
    W, H,
} from '../../js/ledicons/iconLibrary.js';

/**
 * Where icons are read and written.
 *
 * Standalone, that is this window's own icon library. Embedded, it is NOT:
 * ChatBroadcast keeps a game's edited icons in memory so they can be saved
 * with that game, and an iframe gets its own module instance with its own
 * empty copy. So the host injects its store here (through
 * `iconMaker.library.setBackend`) and every read and write in the Maker goes
 * to the open game instead of to this window's shared localStorage.
 *
 * One indirection, used by attachLibraryBar, saveToLibrary and the API alike,
 * so there is no second path that could still write to the wrong place.
 */
/**
 * Standalone, "the library" is the shared starter palette in localStorage --
 * this tool is how it gets curated. Embedded, the host replaces every one of
 * these with its own per-game store, so a game's edits can never reach it.
 */
const LOCAL_BACKEND = {
    list: listIcons,
    get: getIcon,
    save: saveStarterIcon,
    revert: revertStarterIcon,
    isCustom: isStarterIcon,
};

let backend = LOCAL_BACKEND;
const backendListeners = new Set();

export function setLibraryBackend(next) {
    backend = next ? { ...LOCAL_BACKEND, ...next } : LOCAL_BACKEND;
    backendListeners.forEach((cb) => { try { cb(); } catch (_) {} });
    return backend;
}

export function onLibraryBackendChange(cb) {
    backendListeners.add(cb);
    return () => backendListeners.delete(cb);
}

export function library() {
    return backend;
}

/** doc.pixels (256 [r,g,b]) -> the flat 768-value array the library stores. */
export function pixelsToFlat(pixels) {
    const flat = new Array(W * H * 3);
    for (let i = 0; i < W * H; i++) {
        const p = pixels[i] || [0, 0, 0];
        flat[i * 3] = p[0];
        flat[i * 3 + 1] = p[1];
        flat[i * 3 + 2] = p[2];
    }
    return flat;
}

/** The library's flat 768 values -> doc.pixels' 256 [r,g,b] triples. */
export function flatToPixels(flat) {
    const out = new Array(W * H);
    for (let i = 0; i < W * H; i++) {
        out[i] = [flat[i * 3], flat[i * 3 + 1], flat[i * 3 + 2]];
    }
    return out;
}

/**
 * Save the icon under `name` into the game library.
 *
 * Raises on a bad name rather than saving under a mangled one: the name is
 * how a generated game refers to the picture, so a silent rename here is a
 * game that draws nothing later.
 */
export function saveToLibrary(name, pixels) {
    const clean = (name || '').trim();
    if (!isValidIconName(clean)) {
        throw new Error(
            'not a usable icon name: "' + clean + '" -- letters, digits and '
            + '_ or - only, up to 24 characters');
    }
    backend.save(clean, pixelsToFlat(pixels));
    return clean;
}


/**
 * Add a library row to the Maker's chrome.
 *
 * This row BROWSES the library; it does not write to it. Saving is the top
 * bar's Save alone, which goes through saveToLibrary() and therefore through
 * whichever backend is installed. Two buttons that saved to the same place,
 * one of them quietly worse, is the kind of choice a teacher can only get
 * wrong -- and with a swappable backend it is also two chances to write to
 * the wrong store.
 *
 * @param {HTMLElement} mount  where the row goes
 * @param {object} hooks
 * @param {(name: string, pixels: Array) => void} hooks.loadDoc  replace the open icon
 * @param {(msg: string, isError?: boolean) => void} hooks.say   user feedback
 */
export function attachLibraryBar(mount, { loadDoc, say }) {
    const el = document.createElement('div');
    el.className = 'library-bar';
    el.innerHTML = `
      <span class="library-bar-label">Game library</span>
      <select id="libPick" title="Icons this game can refer to by name"></select>
      <button type="button" id="libOpen" title="Open this saved icon for editing">Open</button>
      <button type="button" id="libRevert" title="Drop your edit and restore the shipped icon">Revert</button>
      <span id="libMsg"></span>
    `;
    mount.appendChild(el);

    const pick = el.querySelector('#libPick');
    const msg = el.querySelector('#libMsg');

    const note = (text, isError) => {
        if (say) say(text, isError);
        msg.textContent = text;
        msg.className = isError ? 'err' : '';
    };

    function refreshList(selected) {
        const names = backend.list();
        pick.innerHTML = names
            .map((n) => `<option value="${n}">${n}${backend.isCustom(n) ? ' *' : ''}</option>`)
            .join('');
        if (selected && names.includes(selected)) pick.value = selected;
        el.querySelector('#libRevert').disabled = !backend.isCustom(pick.value);
    }

    pick.addEventListener('change', () => {
        el.querySelector('#libRevert').disabled = !backend.isCustom(pick.value);
    });

    el.querySelector('#libOpen').addEventListener('click', () => {
        const name = pick.value;
        const flat = backend.get(name);
        if (!flat) { note(`No icon named "${name}".`, true); return; }
        loadDoc(name, flatToPixels(flat));
        note(`Opened ${name}.`);
    });

    el.querySelector('#libRevert').addEventListener('click', () => {
        const name = pick.value;
        if (!backend.isCustom(name)) { note(`"${name}" has no edit to drop.`, true); return; }
        backend.revert(name);
        refreshList(name);
        note(`Reverted "${name}".`);
    });

    refreshList();
    return { refreshList };
}
