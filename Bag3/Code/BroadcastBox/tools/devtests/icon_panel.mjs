import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
// BroadcastBox/, two levels up from tools/devtests/.
const BB = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
/**
 * Check the icon panel picks the right icon out of a display game, and that
 * the Maker bridge's conversions round-trip.
 *
 * renderPreview needs a canvas; a minimal recording stub stands in, because
 * what is under test here is WHICH icon gets drawn, not the bloom compositing
 * (that is the Maker's, unchanged).
 */
const CB = BB + '/ChatBroadcast';

globalThis.localStorage = {
    _d: {}, getItem(k) { return this._d[k] || null; }, setItem(k, v) { this._d[k] = v; },
};

const drawn = [];
function fakeCtx() {
    return {
        fillStyle: '', globalCompositeOperation: '', globalAlpha: 1, filter: '',
        fillRect() {}, beginPath() {}, arc() {}, fill() {},
        drawImage() {}, clearRect() {}, putImageData() {},
    };
}
function fakeCanvas() {
    return { width: 0, height: 0, getContext: fakeCtx };
}
globalThis.document = {
    createElement(tag) {
        if (tag === 'canvas') return fakeCanvas();
        return {
            tagName: tag, className: '', innerHTML: '', style: {}, dataset: {},
            children: [], appendChild(c) { this.children.push(c); },
            querySelector() { return null; }, addEventListener() {},
        };
    },
};

const lib = await import(`${CB}/js/ledicons/iconLibrary.js`);
const panel = await import(`${CB}/js/ledicons/iconPanel.js`);
const bridge = await import(`${CB}/iconmaker/js/libraryBridge.js`);

const fails = [];
const check = (l, ok, d = '') => {
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${l}${d ? ' -- ' + d : ''}`);
    if (!ok) fails.push(l);
};

const GAME = `
import icon_store
IDLE_ICON = "ready"
TEAM_ICON = {"green": "tree", "blue": "whale"}
def play(nfc, panel, enow):
    icon_store.read_icon(IDLE_ICON, into=panel.src)
`;

check('starting icon comes from IDLE_ICON', panel.startingIcon(GAME) === 'ready',
    String(panel.startingIcon(GAME)));
check('a game naming no icon has no starting icon',
    panel.startingIcon('def play(nfc, panel, enow): pass') === null);

const c = fakeCanvas();
check('a known icon draws', panel.drawIcon(c, 'whale', 0.3).ok === true);
const bad = panel.drawIcon(c, 'dragon', 0.3);
check('an unknown icon reports rather than drawing the last one',
    bad.ok === false && bad.error.includes('dragon'), bad.error);

// ── Maker bridge conversions ──
const flat = lib.getIcon('whale');
const triples = bridge.flatToPixels(flat);
check('flat -> 256 triples', triples.length === 256 && triples[0].length === 3);
check('round-trips back to the same bytes',
    JSON.stringify(bridge.pixelsToFlat(triples)) === JSON.stringify(flat));

// ── Saving through the bridge makes an icon referable by name ──
const edited = flat.slice();
edited[0] = 200; edited[1] = 10; edited[2] = 10;
lib.saveIcon('whale', edited);
check('an edited default shadows the shipped one', lib.getIcon('whale')[0] === 200);
check('it is marked as a teacher edit', lib.isCustom('whale') === true);
lib.revertIcon('whale');
check('reverting brings the shipped icon back', lib.getIcon('whale')[0] === flat[0]);

lib.saveIcon('dragon', edited);
check('a brand new icon joins the library', lib.listIcons().includes('dragon'));
check('and is then resolvable by a game',
    lib.missingIconsIn('icon_store.read_icon("dragon")').length === 0);
check('its .py text parses as ICON data',
    lib.iconFileText('dragon').includes('SIZE = (16, 16)') &&
    (lib.iconFileText('dragon').match(/\(\d+, \d+, \d+\)/g) || []).length === 256);

console.log();
if (fails.length) { console.log(`FAILED: ${fails.length}`); process.exit(1); }
console.log('icon panel + Maker bridge OK');
