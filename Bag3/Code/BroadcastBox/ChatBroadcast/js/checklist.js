/**
 * Plain-language hardware checklist for teachers — the full "You'll need:"
 * list shown at the connect / send-confirm stage.
 */

export function buildComponentChecklist(capabilities, requiredTags) {
    const items = [];
    items.push({ icon: '🪄', label: 'at least 1 wand' });

    const tags = requiredTags || [];
    const n = tags.length;
    if (n > 1) {
        items.push({ icon: '🃏', label: `${n} NFC cards` });
    } else if (n === 1) {
        items.push({ icon: '🃏', label: `1 NFC card (${tags[0]})` });
    } else if (capabilities && capabilities.usesNfc) {
        items.push({ icon: '🃏', label: 'NFC cards (stop / launch tags)' });
    }

    if (capabilities) {
        if (capabilities.usesAccel) items.push({ icon: '📳', label: 'shake / jump sensor' });
        if (capabilities.usesButton) items.push({ icon: '🔘', label: 'wand button' });
        if (capabilities.usesBuzzer) items.push({ icon: '🔊', label: 'buzzer' });
        if (capabilities.usesLeds || capabilities.hasCode) {
            items.push({ icon: '💡', label: 'LED matrix' });
        }
    }

    return items;
}

export function checklistLines(items) {
    return (items || []).map((i) => `${i.icon} ${i.label}`);
}
