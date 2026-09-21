import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
// BroadcastBox/, two levels up from tools/devtests/.
const BB = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
/**
 * Walk a two-device reply through ChatBroadcast's pipeline, host-side.
 *
 * editor.js and app.js import CodeMirror from a CDN and touch the DOM, so
 * they cannot run here; this covers the parts that can -- block extraction,
 * per-role validation, icon resolution, and the file list a send builds --
 * plus pushPayload's ordering against a fake REPL.
 */
// Dynamic imports throughout: the module paths are built from this file's
// own location, and a static import cannot take an expression.
const { extractCodeBlocks, stripDeviceMarkers, ROLES } = await import(
    BB + '/ChatBroadcast/js/chat.js');
const { validateGameCode, signatureFor } = await import(
    BB + '/ChatBroadcast/js/upload.js');

globalThis.localStorage = {
    _d: {}, getItem(k) { return this._d[k] || null; }, setItem(k, v) { this._d[k] = v; },
};
const lib = await import(
    BB + '/ChatBroadcast/js/ledicons/iconLibrary.js');
const { pushPayload } = await import(
    BB + '/ChatBroadcast/js/device/boxFirmwareInstaller.js');

const fails = [];
const check = (label, ok, detail = '') => {
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}${detail ? ' -- ' + detail : ''}`);
    if (!ok) fails.push(label);
};

// ── A reply the model would produce for the goalrace demo ──
const REPLY = `Here is Team Goal Race. Two files, one per device.

[DEVICE: wand]
\`\`\`python
from game_tags import exit_tags_excluding
_EXIT_TAGS = exit_tags_excluding("goalrace")
COMMANDS = {"teamgreen", "teamblue", "goal"} | _EXIT_TAGS
def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    enow.broadcast({"type": "goal", "team": "green"})
\`\`\`

And the display half:

[DEVICE: icon]
\`\`\`python
import icon_store
from display_tags import exit_tags_excluding
_EXIT_TAGS = exit_tags_excluding("goalrace")
COMMANDS = _EXIT_TAGS
TEAM_ICON = {"green": "tree", "blue": "whale"}
def play(nfc, panel, enow):
    icon_store.read_icon("ready", into=panel.src)
\`\`\`

[NFC_CARDS: "teamgreen", "teamblue", "goal"]
[GAME_NAME: Team Goal Race]`;

const blocks = extractCodeBlocks(REPLY);
check('both device blocks extracted', blocks.length === 2, `${blocks.length} blocks`);
check('roles are wand then icon',
    blocks.map(b => b.role).join(',') === 'wand,icon', blocks.map(b => b.role).join(','));
check('device markers are stripped from the displayed text',
    !stripDeviceMarkers(REPLY).includes('[DEVICE:'));

const wand = blocks[0].code, icon = blocks[1].code;
check('wand file validates as wand', validateGameCode(wand, 'wand')[0] === true);
check('icon file validates as icon', validateGameCode(icon, 'icon')[0] === true);
check('wand file is REJECTED as an icon file', validateGameCode(wand, 'icon')[0] === false,
    validateGameCode(wand, 'icon')[1]);
check('icon file is REJECTED as a wand file', validateGameCode(icon, 'wand')[0] === false);
check('every role has a documented signature',
    ROLES.every(r => typeof signatureFor(r) === 'string'));

// ── Icons the display file needs ──
const names = lib.iconNamesIn(icon);
check('icons resolved from the display file',
    JSON.stringify(names) === JSON.stringify(['ready', 'tree', 'whale']), names.join(','));
check('none of them are missing', lib.missingIconsIn(icon).length === 0);
check('a game naming a nonexistent icon is caught',
    lib.missingIconsIn('icon_store.read_icon("dragon")').join(',') === 'dragon');

// ── The file list a send builds (mirrors app.js confirmSend) ──
const slug = 'goalrace';
const extraFiles = [{ path: `/flash/games/${slug}_icon.py`, content: icon }];
for (const n of names) {
    extraFiles.push({ path: `/flash/games/${slug}_icons/${n}.py`, content: lib.iconFileText(n) });
}

