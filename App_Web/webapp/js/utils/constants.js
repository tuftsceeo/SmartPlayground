/**
 * Application Constants
 * 
 * Command definitions loaded from commands.json.
 * Update commands.json to add/edit commands.
 */

// Load commands from JSON configuration file
let commandsData = [];

// Fetch commands synchronously using top-level await (ES2022)
try {
    const response = await fetch('./js/utils/commands.json');
    commandsData = await response.json();
    console.log('Commands loaded from JSON:', commandsData);
} catch (error) {
    console.error('Failed to load commands.json:', error);
    // Fallback to empty array - app will still work
    commandsData = [];
}

export const COMMANDS = commandsData;

/**
 * Get command label from command ID
 * @param {string} commandId - The command ID (e.g., "Hot_cold")
 * @returns {string} - The display label (e.g., "Hot/Cold")
 */
export function getCommandLabel(commandId) {
    const command = COMMANDS.find(cmd => cmd.id === commandId);
    return command ? command.label : commandId;
}

/**
 * Get command by ID
 * @param {string} commandId - The command ID
 * @returns {object|null} - The command object or null if not found
 */
export function getCommandById(commandId) {
    return COMMANDS.find(cmd => cmd.id === commandId) || null;
}

