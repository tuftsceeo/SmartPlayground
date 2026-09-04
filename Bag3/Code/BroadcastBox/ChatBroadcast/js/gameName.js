/**
 * gameName.js — slugify + reserved/duplicate validation for Broadcast Box games.
 * Pure functions; no DOM. Used by the send-confirm flow (P4).
 */

import { EXAMPLES } from "./examples.js";

export const SLUG_MAX = 16;

/** Reserved slugs: example ids + protocol / firmware names. */
export const RESERVED_SLUGS = new Set([
  ...EXAMPLES.map((e) => e.id),
  "sound",
  "getcode",
  "DONE",
  "done",
  "payload",
  "main",
]);

/**
 * Lowercase, spaces→hyphens, drop anything outside [a-z0-9-], collapse
 * repeats, cap SLUG_MAX chars.
 */
export function slugify(name) {
  if (!name || typeof name !== "string") return "";
  let s = name
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  if (s.length > SLUG_MAX) s = s.slice(0, SLUG_MAX).replace(/-$/, "");
  return s;
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
