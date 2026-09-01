/**
 * boxFirmwareInstaller.js — push payload.py via raw REPL, soft reset.
 * Waits for any JSON line with "type" after Ctrl-D (not hello specifically).
 */

import { loadBoxFiles } from "../../../BBoxFirmware/manifest.js";

export async function installBoxFirmware(repl, adapter, onProgress) {
  const files = await loadBoxFiles("../../../BBoxFirmware/");

  await repl.enterRepl();
  await repl.enterRawRepl();

  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    onProgress?.({ current: i + 1, total: files.length, file: f.localPath, status: "uploading" });
    await repl.uploadFile(f.path, f.content);
    onProgress?.({ current: i + 1, total: files.length, file: f.localPath, status: "uploaded" });
  }

  await repl.exitRawRepl();
  await repl.softReset();
  const ok = await waitForTypedMessage(adapter, 10000);
  if (!ok) {
    throw new Error(
      "Files uploaded, but the firmware did not confirm restart. Try Restart firmware, or power-cycle and reconnect."
    );
  }
}

/**
 * Push payload.py and reset. The box arms itself (AP + card-write-ready)
 * on this reboot as soon as it sees payload.py on flash -- no separate
 * "arm" round-trip from the laptop. That matters because the box has to
 * keep working after it's unplugged and carried to the playground; a
 * standing fact on flash shouldn't depend on a live serial handshake.
 * See bbox_server.py's _try_arm(), called from run() right after boot.
 */
export async function pushPayload(repl, adapter, code, onProgress) {
  onProgress?.({ current: 1, total: 1, file: "payload.py", status: "uploading" });
  await repl.enterRepl();
  await repl.enterRawRepl();
  await repl.uploadFile("/flash/payload.py", code);
  onProgress?.({ current: 1, total: 1, file: "payload.py", status: "uploaded" });
  await repl.exitRawRepl();
  await repl.softReset();
  const restarted = await waitForTypedMessage(adapter, 10000);
  if (!restarted) {
    return { ok: false, error: "Code uploaded, but the Box did not confirm restart." };
  }
  onProgress?.({ current: 1, total: 1, file: "payload.py", status: "done" });
  return { ok: true };
}

async function waitForTypedMessage(adapter, timeoutMs) {
  const { found } = await adapter.readUntil('"type":', timeoutMs);
  return found;
}
