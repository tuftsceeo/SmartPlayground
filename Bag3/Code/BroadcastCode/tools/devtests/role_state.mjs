import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { register } from 'node:module';

// BroadcastBox/, two levels up from tools/devtests/.
const BB = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SCRATCH = dirname(fileURLToPath(import.meta.url));

/**
 * Drive ChatBroadcast/js/editor.js's per-role editor state through a full
 * authoring cycle, host-side.
 *
 * editor.js imports CodeMirror from four esm.sh URLs; the loader hook in
 * stubs/cm_loader.mjs redirects those to stubs/codemirror_stub.mjs so the
 * module can be imported under plain Node with no network access. This
 * test never calls initEditor(), so editorView stays null throughout and
 * getCode()/setCode() operate purely on the roleState object under test --
 * the same fallback path a real page takes before the editor mounts.
 *
 * app.js's syncRoleRail()/selectRole()/confirmSend() and the per-game
 * dirty/name/tags state they read are NOT covered here: app.js pulls in
 * auth.js, router.js and other DOM-touching modules that a loader hook
 * cannot paper over the way a handful of CodeMirror exports can. This
 * fills the editor.js gap chatbroadcast_flow.mjs's own docstring already
 * flags as untestable at that layer.
 */
register('file://' + resolve(SCRATCH, 'stubs', 'cm_loader.mjs'));

globalThis.localStorage = {
    _d: {}, getItem(k) { return this._d[k] || null; }, setItem(k, v) { this._d[k] = v; },
};
// updateVersionUI() is the only editor.js function that touches the DOM
// once initEditor() is never called; its own guard returns early when any
// of these three ids is missing, so a document that never has them is
// sufficient -- this test cares about roleState, not the version label UI.
globalThis.document = { getElementById: () => null, createElement: () => ({}) };

const { ROLES } = await import(BB + '/ChatBroadcast/js/chat.js');
const editor = await import(BB + '/ChatBroadcast/js/editor.js');

const fails = [];
const check = (label, ok, detail = '') => {
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}${detail ? ' -- ' + detail : ''}`);
    if (!ok) fails.push(label);
};

check('editor.js imported with no network access', true);
check('ROLES is wand then icon', ROLES.join(',') === 'wand,icon', ROLES.join(','));
check('editorView never mounts -- getCode/setCode fall back to roleState',
    editor.getActiveRole() === 'wand');

// ── Two blocks land, the way confirmSend's role split would place them ──
editor.setCode('# wand code v1\n', 'wand');
editor.setCode('# icon code v1\n', 'icon');
check('wand code set independently of icon',
    editor.getCode('wand') === '# wand code v1\n');
check('icon code set independently of wand',
    editor.getCode('icon') === '# icon code v1\n');
check('both roles now show up in the tab rail',
    JSON.stringify(editor.rolesWithCode()) === JSON.stringify(['wand', 'icon']),
    editor.rolesWithCode().join(','));

// ── Switch tabs, edit each, and confirm nothing leaks between roles ──
check('starts on wand', editor.getActiveRole() === 'wand');
const afterSwitch = editor.setActiveRole('icon');
check('setActiveRole returns the new active role', afterSwitch === 'icon');
check('getActiveRole agrees', editor.getActiveRole() === 'icon');
check('switching to icon does not touch its code',
    editor.getCode('icon') === '# icon code v1\n');

editor.setCode('# icon code v2, edited while active\n');
check('an edit with no role argument lands on the active role (icon)',
    editor.getCode('icon') === '# icon code v2, edited while active\n');
check('the wand slot is untouched by an icon-tab edit',
    editor.getCode('wand') === '# wand code v1\n');

editor.setActiveRole('wand');
check('switching back to wand carries its own code, unaffected by icon edits',
    editor.getCode('wand') === '# wand code v1\n');
editor.setCode('# wand code v2, edited while active\n');
check('an edit on the wand tab does not leak into icon',
    editor.getCode('icon') === '# icon code v2, edited while active\n');

check('setActiveRole is a no-op for an unknown role',
    editor.setActiveRole('nosuchrole') === 'wand' && editor.getActiveRole() === 'wand');

// ── Version history is per-role too ──
editor.saveVersion('# wand code v1\n', 'From chat', 'wand');
editor.saveVersion('# wand code v2, edited while active\n', 'Manual edit', 'wand');
check('wand has its own version count', editor.getVersionCount('wand') === 2);
check('icon has no versions of its own', editor.getVersionCount('icon') === 0);
check('wand version index points at the latest save', editor.getVersionIndex('wand') === 1);

// ── clearAllRoles() leaves no residue ──
editor.clearAllRoles();
check('clearAllRoles resets the active role to the first one',
    editor.getActiveRole() === 'wand');
check('clearAllRoles empties every role\'s code',
    ROLES.every(r => editor.getCode(r) === ''));
check('clearAllRoles empties every role\'s version history',
    ROLES.every(r => editor.getVersionCount(r) === 0));
check('no role shows up in the tab rail after a clear',
    editor.rolesWithCode().length === 0, editor.rolesWithCode().join(','));

console.log();
if (fails.length) {
    console.log(`FAILED: ${fails.length}`);
    for (const f of fails) console.log('  -', f);
    process.exit(1);
}
console.log('Per-role editor state OK');
