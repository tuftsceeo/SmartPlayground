/**
 * jsonIcon.js -- read an icon from a "rows + pal" JSON file, pixel for pixel.
 *
 * Unlike an imported image this does no segmentation: each character in
 * `rows` is one cell, so what is in the file is what lands on the grid.
 *
 *   {"rows": ["..AA..", ...], "pal": {"A": "#ff9900", ...}}      one icon
 *   {"_key": "...", "m00": {rows, pal}, "m01": {...}}             several (pick one)
 *
 * `.` (or space) = off. `pal` values are "#rrggbb" or [r,g,b]. They are SCREEN
 * colours (as seen/painted) by default and are converted to authored linear duty
 * at this boundary; set "space": "duty" on the icon (or file) if they are already
 * duty bytes. Rows must be a square W x H grid; the caller switches profile to fit.
 */
import { displayToAuthored } from "./ledDisplay.js";

/** @returns {{ids:string[], multi:boolean, get:(id?:string)=>{id:string,w:number,h:number,pixels:number[][]}}} */
export function parseIconJson(text) {
  let data;
  try { data = JSON.parse(text); } catch (e) { throw new Error(`Not valid JSON: ${e.message}`); }
  const isIcon = (o) => o && typeof o === "object" && Array.isArray(o.rows) && o.pal;
  const entries = isIcon(data)
    ? { icon: data }
    : Object.fromEntries(Object.entries(data || {}).filter(([k, v]) => !k.startsWith("_") && isIcon(v)));
  const ids = Object.keys(entries);
  if (!ids.length) throw new Error('No icon found: expected {"rows": [...], "pal": {...}}.');
  const fileSpace = data && data.space;

  function get(id) {
    const key = id ?? ids[0];
    const o = entries[key];
    if (!o) throw new Error(`No icon "${key}" in this file.`);
    const h = o.rows.length, w = String(o.rows[0] || "").length;
    if (!h || !w || w !== h) throw new Error(`"${key}": rows must be a square grid (got ${w}x${h}).`);
    const space = o.space || fileSpace || "screen";
    const toRgb = (v) => {
      const rgb = Array.isArray(v) ? v.map(Number) : [1, 3, 5].map((i) => parseInt(String(v).replace("#", "").slice(i - 1, i + 1), 16));
      if (rgb.length !== 3 || rgb.some((n) => !Number.isFinite(n))) throw new Error(`"${key}": bad palette colour ${JSON.stringify(v)}.`);
      return space === "duty" ? rgb : displayToAuthored(rgb);
    };
    const pal = {};
    for (const [ch, v] of Object.entries(o.pal)) pal[ch] = toRgb(v);
    const pixels = [];
    o.rows.forEach((row, y) => {
      if (String(row).length !== w) throw new Error(`"${key}": row ${y} is ${String(row).length} wide, expected ${w}.`);
      for (const ch of String(row)) {
        if (ch === "." || ch === " ") pixels.push([0, 0, 0]);
        else if (pal[ch]) pixels.push(pal[ch].slice());
        else throw new Error(`"${key}": row ${y} uses "${ch}" which is not in pal.`);
      }
    });
    return { id: key === "icon" ? null : key, w, h, pixels };
  }
  return { ids, multi: ids.length > 1, get };
}
