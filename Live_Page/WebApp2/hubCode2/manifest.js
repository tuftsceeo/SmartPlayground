/**
 * Hub2 Code Manifest
 *
 * Lists all files to upload to ESP32-C6 to transform it into a Wand Hub (Hub2).
 * Files are fetched from the hubCode2 directory at runtime.
 */

export const HUB_FILES = [
    { path: 'main.py', remotePath: 'main.py' },
    { path: 'espnow_manager.py', remotePath: 'espnow_manager.py' },
    { path: 'game_tags.py', remotePath: 'game_tags.py' },
    { path: 'ssd1306.py', remotePath: 'ssd1306.py' },
];

/**
 * Load all hub files from the hubCode2 directory.
 * @returns {Promise<Array>} Array of {path, content} objects
 */
export async function loadHubFiles() {
    const baseUrl = './hubCode2/';
    const files = [];

    for (const fileInfo of HUB_FILES) {
        try {
            const cacheBuster = `?t=${Date.now()}`;
            const response = await fetch(baseUrl + fileInfo.path + cacheBuster, {
                cache: 'no-store'
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const content = await response.text();
            files.push({
                path: fileInfo.remotePath,
                content: content,
                localPath: fileInfo.path
            });
            console.log(`✓ Loaded ${fileInfo.path} (${content.length} bytes)`);
        } catch (error) {
            console.error(`✗ Failed to load ${fileInfo.path}:`, error);
            throw new Error(`Failed to load hub file: ${fileInfo.path}`);
        }
    }

    return files;
}

export default { HUB_FILES, loadHubFiles };
