/**
 * nfcStationLink.js — JSON-line link to the NFC Station
 * (Bag3/Code/Stations/NFC Station/station.py). Same wire protocol as the
 * Box, so it reuses BboxLink's framing and id correlation. Kept out of
 * bboxDeviceLink.js's EXPECTED_DEVICES so the station is never offered
 * Box firmware.
 *
 * Station replies: {"type":"ok","id":N,"cmd":"catalog.set","groups":G}, or
 * json_link.py's {"type":"error","code":"cmd_failed","cmd","id","msg"}.
 * Events: card_read {uid,type,text}, card_written {uid,text},
 * write_failed {uid,text}.
 */

import { BboxLink } from "./bboxLink.js";
import { buildHardwareReqs } from "../hardware.js";
import { slugify } from "../gameName.js";

export const STATION_EVENTS = ["card_read", "card_written", "write_failed"];

/**
 * {slug: {name, tags}} from saved-game entries (library.js shape). Tags come
 * from buildHardwareReqs, as for a Box send. The list is newest-first, so the
 * first entry for a slug wins.
 */
export function buildCatalogIndex(games) {
  const index = {};
  for (const g of games || []) {
    if (!g) continue;
    const name = g.name || "";
    const slug = slugify(name);
    if (!slug || index[slug]) continue;
    const { tags } = buildHardwareReqs({
      code: g.code || "",
      gameName: name,
      declared: g.requiredTags,
    });
    index[slug] = { name, tags };
  }
  return index;
}

export function buildCatalogSetCommand(games) {
  return { cmd: "catalog.set", index: buildCatalogIndex(games) };
}

/**
 * Interpret a reply to catalog.set. Returns {ok:true, groups} or
 * {ok:false, code, msg}.
 */
export function parseCatalogReply(obj) {
  if (obj && obj.type === "ok" && obj.cmd === "catalog.set") {
    return { ok: true, groups: obj.groups };
  }
  if (obj && obj.type === "error") {
    return { ok: false, code: obj.code || "error", msg: obj.msg || "" };
  }
  return { ok: false, code: "unexpected_reply", msg: JSON.stringify(obj) };
}

export class NfcStationLink extends BboxLink {
  constructor(adapter) {
    super(adapter);
    this.capabilities = { nfcStation: true };
  }

  /** Subscribe to card_read / card_written / write_failed; returns an unsubscribe. */
  onCardEvent(cb) {
    const offs = STATION_EVENTS.map((t) => this.on(t, cb));
    return () => offs.forEach((off) => off());
  }

  /**
   * Push the saved-games catalog. Resolves with parseCatalogReply's result;
   * a cmd_failed reply resolves {ok:false,...}. Timeouts and a stopped link
   * reject.
   */
  async pushCatalog(games, { timeoutMs = 8000 } = {}) {
    const cmd = buildCatalogSetCommand(games);
    try {
      return parseCatalogReply(await this.send(cmd, { timeoutMs }));
    } catch (e) {
      // BboxLink.send rejects error replies as "<code>: <msg>".
      const m = /^(\w+): ?(.*)$/s.exec(e.message || "");
      if (m) return { ok: false, code: m[1], msg: m[2] };
      throw e;
    }
  }
}
