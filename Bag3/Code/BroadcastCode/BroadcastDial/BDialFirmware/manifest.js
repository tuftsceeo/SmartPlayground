/**
 * manifest.js — firmware file list for Broadcast Dial installer.
 * Same shape as BBoxFirmware/manifest.js. Every module reachable from
 * main.py must be listed, or boot is an ImportError and a fatal JSON.
 */

export const DIAL_FILES = [
    { path: 'json_link.py', remotePath: '/flash/json_link.py' },
    { path: 'reset_log.py', remotePath: '/flash/reset_log.py' },
    { path: 'stats_log.py', remotePath: '/flash/stats_log.py' },
    { path: 'ws1850s.py', remotePath: '/flash/ws1850s.py' },
    { path: 'card_writer.py', remotePath: '/flash/card_writer.py' },
    { path: 'code_link.py', remotePath: '/flash/code_link.py' },
    { path: 'code_sender.py', remotePath: '/flash/code_sender.py' },
    { path: 'dial_board.py', remotePath: '/flash/dial_board.py' },
    { path: 'dial_input.py', remotePath: '/flash/dial_input.py' },
    { path: 'text_entry.py', remotePath: '/flash/text_entry.py' },
    { path: 'station.py', remotePath: '/flash/station.py' },
    { path: 'station_ui.py', remotePath: '/flash/station_ui.py' },
    { path: 'kb_rings.json', remotePath: '/flash/kb_rings.json' },
    { path: 'kb_letters.bin', remotePath: '/flash/kb_letters.bin' },
    { path: 'station_fonts.py', remotePath: '/flash/station_fonts.py' },
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
            // .bin files (the keyboard ring image) are bytes, not text.
            content: fileInfo.path.endsWith('.bin')
                ? new Uint8Array(await res.arrayBuffer())
                : await res.text(),
            localPath: fileInfo.path,
        });
    }
    return files;
}
