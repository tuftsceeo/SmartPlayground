/**
 * manifest.js — firmware file list for Broadcast Box installer.
 * Same shape as Live_Page/WebApp2/hubCode2/manifest.js
 */

export const BOX_FILES = [
    { path: 'json_link.py', remotePath: '/flash/json_link.py' },
    { path: 'pn532.py', remotePath: '/flash/pn532.py' },
    { path: 'opcodes.py', remotePath: '/flash/opcodes.py' },
    { path: 'nfc_reader.py', remotePath: '/flash/nfc_reader.py' },
    { path: 'card_writer.py', remotePath: '/flash/card_writer.py' },
    { path: 'code_server.py', remotePath: '/flash/code_server.py' },
    { path: 'bbox_ui.py', remotePath: '/flash/bbox_ui.py' },
    { path: 'bbox_server.py', remotePath: '/flash/bbox_server.py' },
    { path: 'main.py', remotePath: '/flash/main.py' },
];

export async function loadBoxFiles(baseUrl = './BBoxFirmware/') {
    const cacheBuster = '?t=' + Date.now();
    const files = [];
    for (const fileInfo of BOX_FILES) {
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
