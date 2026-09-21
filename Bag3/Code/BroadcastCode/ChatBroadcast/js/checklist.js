/**
 * Plain-language hardware checklist for teachers — icon row on connect / send.
 */

export function buildComponentChecklist(capabilities, requiredTags) {
    const items = [];
    items.push({ icon: "wand", kind: "wand", label: "at least 1 wand" });

    const tags = requiredTags || [];
    const n = tags.length;
    if (n > 1) {
        items.push({ icon: "smartphone-nfc", kind: "nfc", label: `${n} NFC cards` });
    } else if (n === 1) {
        items.push({ icon: "smartphone-nfc", kind: "nfc", label: `1 NFC card (${tags[0]})` });
    } else if (capabilities && capabilities.usesNfc) {
        items.push({ icon: "smartphone-nfc", kind: "nfc", label: "NFC cards (stop / launch tags)" });
    }

    if (capabilities) {
        if (capabilities.usesAccel) {
            items.push({ icon: "vibrate", kind: "shake", label: "shake / jump sensor" });
        }
        if (capabilities.usesButton) {
            items.push({ icon: "circle", kind: "other", label: "wand button" });
        }
        if (capabilities.usesBuzzer) {
            items.push({ icon: "volume-2", kind: "other", label: "buzzer" });
        }
        if (capabilities.usesLeds || capabilities.hasCode) {
            items.push({ icon: "grid-3x3", kind: "other", label: "LED matrix" });
        }
    }

    return items;
}

/** @deprecated prefer renderChecklistIcons */
export function checklistLines(items) {
    return (items || []).map((i) => i.label);
}
