/**
 * Playground Control App - Icon Components
 */

export function createIcon(name, className = "w-4 h-4") {
    const i = document.createElement("i");
    i.setAttribute("data-lucide", name);
    i.className = className;
    return i;
}

export function getCommandIcon(commandLabel, size = "small") {
    console.log(`getCommandIcon called with: "${commandLabel}", size: "${size}"`);

    const commands = {
        Play: { bgColor: "#7eb09b", icon: "play" },
        Pause: { bgColor: "#d4a574", icon: "pause" },
        Win: { bgColor: "#b084cc", icon: "trophy" },
        "Color Game": { bgColor: "#658ea9", icon: "palette" },
        "Number Game": { bgColor: "#d7a449", icon: "hash" },
        Off: { bgColor: "#e98973", icon: "power-off" },
    };

    const cmd = commands[commandLabel];
    console.log(`Command lookup result:`, cmd);

    if (!cmd) {
        console.warn(`No icon found for command: ${commandLabel}`);
        return null;
    }

    const div = document.createElement("div");
    const isSmall = size === "small";
    div.className = `${isSmall ? "w-8 h-8" : "w-16 h-16"} ${isSmall ? "rounded-lg" : "rounded-xl"} flex items-center justify-center flex-shrink-0`;
    div.style.backgroundColor = cmd.bgColor;

    console.log(`Creating icon for: ${cmd.icon}`);

    if (cmd.icon === "1" || cmd.icon === "2") {
        div.innerHTML = `<span class="${isSmall ? "text-lg" : "text-3xl"} font-bold text-white">${cmd.icon}</span>`;
    } else {
        const icon = createIcon(cmd.icon, `${isSmall ? "w-4 h-4" : "w-8 h-8"} text-white`);
        console.log(`Created icon element:`, icon, "Type:", typeof icon, "Is Node:", icon instanceof Node);
        div.appendChild(icon);
    }

    console.log(`Returning div:`, div, "Type:", typeof div, "Is Node:", div instanceof Node);
    return div;
}

export function getDeviceIcon(type, size = "medium") {
    const sizes = {
        small: "w-8 h-8",
        medium: "w-12 h-12",
    };

    const iconSizes = {
        small: "w-4 h-4",
        medium: "w-6 h-6",
    };

    const icons = {
        module: "smartphone",
        extension: "box",
        button: "circle-dot",
    };

    const div = document.createElement("div");
    div.className = `${sizes[size]} rounded-full flex items-center justify-center flex-shrink-0 ${type === "extension" ? "bg-gray-600" : "bg-gray-500"}`;
    div.appendChild(createIcon(icons[type], `${iconSizes[size]} text-white`));

    return div;
}

export function getSignalIcon(signal) {
    if (signal === 0) return createIcon("wifi-off", "w-4 h-4 text-gray-400");

    const container = document.createElement("div");
    container.className = "flex items-end gap-0.5";

    for (let i = 0; i < 3; i++) {
        const bar = document.createElement("div");
        bar.className = `w-1 ${i === 0 ? "h-2" : i === 1 ? "h-3" : "h-4"} rounded-sm ${i < signal ? "bg-gray-600" : "bg-gray-300"}`;
        container.appendChild(bar);
    }

    return container;
}

export function getBatteryIcon(battery) {
    const icons = {
        full: "battery-full",
        high: "battery-medium",
        medium: "battery-low",
        low: "battery",
    };

    const colors = {
        full: "text-green-700",
        high: "text-green-500",
        medium: "text-amber-600",
        low: "text-red-700",
    };

    return createIcon(icons[battery] || "battery", `w-4 h-4 ${colors[battery] || "text-gray-400"}`);
}
