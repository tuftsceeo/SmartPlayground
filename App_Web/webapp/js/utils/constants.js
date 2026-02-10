/**
 * Application Constants - commands loaded from commands.json.
 */

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

