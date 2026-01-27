/**
 * Hub Code Manifest
 * 
 * Lists all files to upload to ESP32 to transform it into a Simple Hub
 * Files are fetched from the hubCode directory at runtime
 */

export const HUB_FILES = [
    // Core files
    { path: 'main.py', remotePath: 'main.py' },
    { path: 'controller.py', remotePath: 'controller.py' },
    { path: 'ssd1306.py', remotePath: 'ssd1306.py' },
    
    // Utility files (go in utilities/ subdirectory on ESP32)
    { path: 'utilities/utilities.py', remotePath: 'utilities/utilities.py' },
    { path: 'utilities/lights.py', remotePath: 'utilities/lights.py' },
    { path: 'utilities/i2c_bus.py', remotePath: 'utilities/i2c_bus.py' },
    { path: 'utilities/wifi.py', remotePath: 'utilities/wifi.py' },
    { path: 'utilities/now.py', remotePath: 'utilities/now.py' },
    { path: 'utilities/colors.py', remotePath: 'utilities/colors.py' },
    { path: 'utilities/lc709203f.py', remotePath: 'utilities/lc709203f.py' },
    { path: 'utilities/secrets.py', remotePath: 'utilities/secrets.py' },
];

/**
 * Load all hub files from the hubCode directory
 * @returns {Promise<Array>} Array of {path, content} objects
 */
export async function loadHubFiles() {
    const baseUrl = './hubCode/';
    const files = [];
    
    for (const fileInfo of HUB_FILES) {
        try {
            // Add cache busting to ensure we get the latest version
            const cacheBuster = `?t=${Date.now()}`;
            const response = await fetch(baseUrl + fileInfo.path + cacheBuster, {
                cache: 'no-store'
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const content = await response.text();
            files.push({
                path: fileInfo.remotePath, // Path on ESP32
                content: content,
                localPath: fileInfo.path // Path in webapp
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

