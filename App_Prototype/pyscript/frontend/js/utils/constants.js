/**
 * Playground Control App - Constants
 */

export const COMMANDS = [
    { id: "play", label: "Play", bgColor: "#7eb09b", icon: "play", textColor: "white" },
    { id: "pause", label: "Pause", bgColor: "#d4a574", icon: "pause", textColor: "white" },
    { id: "win", label: "Win", bgColor: "#b084cc", icon: "trophy", textColor: "white" },
    { id: "color_game", label: "Color Game", bgColor: "#658ea9", icon: "palette", textColor: "white" },
    { id: "number_game", label: "Number Game", bgColor: "#d7a449", icon: "hash", textColor: "white" },
    { id: "off", label: "Off", bgColor: "#e98973", icon: "poweroff", textColor: "white" },
];

// Get range label for slider position (1-100)
export function getRangeLabel(position) {
    if (position === 100) return "All";
    if (position >= 84) return "Far";
    if (position >= 68) return "Distant";
    if (position >= 51) return "Close";
    if (position >= 34) return "Near";
    return "Here";
}
