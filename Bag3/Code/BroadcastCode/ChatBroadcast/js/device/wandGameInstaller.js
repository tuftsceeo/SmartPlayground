/**
 * wandGameInstaller.js — push a game file straight to a wand over USB,
 * sibling to boxFirmwareInstaller.js's pushPayload(). No Box in the loop:
 * the file that would have gone to /flash/games/<slug>.py for the Box to
 * courier over ESP-NOW instead lands directly at /games/<slug>.py, which
 * is where the wand looks for a pulled game either way
 * (MockWand/lib/game_store.py).
 */

const WAND_INSTALL_TIMEOUT_MS = 25000; // wand boot is >20s (HARDWARE_PROTOCOL.md); Box allows 10s

/**
 * Read /hubtype.txt over the raw REPL and confirm it says "wand" before
 * writing anything. Cheap here (we're already at the REPL to upload), and
 * the one thing standing between "teacher picked the wrong port" and a
 * stray file on some other MicroPython board's flash. The Box path must
 * never gain a REPL probe like this -- it would stop bbox_server.py's JSON
 * loop for no reason.
 */
async function verifyIsWand(repl) {
  const code =
    "try:\n" +
    " with open('hubtype.txt') as f:\n" +
    "  print('HUBTYPE:' + f.read().strip())\n" +
    "except OSError:\n" +
    " print('HUBTYPE:<missing>')\n";
  const response = await repl.execScript(code, { timeoutMs: 5000 });
  const m = response.match(/HUBTYPE:(\S*)/);
  const found = m ? m[1] : "<unreadable>";
  if (found !== "wand") {
    throw new Error(`Not a wand (hubtype.txt says "${found}") — check you picked the right port.`);
  }
}

/**
 * @param {string} code
 * @param {{ slug: string, destLabel?: string, autoLaunch?: boolean, deviceLabel?: string }} meta
 *   `slug` is required and must already be a validated module name (see
 *   gameName.js) -- this function does not re-check it. `autoLaunch`
 *   defaults to true: the wand plays the game on its next boot via the
 *   same game_store.take_last_pulled() path a real ESP-NOW pull uses
 *   (MockWand/main.py, "Auto-launch a just-pulled game").
 */
export async function installGameOnWand(repl, adapter, code, onProgress, meta = {}) {
  const { slug, autoLaunch = true } = meta;
  if (!slug) throw new Error("installGameOnWand: meta.slug is required");
  const destPath = `/games/${slug}.py`;
  const label = meta.destLabel || `${slug}.py`;
  const who = meta.deviceLabel || "Wand";

  onProgress?.({ current: 1, total: 1, file: label, status: "uploading" });
  await repl.enterRepl();
  await repl.enterRawRepl();

  try {
    await verifyIsWand(repl);
    await repl.ensureDirectory("/games");
    await repl.uploadFile(destPath, code);
    if (autoLaunch) {
      await repl.execScript(
        `import game_store\ngame_store.set_last_pulled('${slug}')\n`,
        { timeoutMs: 5000 }
      );
    }
  } finally {
    await repl.exitRawRepl();
  }

  onProgress?.({ current: 1, total: 1, file: label, status: "uploaded" });
  await repl.softReset();

  const restarted = await waitForTypedMessage(adapter, WAND_INSTALL_TIMEOUT_MS);
  if (!restarted) {
    return { ok: false, error: `Code uploaded, but the ${who} did not confirm restart.` };
  }
  onProgress?.({ current: 1, total: 1, file: label, status: "done" });
  return { ok: true };
}

async function waitForTypedMessage(adapter, timeoutMs) {
  const { found } = await adapter.readUntil('"type":', timeoutMs);
  return found;
}
