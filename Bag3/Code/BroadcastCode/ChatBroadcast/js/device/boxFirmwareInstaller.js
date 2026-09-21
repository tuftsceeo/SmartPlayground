/**
 * boxFirmwareInstaller.js — push payload.py via raw REPL, soft reset.
 * Waits for any JSON line with "type" after Ctrl-D (not identity specifically).
 *
 * Firmware manifest is loaded lazily so the chat UI can boot when BBoxFirmware
 * is not on the static server path (e.g. serving ChatBroadcast alone).
 * Dial vs Box is chosen from the link's stored identity; defaults to Box.
 */

async function loadFirmwareFiles(device) {
  if (device === "broadcast_dial") {
    // ChatBroadcast lives under BroadcastBox/; Dial firmware is a sibling tree.
    const { loadDialFiles } = await import(
      "../../../../BroadcastDial/BDialFirmware/manifest.js"
    );
    return loadDialFiles("../../../../BroadcastDial/BDialFirmware/");
  }
  const { loadBoxFiles } = await import("../../../BBoxFirmware/manifest.js");
  return loadBoxFiles("../../../BBoxFirmware/");
}

export async function installBoxFirmware(repl, adapter, onProgress, device = null) {
  const files = await loadFirmwareFiles(device || "broadcast_box");
  // Only the file manifest needs a hard default (something has to be
  // flashed) -- the display label stays generic when the device type
  // genuinely isn't known yet, rather than guessing "Box".
  const label = device === "broadcast_dial" ? "Dial" : device === "broadcast_box" ? "Box" : "device";

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
      `Files uploaded, but the ${label} firmware did not confirm restart. Try Restart firmware, or power-cycle and reconnect.`
    );
  }
}

/**
 * Push a game file and reset. Destination defaults to /flash/payload.py for
 * legacy callers; P4 passes /flash/games/<slug>.py. The box boot-scans the
 * games directory and updates index.json / active.txt on reboot.
 *
 * When meta.tags is a non-empty array it is written beside the game as
 * <slug>.tags.json, in the same raw-REPL session so it costs no extra reset.
 * The Box reads that file at boot to build its writable-tag menu, so a
 * missing one leaves a game whose cards cannot be written — the write is not
 * swallowed.
 */
export async function pushPayload(repl, adapter, code, onProgress, meta = {}) {
  const destPath = meta.destPath || "/flash/payload.py";
  const label = meta.destLabel || destPath.split("/").pop() || "payload.py";
  // A multi-device game is several files -- the wand's, the display's, and
  // the display's named icons. All of them go in ONE raw-REPL session so the
  // whole game costs a single reset.
  const extras = Array.isArray(meta.extraFiles) ? meta.extraFiles : [];
  const total = 1 + extras.length;
  onProgress?.({ current: 1, total, file: label, status: "uploading" });
  await repl.enterRepl();
  await repl.enterRawRepl();
  // Ensure /flash/games exists when pushing into the library.
  if (destPath.startsWith("/flash/games/")) {
    await repl.ensureDirectory("/flash/games");
  }
  // uploadFile() throws if the device doesn't echo "OK" -- reaching the
  // line after it IS the device's confirmation that the file is written.
  // That is the real "receipt confirmed" moment; everything below is a
  // best-effort reboot, not a condition of success.
  await repl.uploadFile(destPath, code);
  if (Array.isArray(meta.tags) && meta.tags.length) {
    const tagsPath = destPath.replace(/\.py$/, "") + ".tags.json";
    await repl.uploadFile(tagsPath, JSON.stringify(meta.tags));
  }
  let done = 1;
  for (const extra of extras) {
    if (!extra?.path || extra.content === undefined) continue;
    const dir = extra.path.slice(0, extra.path.lastIndexOf("/"));
    if (dir && dir !== "/flash") await repl.ensureDirectory(dir);
    done++;
    const name = extra.path.split("/").pop();
    onProgress?.({ current: done, total, file: name, status: "uploading" });
    await repl.uploadFile(extra.path, extra.content);
  }
  onProgress?.({ current: total, total, file: label, status: "uploaded" });
  // Confirmed on hardware (both Box and Dial): exitRawRepl()+softReset()'s
  // Ctrl-D reliably reboots the board's native USB CDC, which drops the
  // serial connection before any post-reset message can arrive -- every
  // time, not as a rare edge case. Treating that expected drop as a send
  // failure was reporting real, completed sends (the files ARE on flash) as
  // errors. So the reboot is now fire-and-forget: any error here (write
  // failing because the port already died under it, etc.) is logged, not
  // thrown, and never turns a completed write into a reported failure.
  try {
    await repl.exitRawRepl();
    await repl.softReset();
  } catch (e) {
    console.warn(`pushPayload: reset step raised (expected on reboot): ${e.message}`);
  }
  // Best-effort only, per the above -- if the device is still attached and
  // happens to answer quickly, `restarted` says so, but nothing below
  // depends on it.
  const restarted = await waitForTypedMessage(adapter, 3000).catch(() => false);
  onProgress?.({ current: total, total, file: label, status: "done" });
  return { ok: true, restarted };
}

async function waitForTypedMessage(adapter, timeoutMs) {
  const { found } = await adapter.readUntil('"type":', timeoutMs);
  return found;
}
