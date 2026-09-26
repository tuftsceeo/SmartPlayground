/**
 * manifest.js — firmware file list for the BDialEUM build (Broadcast Dial,
 * code over ESP-NOW via the EUM modem). Same shape as
 * BroadcastDial/BDialFirmware/manifest.js. Every module reachable from
 * main.py must be listed, or boot is an ImportError and a fatal JSON.
 *
 * ChatBroadcast's installer does NOT load this file: it loads the WiFi
 * Dial's manifest for any "broadcast_dial" identity. Deploy this build
 * with tools/deploy_dial.py, never with the ChatBroadcast installer.
 */

export const DIAL_FILES = [
    { path: 'json_link.py', remotePath: '/flash/json_link.py' },
    { path: 'reset_log.py', remotePath: '/flash/reset_log.py' },
    { path: 'stats_log.py', remotePath: '/flash/stats_log.py' },
    { path: 'ws1850s.py', remotePath: '/flash/ws1850s.py' },
    { path: 'card_writer.py', remotePath: '/flash/card_writer.py' },
    { path: 'eum_proto.py', remotePath: '/flash/eum_proto.py' },
    { path: 'espnow_manager.py', remotePath: '/flash/espnow_manager.py' },
    { path: 'code_sender.py', remotePath: '/flash/code_sender.py' },
    { path: 'code_link.py', remotePath: '/flash/code_link.py' },
    { path: 'dial_board.py', remotePath: '/flash/dial_board.py' },
    { path: 'dial_input.py', remotePath: '/flash/dial_input.py' },
    { path: 'dial_ui.py', remotePath: '/flash/dial_ui.py' },
    { path: 'bdial_server.py', remotePath: '/flash/bdial_server.py' },
    { path: 'main.py', remotePath: '/flash/main.py' },
];

export async function loadDialFiles(baseUrl = './BDialFirmware/') {
    const cacheBuster = '?t=' + Date.now();
    const files = [];
    for (const fileInfo of DIAL_FILES) {
        const res = await fetch(baseUrl + fileInfo.path + cacheBuster, { cache: 'no-store' });
        if (!res.ok) {
            throw new Error("couldn't fetch " + fileInfo.path + " (" + res.status + ")");
        }
        files.push({
            path: fileInfo.remotePath,
            content: await res.text(),
            localPath: fileInfo.path,
        });
    }
    return files;
}
