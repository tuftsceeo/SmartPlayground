/**
 * Application Constants - commands loaded from commands.json.
 */

import { state } from '../state/store.js';

let commandsData = [];

try {
    const response = await fetch('./js/utils/commands.json');
    commandsData = await response.json();
    console.log('Commands loaded from JSON:', commandsData);
} catch (error) {
    console.error('Failed to load commands.json:', error);
    commandsData = [];
}

export const COMMANDS = commandsData;

export function getCommandLabel(commandId) {
    const command = COMMANDS.find(cmd => cmd.id === commandId);
    return command ? command.label : commandId;
}

export function getCommandById(commandId) {
    return COMMANDS.find(cmd => cmd.id === commandId) || null;
}

/**
 * Get filtered commands based on user settings (beta games toggle)
 * @returns {Array} Filtered array of commands
 */
export function getFilteredCommands() {
    if (state.showBetaGames) {
        // Show all commands if beta games are enabled
        return COMMANDS;
    }
    // Filter out beta commands
    return COMMANDS.filter(cmd => !cmd.beta);
}

