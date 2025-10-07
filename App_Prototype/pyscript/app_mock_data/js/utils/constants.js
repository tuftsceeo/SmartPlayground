/**
 * Smart Playground Control - Application Constants
 * 
 * This module defines all constant values used throughout the application,
 * including command definitions, colors, icons, and configuration values.
 * Centralizing constants here makes the application easier to maintain
 * and allows for consistent theming and behavior.
 * 
 * Key Constants:
 * - COMMANDS: Available playground commands with styling and icons
 * - Command properties: id, label, background color, icon, text color
 * 
 * Command Types:
 * - play: Start playground activity
 * - pause: Pause current activity
 * - win: Trigger win/success state
 * - color_game: Start color-based game
 * - number_game: Start number-based game
 * - off: Turn off/reset modules
 * 
 * Usage:
 * - Import COMMANDS array for command palette generation
 * - Use consistent command IDs throughout application
 * - Colors and icons are defined here for easy theming
 * 
 */

export const COMMANDS = [
    { id: "play", label: "Play", bgColor: "#7eb09b", icon: "play", textColor: "white" },
    { id: "pause", label: "Pause", bgColor: "#d4a574", icon: "pause", textColor: "white" },
    { id: "win", label: "Win", bgColor: "#b084cc", icon: "trophy", textColor: "white" },
    { id: "color_game", label: "Color Game", bgColor: "#658ea9", icon: "palette", textColor: "white" },
    { id: "number_game", label: "Number Game", bgColor: "#d7a449", icon: "hash", textColor: "white" },
    { id: "off", label: "Off", bgColor: "#e98973", icon: "poweroff", textColor: "white" },
];

