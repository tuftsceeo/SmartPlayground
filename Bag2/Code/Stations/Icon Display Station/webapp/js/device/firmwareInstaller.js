/**
 * firmwareInstaller.js -- upload icon_matrix.py / json_link.py /
 * icon_store.py / icon_server.py / main.py onto the device via raw REPL,
 * then reset and wait for the JSON `hello`. See the plan §Mode switching.
 */

const FIRMWARE_FILES = ["icon_matrix.py", "json_link.py", "icon_store.py", "icon_server.py", "main.py"];

/** Fetch the five firmware source files from the station folder (one level up from webapp/). */
export async function loadFirmwareFiles() {
  const files = [];
  for (const name of FIRMWARE_FILES) {
    const res = await fetch(`../${name}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`couldn't fetch ${name} (${res.status}) -- is this served from the station folder?`);
    files.push({ path: name, content: await res.text() });
  }
  return files;
}

/**
 * @param {import('./replController.js').ReplController} repl
 * @param {import('./serialAdapter.js').SerialAdapter} adapter
 * @param {(progress: {current, total, file, status}) => void} [onProgress]
 */
export async function installFirmware(repl, adapter, onProgress) {
  const files = await loadFirmwareFiles();

  await repl.enterRepl();
  await repl.enterRawRepl();

  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    onProgress?.({ current: i + 1, total: files.length, file: f.path, status: "uploading" });
    await repl.uploadFile(f.path, f.content);
    onProgress?.({ current: i + 1, total: files.length, file: f.path, status: "uploaded" });
  }

  // Leave raw REPL, then SOFT reset (Ctrl-D at the friendly prompt), which
  // re-runs boot.py + main.py in place.
  //
  // NOT machine.reset(): a hard reset re-enumerates USB on this board, which
  // destroys the Web Serial port the browser is holding, so the freshly
  // booted firmware's hello can never arrive and the only recovery is a
  // physical power cycle. Observed exactly that -- upload succeeded, then an
  // 8s wait for hello timed out with the port already dead. Ctrl-D restarts
  // the program without touching the USB device.
  await repl.exitRawRepl();
  await repl.softReset();

  // Wait for the fresh boot's JSON hello rather than a fixed delay.
  const { found, text } = await adapter.readUntil('"type":"hello"', 10000);
  if (!found) {
    throw new Error(
      "Files uploaded, but the firmware did not announce itself after a soft reset. " +
        "Try 'Restart firmware'; if that is also silent, power-cycle the board and reconnect."
    );
  }
  return text;
}
