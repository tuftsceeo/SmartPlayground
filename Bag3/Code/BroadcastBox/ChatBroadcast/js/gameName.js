/**
 * gameName.js — slugify + reserved/duplicate validation for Broadcast Box games.
 * Pure functions; no DOM. Used by the send-confirm flow.
 *
 * A slug is also a MicroPython MODULE NAME on both the Box (/flash/games/<slug>.py)
 * and the wand (/games/<slug>.py, imported with __import__). So it must be a legal
 * Python identifier: underscores, not hyphens, and never leading with a digit.
 */

import { EXAMPLES } from "./examples.js";

export const SLUG_MAX = 16;

/** Python keywords + module names a game file must never shadow on either device. */
const PYTHON_RESERVED = [
  "and", "as", "assert", "break", "class", "continue", "def", "del", "elif",
  "else", "except", "finally", "for", "from", "global", "if", "import", "in",
  "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
  "while", "with", "yield", "none", "true", "false",
  "main", "boot", "sys", "os", "time", "gc", "machine", "network", "socket",
  "struct", "json", "math", "random", "hashlib",
];

/** Wand built-in game modules and command tags — a pulled game must not shadow one. */
const WAND_RESERVED = [
  "colorquest", "freezedance", "jumpin", "cooking", "melody", "shake",
  "shakerainbow", "rainbow", "jump", "sound", "nfcsound", "simpleicecream",
  "multiicecream", "gestures", "finddevice",
  "start", "stop", "erase", "battery", "getcode", "done",
  "buttondown", "buttonup", "whenshake", "playnote",
];

/** Box-side names that are not games. */
const BOX_RESERVED = ["payload", "index", "active", "stats"];

export const RESERVED_SLUGS = new Set([
  ...EXAMPLES.map((e) => e.id),
  ...PYTHON_RESERVED,
  ...WAND_RESERVED,
  ...BOX_RESERVED,
]);

/**
 * Lowercase, non-alphanumerics→underscores, collapse repeats, cap SLUG_MAX.
 * Guarantees the result is a legal Python identifier (or "").
 */
export function slugify(name) {
  if (!name || typeof name !== "string") return "";
  let s = name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
  if (!s) return "";
  // A module name may not start with a digit.
  if (/^[0-9]/.test(s)) s = "g" + s;
  if (s.length > SLUG_MAX) s = s.slice(0, SLUG_MAX).replace(/_$/, "");
  return s;
}

/** True if `slug` is a legal Python identifier we are willing to write to flash. */
export function isValidSlug(slug) {
  return typeof slug === "string" && /^[a-z][a-z0-9_]*$/.test(slug) && slug.length <= SLUG_MAX;
}

/**
 * @param {string} prettyName
 * @param {{ existingSlugs?: string[], allowReplace?: boolean }} [opts]
 * @returns {{ ok: true, slug: string, pretty: string } | { ok: false, reason: string, slug?: string }}
 */
export function validateGameName(prettyName, opts = {}) {
  const pretty = (prettyName || "").trim();
  if (!pretty) return { ok: false, reason: "Give the game a short name." };
  const slug = slugify(pretty);
  if (!slug) return { ok: false, reason: "That name has no letters or numbers left." };
  if (!isValidSlug(slug)) {
    return { ok: false, reason: `"${pretty}" can't be used as a game name.`, slug };
  }
  if (RESERVED_SLUGS.has(slug)) {
    return { ok: false, reason: `"${pretty}" is reserved — pick another name.`, slug };
  }
  const existing = opts.existingSlugs || [];
  if (existing.includes(slug) && !opts.allowReplace) {
    return {
      ok: false,
      reason: "replace",
      slug,
      pretty,
    };
  }
  return { ok: true, slug, pretty };
}
