/**
 * Inline stroke icons for ChatBroadcast chrome.
 * Mock paths from Box Manager.dc.html; Lucide paths (ISC) for the rest.
 * No lucide npm package — paths only.
 */

const SVG_ATTRS =
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';

/** Lucide / mock inner path markup keyed by name. */
const PATHS = {
    // Mock-up paths
    wifi:
        '<path d="M2 8.5a15 15 0 0 1 20 0"/><path d="M5.5 12a10 10 0 0 1 13 0"/><path d="M9 15.5a5 5 0 0 1 6 0"/><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none"/>',
    box:
        '<path d="M3 8l9-4 9 4-9 4-9-4z"/><path d="M3 8v8l9 4 9-4V8"/><path d="M12 12v8"/>',
    plug:
        '<path d="M9 2v4M15 2v4"/><path d="M6 6h12v4a6 6 0 0 1-12 0V6z"/><path d="M12 16v6"/>',
    floppy:
        '<path d="M5 4h11l3 3v13H5V4z"/><path d="M8 4v5h7V4"/><path d="M8 14h8v6H8z"/>',
    wand:
        '<path d="M4 20L16 8"/><path d="M18 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
    nfcCard:
        '<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="12" cy="12" r="2.5"/>',
    close:
        '<path d="M6 6l12 12M18 6L6 18"/>',
    trash:
        '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
    pencil:
        '<path d="M4 20l4-1 11-11-3-3L5 16l-1 4z"/>',
    radio:
        '<circle cx="12" cy="12" r="8"/>',
    radioOn:
        '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5" fill="currentColor" stroke="none"/>',
    check:
        '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    warning:
        '<path d="M12 3l10 18H2L12 3z"/><path d="M12 9v5"/><circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none"/>',
    modeServe:
        '<rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="0.6" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="0.6" fill="currentColor" stroke="none"/>',
    shakePhone:
        '<rect x="7" y="2" width="10" height="20" rx="3"/><path d="M7 7h10M7 17h10"/>',
    spinner:
        '<circle cx="12" cy="12" r="8" stroke-dasharray="38" stroke-dashoffset="12"/>',
    code:
        '<path d="M8 6l-5 6 5 6"/><path d="M16 6l5 6-5 6"/>',

    // Lucide (simplified stroke paths, viewBox 0 0 24 24)
    wrench:
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "message-circle":
        '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>',
    library:
        '<path d="M16 6l4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/>',
    "folder-open":
        '<path d="M6 14l1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    shuffle:
        '<path d="M2 18h1.4a4 4 0 0 0 3.3-1.7l6.6-9.6a4 4 0 0 1 3.3-1.7H22"/><path d="M18 2l4 4-4 4"/><path d="M2 6h1.9a4 4 0 0 1 3.3 1.7l.7 1"/><path d="M22 18h-5.9a4 4 0 0 1-3.3-1.7l-.7-1"/><path d="M18 14l4 4-4 4"/>',
    send:
        '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="M21.854 2.147l-10.94 10.939"/>',
    download:
        '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/>',
    cable:
        '<path d="M17 21v-2a1 1 0 0 1-1-1v-1a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1"/><path d="M19 15V6.5a1 1 0 0 0-7 0v11a1 1 0 0 1-7 0V9"/><path d="M21 21v-2h-4"/><path d="M3 5h4V3"/><path d="M7 5a1 1 0 0 1 1 1v1a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a1 1 0 0 1 1-1"/>',
    unplug:
        '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    gamepad:
        '<line x1="6" x2="10" y1="12" y2="12"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="15" x2="15.01" y1="13" y2="13"/><line x1="18" x2="18.01" y1="11" y2="11"/><rect width="20" height="12" x="2" y="6" rx="2"/>',
    "square-arrow-out-up-right":
        '<path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"/><path d="M21 3l-9 9"/><path d="M15 3h6v6"/>',
    "smartphone-nfc":
        '<rect width="7" height="12" x="2" y="6" rx="1"/><path d="M13 8.32a7.43 7.43 0 0 1 0 7.36"/><path d="M16.46 6.21a11.76 11.76 0 0 1 0 11.58"/><path d="M19.91 4.1a15.91 15.91 0 0 1 .01 15.8"/>',
    vibrate:
        '<path d="M2 8a2 2 0 0 1 2-2h2v12H4a2 2 0 0 1-2-2Z"/><path d="M18 6h2a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2"/><rect width="8" height="16" x="8" y="4" rx="1"/><path d="m5.5 2.5-.5-.5"/><path d="m5.5 21.5-.5.5"/><path d="m18.5 2.5.5-.5"/><path d="m18.5 21.5.5.5"/>',
    circle: '<circle cx="12" cy="12" r="10"/>',
    "volume-2":
        '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
    "grid-3x3":
        '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>',
    music:
        '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    palette:
        '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
    tag:
        '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
    snowflake:
        '<path d="M2 12h20"/><path d="M12 2v20"/><path d="m20 16-4-4 4-4"/><path d="m4 8 4 4-4 4"/><path d="m16 4-4 4-4-4"/><path d="m8 20 4-4 4 4"/>',
    rainbow:
        '<path d="M22 17a10 10 0 0 0-20 0"/><path d="M6 17a6 6 0 0 1 12 0"/><path d="M10 17a2 2 0 0 1 4 0"/>',
    "arrow-up":
        '<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/>',
    "chef-hat":
        '<path d="M17 21a1 1 0 0 0 1-1v-5.35c0-.457.316-.844.727-1.041a4 4 0 0 0-2.134-7.589 5 5 0 0 0-9.186 0 4 4 0 0 0-2.134 7.588c.411.198.727.585.727 1.041V20a1 1 0 0 0 1 1Z"/><path d="M6 17h12"/>',
    "circle-check":
        '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>',
    save:
        '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    home:
        '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "brain-circuit":
        '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M9 13a4.5 4.5 0 0 0 3-4"/><path d="M12 13h4"/><path d="M12 18h4"/><path d="M12 5h4"/><path d="M16 9h.01"/><path d="M20 9h.01"/><path d="M16 13h.01"/><path d="M20 13h.01"/><path d="M16 17h.01"/><path d="M20 17h.01"/><path d="M17 5a3 3 0 1 1 .5 5.5"/><circle cx="9" cy="9" r="0.5" fill="currentColor"/>',
};

