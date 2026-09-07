/**
 * Inline stroke icons for the simulator panel.
 *
 * Paths are copied verbatim from ChatBroadcast/js/icons.js — the canonical
 * set for this product — rather than imported from it: ChatBroadcast depends
 * on this directory (it imports wand-sim.js), so the dependency may not run
 * the other way, and the Simulator has to stand alone when served on its own.
 * `sparkles` and `mop-sparkles` aren't in that file; they are Lucide (ISC,
 * https://lucide.dev) like the rest of the generic glyphs here.
 *
 * Style follows the design system: 24x24 viewBox, no fill, currentColor
 * stroke at 1.8, round caps and joins — dropping to 1.3 at the 40px+ sizes
 * the overlays use, where 1.8 reads heavy.
 */

/** Lucide / mock inner path markup keyed by name. */
const PATHS = {
  // ── Panel chrome ────────────────────────────────────────────────────
  "volume-2":
    '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
  "volume-x":
    '<path d="M16 9a5 5 0 0 1 .95 2.293"/><path d="M19.364 5.636a9 9 0 0 1 1.889 9.96"/><path d="m2 2 20 20"/><path d="m7 7-.587.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298V11"/><path d="M9.828 4.172A.686.686 0 0 1 11 4.657v.686"/>',
  code:
    '<path d="M8 6l-5 6 5 6"/><path d="M16 6l5 6-5 6"/>',
  "mop-sparkles":
    '<path d="M10 22a3 3 0 0 1-3-3"/><path d="M10 22c2.761 0 5-1.79 5-4-4.42 0-4.08-5-8.5-5a4.501 4.501 0 0 0 0 9z"/><path d="M10 3H8"/><path d="M12.5 11.5 22 2"/><path d="M20 13v4"/><path d="M22 15h-4"/><path d="M4 5v4"/><path d="M6 7H2"/><path d="m6.98 13.02 2.665-2.664a1.21 1.21 0 0 1 1.71 0l2.29 2.288a1.21 1.21 0 0 1 0 1.712l-2.088 2.087"/><path d="M9 2v2"/>',

  // ── Gestures ────────────────────────────────────────────────────────
  "arrow-up":
    '<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/>',
  shuffle:
    '<path d="M2 18h1.4a4 4 0 0 0 3.3-1.7l6.6-9.6a4 4 0 0 1 3.3-1.7H22"/><path d="M18 2l4 4-4 4"/><path d="M2 6h1.9a4 4 0 0 1 3.3 1.7l.7 1"/><path d="M22 18h-5.9a4 4 0 0 1-3.3-1.7l-.7-1"/><path d="M18 14l4 4-4 4"/>',
  vibrate:
    '<path d="M2 8a2 2 0 0 1 2-2h2v12H4a2 2 0 0 1-2-2Z"/><path d="M18 6h2a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2"/><rect width="8" height="16" x="8" y="4" rx="1"/><path d="m5.5 2.5-.5-.5"/><path d="m5.5 21.5-.5.5"/><path d="m18.5 2.5.5-.5"/><path d="m18.5 21.5.5.5"/>',
  shakePhone:
    '<rect x="7" y="2" width="10" height="20" rx="3"/><path d="M7 7h10M7 17h10"/>',

  // ── Tags ────────────────────────────────────────────────────────────
  "smartphone-nfc":
    '<rect width="7" height="12" x="2" y="6" rx="1"/><path d="M13 8.32a7.43 7.43 0 0 1 0 7.36"/><path d="M16.46 6.21a11.76 11.76 0 0 1 0 11.58"/><path d="M19.91 4.1a15.91 15.91 0 0 1 .01 15.8"/>',
  nfcCard:
    '<rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="12" cy="12" r="2.5"/>',
  tag:
    '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
  close:
    '<path d="M6 6l12 12M18 6L6 18"/>',

  // ── Overlays ────────────────────────────────────────────────────────
  wand:
    '<path d="M4 20L16 8"/><path d="M18 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
  sparkles:
    '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',

  // ── Status line ─────────────────────────────────────────────────────
  "loader-circle":
    '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
  "circle-check":
    '<circle cx="12" cy="12" r="10"/><path d="m16 9-5.5 5.5L8 12"/>',
  "circle-play":
    '<path d="M9 9.003a1 1 0 0 1 1.517-.859l4.997 2.997a1 1 0 0 1 0 1.718l-4.997 2.997A1 1 0 0 1 9 14.996z"/><circle cx="12" cy="12" r="10"/>',
  "circle-stop":
    '<circle cx="12" cy="12" r="10"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
  "triangle-alert":
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
};

/**
 * Inline <svg> markup for `name` at `size` px. Unknown names throw rather
 * than render an empty box — a typo'd icon should surface at the call site,
 * not turn into a silent gap in the panel.
 */
export function icon(name, size = 18) {
  const paths = PATHS[name];
  if (!paths) throw new Error(`icons.js: no icon named "${name}"`);
  // 1.8 is the system weight; the 40px+ overlay glyphs need 1.3 or the
  // strokes read as slabs at that scale.
  const stroke = size >= 40 ? 1.3 : 1.8;
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

export { PATHS };
