# Adding a new device to ChatBroadcast's knowledge

Instructions for an agent (or person) adding a device type the chat assistant can write games for.
Based on how the icon display and the Splat Companion were added.

This file covers the **assistant's knowledge and the ChatBroadcast app**. For the device firmware,
the Broadcast Box / Dial serving side, host devtests and repository docs, follow
[`../../docs_and_design/DEVICE_ONBOARDING_SURFACES.md`](../../docs_and_design/DEVICE_ONBOARDING_SURFACES.md).

## How the knowledge is organised

| File | Holds | Sent to the model |
|---|---|---|
| `policy.md` | Behavior: audience, scope, honesty, reply format, game design | Always |
| `platform.md` | Rules shared by every device: markers, MicroPython limits, ESP-NOW, exit behavior, size budget | Always |
| `troubleshooting.md` | Firmware-verified meaning of every light, sound and screen, per device; USB and card-writing steps | Always |
| `advanced.md` | Technical addendum | Advanced UI mode only |
| `devices/<role>.md` | One device: contract, API, template, limits, checklist | Always, one per row in `js/roles.js` |
| `devices/_TEMPLATE.md` | Blank device file | Never |

A new device adds **one file in `devices/`** plus rows elsewhere. It never edits `policy.md`, and
edits `platform.md` only if the device changes a rule every device shares.

## Steps

1. **Collect facts from the firmware tree.** Read the device's `main.py` (the exact call that
   launches a game), its `hubtype`, and the `lib/` modules a game may import. Note what is
   already built when `play()` runs, what may be `None`, and which hardware the device lacks. Mark
   anything you could not verify. Do not copy facts from another device's knowledge file.
2. **Write `devices/<role>.md`** from `devices/_TEMPLATE.md`. `<role>` is the short key used in
   `[DEVICE: <role>]` markers: lowercase letters and underscores. Keep the canonical template small,
   because every generated game starts from it.
3. **Add the role row** in `js/roles.js`: `key`, `label`, `tabLabel`, `glyph`, `previewGlyph`,
   `previewCaption`, `designator` (the Box/Dial file suffix, e.g. `_splat`), `hubtype`,
   `signature`, `optional`, `hasPreview`, `hasIconLeg`, `knowledgeFile: 'knowledge/devices/<role>.md'`,
   and `unknownNamesIn` if the device has an inventory (step 4).
4. **Inventory of named things** — only if a game names things that must already exist on the
   device (like icons on the display or action names on the Splat). Follow the Splat pattern:
   - The device's source file is the source of truth (e.g. `SplatCompanion/Companion/splat_api.py`).
   - Add `tools/sync_<role>_<things>.py` that generates `js/<role>/<role><Things>.js` from it and
     supports `--check` for drift (model: `tools/sync_splat_actions.py`).
   - Add a checker module (model: `js/splat/splatActionCheck.js`) exporting the list for the
     prompt and an `unknown…In(code)` function; point the role's `unknownNamesIn` at it. The app
     then refuses to send a game that names something the device lacks.
   - Append the list to the request under a clear heading, and name that heading in the device
     file ("Use only the names in '<HEADING>' sent with the request"). Today this is
     `getSystemPrompt()` in `js/app.js`; after the planned move it is `js/prompt/buildRequest.js`.
5. **Add the device's signals to `troubleshooting.md`** — every light, sound or screen a teacher can
   see without a serial cable, with the trigger, taken from the firmware. Anything not verified is
   left out.
6. **Starter ideas and guided mode.** Add two or three teacher-language ideas tagged with the role
   to `js/starterIdeas.js`, and add the device as a choice in guided mode. *(Both land with step 5
   of the prompt plan; skip until they exist.)*
7. **Test prompts.** Add prompts for the device to `tools/prompt_eval.mjs`: one game for the device
   alone and one two-device game with the wand. *(Lands with step 4 of the prompt plan.)*
8. **Firmware, Box/Dial, devtests, docs:** `DEVICE_ONBOARDING_SURFACES.md`.

## App surfaces a device touches

"Generic" means the code reads `js/roles.js` and needs no edit. "Per device" means an edit is
needed. Checked against the code on 2026-09-30; re-check line references before relying on them.

| Surface | File | Status |
|---|---|---|
| Role table | `js/roles.js` `ROLES` | **Per device** — the one row (step 3) |
| Knowledge loading | `js/chat.js` `loadKnowledgeBase` (from `knowledgeFile`) | Generic |
| Code block routing | `js/chat.js` `extractCodeBlocks` / `roleBefore` | Generic |
| Signature check at send | `js/upload.js` `validateGameCode` (from `signature`, `optional`) | Generic |
| Size check at send | `js/upload.js` `MAX_WAND_GAME_BYTES` | Wand only; add a limit if the device has its own measured one |
| Reserved slug suffixes | `js/gameName.js` (from `designator`) | Generic |
| Per-role editor state | `js/editor.js` `roleState` | Generic |
| Device tabs markup | `index.html` — two `.device-tab[data-role]` groups (preview toolbar and code drawer) | **Per device** — one button in each group |
| Tab enable / labels | `js/app.js` `syncRoleRail` | Generic, except the icon-maker button (icon only) |
| Preview | `js/app.js` `updatePreview` / `syncPreviewEmpty` | Generic "no preview" when `hasPreview: false`; a live preview needs its own branch |
| Send: extra files | `js/app.js` `confirmSend` (loop over roles; `designator`, `unknownNamesIn`, `hasIconLeg`) | Generic, unless the device ships extra files like the display's icons |
| Inventory in the prompt | `js/app.js` `getSystemPrompt` (icons, Splat actions) | **Per device** if it has an inventory (step 4) |
| Required-signature lines in the prompt | `js/app.js` `ROLE_SIGNATURE_LINES` | Generic |
| Hardware requirements overlay | `js/hardware.js` `buildHardwareReqs` `stations` | Not wired for any device yet |
| Direct USB connection | `js/device/wandDeviceLink.js` model | **Per device**, only if it connects without the Box |
| Troubleshooting | `knowledge/troubleshooting.md` | **Per device** (step 5) |
| Starter ideas / guided mode | `js/starterIdeas.js`, guided-mode choices | **Per device** (step 6), once they exist |
| Test prompts | `tools/prompt_eval.mjs` | **Per device** (step 7), once it exists |

## Done means

- `devices/<role>.md` follows the template, with no unverified claims.
- The role row exists, and a two-device test game sends from the app without a signature or
  inventory refusal.
- Its inventory sync script, if any, passes `--check`.
- `troubleshooting.md` covers every signal the firmware shows.