// ── pushPayload against a fake REPL ──
const written = [];
const repl = {
    async enterRepl() { written.push('enterRepl'); },
    async enterRawRepl() { written.push('enterRawRepl'); },
    async exitRawRepl() { written.push('exitRawRepl'); },
    async softReset() { written.push('softReset'); },
    async ensureDirectory(p) { written.push(`mkdir ${p}`); },
    async uploadFile(p) { written.push(`put ${p}`); },
};
const adapter = { async readUntil() { return { found: true }; } };
const progress = [];
const res = await pushPayload(repl, adapter, wand, (p) => progress.push(p), {
    destPath: `/flash/games/${slug}.py`,
    destLabel: `${slug}.py`,
    tags: ['getcode:goalrace', 'goalrace', 'teamgreen', 'teamblue', 'goal'],
    extraFiles,
});
check('push reported ok', res.ok === true, JSON.stringify(res));

const puts = written.filter(w => w.startsWith('put ')).map(w => w.slice(4));
check('wand file pushed', puts.includes('/flash/games/goalrace.py'));
check('tags sidecar pushed', puts.includes('/flash/games/goalrace.tags.json'));
check('display file pushed', puts.includes('/flash/games/goalrace_icon.py'));
for (const n of names) {
    check(`icon ${n} pushed`, puts.includes(`/flash/games/goalrace_icons/${n}.py`));
}
check('icons directory created before its files',
    written.indexOf('mkdir /flash/games/goalrace_icons') <
    written.indexOf('put /flash/games/goalrace_icons/ready.py'));
check('ONE raw-REPL session for the whole game',
    written.filter(w => w === 'enterRawRepl').length === 1);
check('ONE soft reset for the whole game',
    written.filter(w => w === 'softReset').length === 1);
check('the reset comes last',
    written[written.length - 1] === 'softReset', written[written.length - 1]);
check('progress counted every file',
    progress[progress.length - 1].total === 1 + extraFiles.length,
    JSON.stringify(progress[progress.length - 1]));

// ── The system prompt names every current icon (closes phase 6's §5.1) ──
// app.js itself cannot be imported here (it and its own imports touch the
// DOM and a CodeMirror CDN), so getSystemPrompt() is checked the same way
// this file already checks the file list a send builds: read the source
// and confirm the wiring, rather than duplicate its string-building logic
// into a second copy that would drift from the real one.
const appSrc = readFileSync(BB + '/ChatBroadcast/js/app.js', 'utf8');
const startIdx = appSrc.indexOf('getSystemPrompt()');
const endIdx = appSrc.indexOf('\n    }\n', startIdx);
const promptMethod = startIdx >= 0 && endIdx >= 0 ? appSrc.slice(startIdx, endIdx) : '';
check('getSystemPrompt() exists', promptMethod.length > 0);
check('it builds the icon list from listIcons(), not a hardcoded copy',
    /listIcons\(\)\.join/.test(promptMethod));
check('the icon list is returned as part of the prompt, not just built',
    /return[\s\S]*icons/.test(promptMethod));
check('listIcons() currently returns at least one real name to inject',
    lib.listIcons().length > 0 && lib.listIcons().every(n => typeof n === 'string' && n.length > 0),
    lib.listIcons().join(','));

// ── A single-device reply, the way every reply looked before markers ──
const legacy = 'Sure.\n```python\ndef play(nfc, leds, buz, accel, i2c, enow, batt=None):\n    pass\n```';
const lb = extractCodeBlocks(legacy);
check('an unmarked reply is still wand code',
    lb.length === 1 && lb[0].role === 'wand', JSON.stringify(lb.map(b => b.role)));

console.log();
if (fails.length) {
    console.log(`FAILED: ${fails.length}`);
    for (const f of fails) console.log('  -', f);
    process.exit(1);
}
console.log('ChatBroadcast two-device flow OK');
