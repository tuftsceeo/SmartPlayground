import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
// BroadcastBox/, two levels up from tools/devtests/.
const BB = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
/**
 * Walk a three-device reply through ChatBroadcast's pipeline, host-side.
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

[DEVICE: splat]
\`\`\`python
# A block for the retired Splat Companion role, as an older reply had.
def play(splat, leds, enow, batt=None):
    msg_type, data, mac = enow.poll()
    if msg_type in ("stop", "start_game"):
        return
    ev = splat.poll()
    if ev == "press":
        splat.play(["turngreen"])
        enow.broadcast({"type": "score", "hit": True})
\`\`\`

[NFC_CARDS: "teamgreen", "teamblue", "goal"]
[GAME_NAME: Team Goal Race]`;

const blocks = extractCodeBlocks(REPLY);
check('two device blocks extracted (the retired splat block is left out)',
    blocks.length === 2, `${blocks.length} blocks`);
check('roles are wand then icon',
    blocks.map(b => b.role).join(',') === 'wand,icon', blocks.map(b => b.role).join(','));
check('device markers are stripped from the displayed text',
    !stripDeviceMarkers(REPLY).includes('[DEVICE:'));

const wand = blocks[0].code, icon = blocks[1].code;
const splat = REPLY.split('```')[5].replace(/^python\n/, '');
check('the splat block did not land in the icon slot', !icon.includes('splat.poll'));
check('wand file validates as wand', validateGameCode(wand, 'wand')[0] === true);
check('icon file validates as icon', validateGameCode(icon, 'icon')[0] === true);
check('the retired splat role is refused',
    validateGameCode(splat, 'splat')[0] === false && /Unknown device role/.test(validateGameCode(splat, 'splat')[1]),
    validateGameCode(splat, 'splat')[1]);
check('wand file is REJECTED as an icon file', validateGameCode(wand, 'icon')[0] === false,
    validateGameCode(wand, 'icon')[1]);
check('icon file is REJECTED as a wand file', validateGameCode(icon, 'wand')[0] === false);
check('splat file is REJECTED as a wand file', validateGameCode(splat, 'wand')[0] === false);
check('display file size limit applies',
    validateGameCode(icon + '#'.repeat(33000), 'icon')[0] === false);
check('every role has a documented signature',
    ROLES.every(r => typeof signatureFor(r) === 'string'));

// ── Icons the display file needs ──
const names = lib.iconNamesIn(icon);
check('icons resolved from the display file',
    JSON.stringify(names) === JSON.stringify(['ready', 'tree', 'whale']), names.join(','));
check('none of them are missing', lib.missingIconsIn(icon).length === 0);
check('a game naming a nonexistent icon is caught',
    lib.missingIconsIn('icon_store.read_icon("dragon")').join(',') === 'dragon');

// ── The Splat Companion role is retired; the action-name checker stays ──
const { roleInfo, ROLES: ROLE_ROWS } = await import(BB + '/ChatBroadcast/js/roles.js');
const { unknownSplatActionsIn, listSplatActions } = await import(
    BB + '/ChatBroadcast/js/splat/splatActionCheck.js');
check('there is no splat role', roleInfo('splat') === undefined);
check('roles are wand then icon', ROLE_ROWS.map(r => r.key).join(',') === 'wand,icon');
check('wand and icon roles carry no name check',
    !roleInfo('wand').unknownNamesIn && !roleInfo('icon').unknownNamesIn);
const { RESERVED_SUFFIXES } = await import(BB + '/ChatBroadcast/js/gameName.js');
check('_splat stays a reserved suffix (devices skip _splat.py)',
    RESERVED_SUFFIXES.includes('_splat') && RESERVED_SUFFIXES.includes('_icon'), RESERVED_SUFFIXES.join(','));
check('the splat file uses only known action names',
    unknownSplatActionsIn(splat).length === 0, unknownSplatActionsIn(splat).join(','));
check('a misspelled color is caught',
    unknownSplatActionsIn('splat.color("turnpurpel")').join(',') === 'turnpurpel');
check('a name from the wrong category is caught',
    unknownSplatActionsIn('splat.sound("turnred")').join(',') === 'turnred');
check('play() accepts a mix of categories',
    unknownSplatActionsIn('splat.play(["cat", "note_c", "turnblue"])').length === 0);
check('an unknown name inside play() is caught',
    unknownSplatActionsIn("splat.play(['cat', 'lion'])").join(',') === 'lion');
check('a call on one unit is checked too',
    unknownSplatActionsIn('splat.unit(1).note("note_z")').join(',') === 'note_z');
check('a name held in a variable is not guessed at',
    unknownSplatActionsIn('c = COLORS[i]\nsplat.color(c)').length === 0);
const sa = listSplatActions();
check('the prompt list has all three categories',
    sa.colors.includes('turnred') && sa.notes.includes('note_c') && sa.sounds.includes('cat'));

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
check('no splat file pushed', !puts.some(p => p.includes('_splat')));
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

// ── A display-only game: the display file is the primary file ──
// (mirrors app.js confirmSend: destPath is <slug><designator>.py, and the
// icon leg rides as extra files)
const dWritten = [];
const dRepl = {
    async enterRepl() {}, async enterRawRepl() {}, async exitRawRepl() {},
    async softReset() { dWritten.push('softReset'); },
    async ensureDirectory(p) { dWritten.push(`mkdir ${p}`); },
    async uploadFile(p) { dWritten.push(`put ${p}`); },
};
const dExtra = names.map(n => ({ path: `/flash/games/scoreonly_icons/${n}.py`, content: lib.iconFileText(n) }));
const dRes = await pushPayload(dRepl, adapter, icon, () => {}, {
    destPath: '/flash/games/scoreonly_icon.py',
    destLabel: 'scoreonly_icon.py',
    tags: ['getcode:scoreonly', 'scoreonly'],
    extraFiles: dExtra,
});
check('display-only push reported ok', dRes.ok === true, JSON.stringify(dRes));
const dPuts = dWritten.filter(w => w.startsWith('put ')).map(w => w.slice(4));
check('display-only game writes <slug>_icon.py', dPuts.includes('/flash/games/scoreonly_icon.py'));
check('display-only game writes no wand file', !dPuts.includes('/flash/games/scoreonly.py'));
check('display-only game ships its icons', names.every(n => dPuts.includes(`/flash/games/scoreonly_icons/${n}.py`)));

// ── The system prompt names every current icon (closes phase 6's §5.1) ──
// app.js cannot be imported here (it and its imports touch the DOM and a
// CodeMirror CDN), so getSystemBlocks() is checked by reading its source;
// sessionText() in prompt/buildRequest.js is the part that writes the names.
const appSrc = readFileSync(BB + '/ChatBroadcast/js/app.js', 'utf8');
const startIdx = appSrc.indexOf('getSystemBlocks()');
const endIdx = appSrc.indexOf('\n    }\n', startIdx);
const blocksMethod = startIdx >= 0 && endIdx >= 0 ? appSrc.slice(startIdx, endIdx) : '';
check('getSystemBlocks() exists', blocksMethod.length > 0);
check('it passes listIcons() to buildSystemBlocks, not a hardcoded copy',
    /buildSystemBlocks\([\s\S]*icons:\s*listIcons\(\)/.test(blocksMethod));
const reqSrc = readFileSync(BB + '/ChatBroadcast/js/prompt/buildRequest.js', 'utf8');
const sIdx = reqSrc.indexOf('export function sessionText(');
const sEnd = reqSrc.indexOf('\n}\n', sIdx);
const sessionSrc = sIdx >= 0 && sEnd >= 0 ? reqSrc.slice(sIdx, sEnd) : '';
check('sessionText() exists', sessionSrc.length > 0);
check('sessionText() writes the icon list into the block',
    /icons\.join\(/.test(sessionSrc));
check('buildSystemBlocks() includes sessionText(icons, ...)',
    /sessionText\(icons,/.test(reqSrc));
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
console.log('ChatBroadcast three-device flow OK');
