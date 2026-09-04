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
 * Push a game file and reset. Destination defaults to /flash/payload.py for
 * legacy callers; P4 passes /flash/games/<slug>.py. The box boot-scans the
 * games directory and updates index.json / active.txt on reboot.
 */
export async function pushPayload(repl, adapter, code, onProgress, meta = {}) {
  const destPath = meta.destPath || "/flash/payload.py";
  const label = meta.destLabel || destPath.split("/").pop() || "payload.py";
  onProgress?.({ current: 1, total: 1, file: label, status: "uploading" });
  await repl.enterRepl();
  await repl.enterRawRepl();
  // Ensure /flash/games exists when pushing into the library.
  if (destPath.startsWith("/flash/games/")) {
    await repl.ensureDirectory("/flash/games");
  }
  await repl.uploadFile(destPath, code);
  onProgress?.({ current: 1, total: 1, file: label, status: "uploaded" });
  await repl.exitRawRepl();
  await repl.softReset();
  const restarted = await waitForTypedMessage(adapter, 10000);
  if (!restarted) {
    return { ok: false, error: "Code uploaded, but the Box did not confirm restart." };
  }
  onProgress?.({ current: 1, total: 1, file: label, status: "done" });
  return { ok: true };
}

async function waitForTypedMessage(adapter, timeoutMs) {
  const { found } = await adapter.readUntil('"type":', timeoutMs);
  return found;
}
