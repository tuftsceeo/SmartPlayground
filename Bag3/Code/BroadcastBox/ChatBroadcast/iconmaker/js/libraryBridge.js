/**
 * Bridge between the Icon Maker and ChatBroadcast's named-icon library.
 *
 * The Maker's own exports write a .py to the teacher's downloads folder,
 * which is right when they are authoring for a station over USB. When it is
 * opened from ChatBroadcast the icon has to land somewhere a generated
 * display game can refer to BY NAME, and that is the shared library in
 * ../js/ledicons/iconLibrary.js.
 *
 * Nothing else in the Maker knows this module exists: main.js calls
 * attachLibraryBar() and the rest of the app is untouched.
 */
import {
    listIcons, getIcon, saveIcon, revertIcon, isCustom, isValidIconName,
    W, H,
} from '../../js/ledicons/iconLibrary.js';

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
 * Add a library row to the Maker's chrome.
 *
 * @param {HTMLElement} mount  where the row goes
 * @param {object} hooks
 * @param {() => {name: string, pixels: Array}} hooks.readDoc   current icon
 * @param {(name: string, pixels: Array) => void} hooks.loadDoc  replace it
 * @param {(msg: string, isError?: boolean) => void} hooks.say   user feedback
 */
export function attachLibraryBar(mount, { readDoc, loadDoc, say }) {
    const el = document.createElement('div');
    el.className = 'library-bar';
    el.innerHTML = `
      <select id="libPick" title="Icons this game can refer to by name"></select>
      <button type="button" id="libOpen">Open</button>
      <button type="button" id="libSave">Save to game library</button>
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
        const names = listIcons();
        pick.innerHTML = names
            .map((n) => `<option value="${n}">${n}${isCustom(n) ? ' *' : ''}</option>`)
            .join('');
        if (selected && names.includes(selected)) pick.value = selected;
        el.querySelector('#libRevert').disabled = !isCustom(pick.value);
    }

    pick.addEventListener('change', () => {
        el.querySelector('#libRevert').disabled = !isCustom(pick.value);
    });

    el.querySelector('#libOpen').addEventListener('click', () => {
        const name = pick.value;
        const flat = getIcon(name);
        if (!flat) { note(`No icon named "${name}".`, true); return; }
        loadDoc(name, flatToPixels(flat));
        note(`Opened ${name}.`);
    });

    el.querySelector('#libSave').addEventListener('click', () => {
        const { name, pixels } = readDoc();
        if (!pixels) { note('Nothing to save yet — import or open an icon first.', true); return; }
        if (!isValidIconName(name)) {
            note(`"${name}" is not a valid icon name: lowercase letters, digits and _, not starting with a digit.`, true);
            return;
        }
        // Let a real failure surface rather than swallowing it: a teacher who
        // thinks an icon saved and finds a blank panel later has a much worse
        // problem than one told now.
        saveIcon(name, pixelsToFlat(pixels));
        refreshList(name);
        note(`Saved "${name}" — a display game can now ask for it by name.`);
    });

    el.querySelector('#libRevert').addEventListener('click', () => {
        const name = pick.value;
        if (!isCustom(name)) { note(`"${name}" has no edit to drop.`, true); return; }
        revertIcon(name);
        refreshList(name);
        note(`Reverted "${name}".`);
    });

    refreshList();
    return { refreshList };
}
