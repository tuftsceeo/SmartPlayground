/**
 * Text for a Box/Dial `pull` event: one finished ESP-NOW transfer of a game
 * to a wand. Firmware shape (bdial_server.py `_emit_pull`):
 *   {"type":"pull","slug","role":"wand","wand":<mac>,"ok":bool,"ms","why"}
 * Any field may be null.
 * @returns {{msg: string, isError: boolean}}
 */
export function formatPullEvent(obj, gameName = null) {
  const who = obj?.wand ? `Wand ${obj.wand}` : "A wand";
  const game = gameName || obj?.slug || "a game";
  if (obj?.ok) {
    const ms = Number.isFinite(obj?.ms) ? ` in ${obj.ms} ms` : "";
    return { msg: `${who} got ${game}${ms}`, isError: false };
  }
  const why = obj?.why ? `: ${obj.why}` : "";
  return { msg: `${who} could not get ${game}${why}`, isError: true };
}
