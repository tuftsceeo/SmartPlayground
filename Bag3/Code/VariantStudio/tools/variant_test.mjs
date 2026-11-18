// Run from VariantStudio/:  node tools/variant_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { REGIONS, TOKENS } from '../js/regions.js';
import { validate, compile, encodeVariant, decodeVariant, normalize, emptyVariant } from '../js/variant.js';
import { toWire, fromWire } from '../js/claude.js';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const appHtml = readFileSync(join(root, '../ChatBroadcast/index.html'), 'utf8');
const appCss = readFileSync(join(root, '../ChatBroadcast/css/app.css'), 'utf8');
let n = 0;
const test = (name, fn) => { fn(); n++; console.log('ok', name); };

test('every catalog selector matches Chat Broadcast markup', () => {
    for (const r of REGIONS) {
        for (const part of r.sel.split(',').map(s => s.trim())) {
            const first = part.split(/\s+/)[0];
            let found;
            if (first.startsWith('#')) found = appHtml.includes(`id="${first.slice(1)}"`);
            else if (first.startsWith('.')) found = new RegExp(`class="[^"]*\\b${first.slice(1)}\\b`).test(appHtml);
            else found = appHtml.includes('<' + first);
            assert.ok(found, `${r.id}: "${first}" not found in ChatBroadcast/index.html`);
        }
    }
});

test('catalog ids are unique', () => {
    const ids = REGIONS.map(r => r.id);
    assert.equal(new Set(ids).size, ids.length);
});

test('every token exists in app.css :root', () => {
    for (const t of TOKENS) assert.ok(appCss.includes(`${t}:`), `${t} missing from app.css`);
});

test('example variant is valid', () => {
    const v = JSON.parse(readFileSync(join(root, 'examples/big-buttons.json'), 'utf8'));
    assert.deepEqual(validate(v), []);
});

test('locked parts cannot be hidden', () => {
    const errs = validate({ ...emptyVariant(), hide: ['send-box', 'connect'] });
    assert.equal(errs.length, 2);
});

test('all three splash cards hidden is rejected', () => {
    const errs = validate({ ...emptyVariant(), hide: ['splash-scratch', 'splash-gallery', 'splash-saved'] });
    assert.ok(errs.some(e => /start screen card/.test(e)));
    assert.deepEqual(validate({ ...emptyVariant(), hide: ['splash-scratch', 'splash-gallery'] }), []);
});

test('unsafe values and properties are rejected', () => {
    const bad = (props) => validate({ ...emptyVariant(), styles: [{ region: 'chat-box', props }] });
    assert.ok(bad({ display: 'none' }).length);
    assert.ok(bad({ opacity: '0' }).length);
    assert.ok(bad({ color: 'red; display:none' }).length);
    assert.ok(bad({ background: 'url(https://evil.example/x.png)' }).length);
    assert.ok(bad({ color: 'red !important' }).length);
    assert.deepEqual(bad({ background: 'url(data:image/png;base64,AAAA)' }).length, 1, 'semicolon in data url is still rejected');
    assert.deepEqual(bad({ background: 'linear-gradient(90deg, #fff, #000)', 'border-radius': '20px' }), []);
});

test('unknown tokens, fonts, labels are rejected', () => {
    assert.ok(validate({ ...emptyVariant(), tokens: { '--nope': '#fff' } }).length);
    assert.ok(validate({ ...emptyVariant(), fonts: { body: 'Wingdings' } }).length);
    assert.ok(validate({ ...emptyVariant(), labels: { 'chat-box': 'hi' } }).length);
    assert.ok(validate({ ...emptyVariant(), labels: { 'send-box': '' } }).length);
});

test('compile scopes everything and hides last', () => {
    const v = JSON.parse(readFileSync(join(root, 'examples/big-buttons.json'), 'utf8'));
    const c = compile(v);
    assert.match(c.css, /html\[data-variant\] #btn-download/);
    assert.match(c.css, /--purple: #2563eb;/);
    assert.match(c.css, /'Fredoka'/);
    assert.ok(c.css.lastIndexOf('display: none') > c.css.lastIndexOf('font-size'));
    assert.equal(c.mode, 'simple');
    assert.ok(c.fontUrl.includes('family=Fredoka'));
    const input = c.labels.find(l => l.id === 'chat-input');
    assert.equal(input.attr, 'placeholder');
});

test('hide rules beat .advanced-only revert on specificity', () => {
    // body.ui-advanced .advanced-only = (0,2,1); ours on a class part = (0,2,1)+
    const c = compile({ ...emptyVariant(), hide: ['dev-mode'] });
    assert.match(c.css, /html\[data-variant\] #btn-dev-mode/); // id selector: (1,1,1)
});

test('link encoding round-trips unicode', () => {
    const v = normalize({ ...emptyVariant('Café ✦'), labels: { 'send-box': 'Lancer →' } });
    assert.deepEqual(decodeVariant(encodeVariant(v)), v);
});

test('Claude wire shape round-trips', () => {
    const v = normalize(JSON.parse(readFileSync(join(root, 'examples/big-buttons.json'), 'utf8')));
    assert.deepEqual(fromWire(toWire(v)), v);
});

console.log(`\n${n} tests passed`);