/**
 * @param {string} name
 * @param {{ size?: number, className?: string, title?: string, strokeWidth?: number|string }} [opts]
 * @returns {string} HTML string for an inline SVG
 */
export function iconSvg(name, opts = {}) {
    const size = opts.size ?? 15;
    const cls = opts.className ? ` class="${opts.className}"` : "";
    const title = opts.title ? `<title>${escapeAttr(opts.title)}</title>` : "";
    const sw = opts.strokeWidth != null ? ` stroke-width="${opts.strokeWidth}"` : "";
    const body = PATHS[name];
    if (!body) {
        console.warn(`[icons] unknown icon "${name}"`);
        return "";
    }
    return `<svg ${SVG_ATTRS.replace('stroke-width="1.8"', sw ? `stroke-width="${opts.strokeWidth}"` : 'stroke-width="1.8"')} width="${size}" height="${size}"${cls}>${title}${body}</svg>`;
}

/** Create a real SVG Element (for appendChild). */
export function iconEl(name, opts = {}) {
    const wrap = document.createElement("span");
    wrap.className = "icon-wrap";
    wrap.innerHTML = iconSvg(name, opts);
    return wrap.firstElementChild || wrap;
}

export function categoryIcon(category) {
    if (category === "sound") return "music";
    if (category === "color") return "palette";
    if (category === "multi") return "tag";
    return "wand";
}

export function exampleIcon(ex) {
    if (ex?.icon) return ex.icon;
    const map = {
        melody: "music",
        freezedance: "snowflake",
        rainbow: "rainbow",
        shakerainbow: "rainbow",
        jump: "arrow-up",
        cooking: "chef-hat",
        jumpin: "brain-circuit",
    };
    return map[ex?.id] || categoryIcon(ex?.category) || "wand";
}

function escapeAttr(s) {
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}
