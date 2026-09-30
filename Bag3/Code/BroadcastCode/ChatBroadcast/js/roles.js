/**
 * Device roles -- the single table every role-aware surface reads from.
 *
 * A role is a device type ChatBroadcast can generate code for. Adding one
 * means adding a row here (plus, on the firmware side, a ROLE_FILES entry
 * in code_server.py and a device tree -- see
 * Bag3/Code/BroadcastCode/docs_and_design/DEVICE_ONBOARDING_SURFACES.md
 * Surface 3).
 *
 * `wand` MUST stay first: ROLES[0] is the default active role, the role an
 * unmarked code block lands in, and the only role a direct wand connection
 * (js/device/wandGameInstaller.js) can push.
 *
 * Fields:
 *   label         full name, used in prose and the connect-overlay button
 *   tabLabel      short name for the device-tab chips
 *   glyph         data-icon name shown on the tab (see icons.js)
 *   previewGlyph  data-icon name for the preview-empty placeholder
 *   previewCaption caption under that placeholder
 *   designator    the Box/Dial staging suffix (ROLE_FILES's 'suffix');
 *                 '' for the wand, which owns the undesignated file
 *   hubtype       the ROLE_FILES / hubtype.txt key on the device
 *   signature     required play() parameter names, in order
 *   optional      names in `signature` the device tolerates missing
 *                 (an older game generated before that parameter existed)
 *   hasPreview    false means the role gets a static "no preview" state
 *                 instead of a live simulator
 *   hasIconLeg    true only for the role whose games ship extra named
 *                 files alongside the game file (only icon, today)
 *   knowledgeFile device knowledge file (knowledge/devices/<role>.md), loaded
 *                 into the system prompt after the shared files
 *   unknownNamesIn optional (code) => string[]: names the game uses that
 *                 the device does not have; a non-empty result refuses
 *                 the send (splat only, today)
 */
import { unknownSplatActionsIn } from './splat/splatActionCheck.js';

export const ROLES = [
    {
        key: 'wand',
        label: 'Wand',
        tabLabel: 'Wand',
        glyph: 'wand',
        previewGlyph: 'wand',
        previewCaption: 'wand preview',
        designator: '',
        hubtype: 'wand',
        signature: ['nfc', 'leds', 'buz', 'accel', 'i2c', 'enow', 'batt'],
        optional: ['batt'],
        hasPreview: true,
        hasIconLeg: false,
        knowledgeFile: 'knowledge/devices/wand.md',
    },
    {
        key: 'icon',
        label: 'Icon display',
        tabLabel: 'Display',
        glyph: 'gamepad',
        previewGlyph: 'grid-3x3',
        previewCaption: 'display preview',
        designator: '_icon',
        hubtype: 'icon_display',
        signature: ['nfc', 'panel', 'enow'],
        optional: [],
        hasPreview: true,
        hasIconLeg: true,
        knowledgeFile: 'knowledge/devices/icon_display.md',
    },
    {
        key: 'splat',
        label: 'Splat Companion',
        tabLabel: 'Splat',
        glyph: 'cable',
        previewGlyph: 'cable',
        previewCaption: 'no preview for this device',
        designator: '_splat',
        hubtype: 'splat_companion',
        signature: ['splat', 'leds', 'enow', 'batt'],
        optional: ['batt'],
        hasPreview: false,
        hasIconLeg: false,
        knowledgeFile: 'knowledge/devices/splat_companion.md',
        unknownNamesIn: unknownSplatActionsIn,
    },
];

const BY_KEY = Object.fromEntries(ROLES.map(r => [r.key, r]));

/** The role object for `key`, or undefined if it names no role. */
export function roleInfo(key) {
    return BY_KEY[key];
}

export const DEFAULT_ROLE = ROLES[0].key;

/** `def play(...)` line for a role, `batt` shown with its device-side
 * default. Used in error text and the system prompt. */
export function signatureFor(key) {
    const r = BY_KEY[key];
    if (!r) return null;
    const shown = r.signature.map(n => (n === 'batt' ? 'batt=None' : n));
    return `def play(${shown.join(', ')})`;
}
