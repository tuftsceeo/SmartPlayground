/**
 * Hub Connection Bar Component
 * Displays BLE connection status at the top of the screen
 */

export function createHubConnectionBar(isConnected, deviceName, onConnect, onDisconnect) {
    const bar = document.createElement("div");
    bar.className = `px-4 py-2 flex items-center gap-3 ${isConnected ? "bg-green-50 border-b border-green-200" : "bg-yellow-50 border-b border-yellow-200"}`;

    bar.innerHTML = `
        <div class="flex-1 flex items-center gap-2">
            <div class="w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-yellow-500"}"></div>
            <span class="text-xs font-medium ${isConnected ? "text-green-700" : "text-yellow-700"}">
                ${isConnected ? `Hub: ${deviceName}` : "Hub Disconnected"}
            </span>
        </div>
        <button id="hubConnectBtn" class="text-xs px-3 py-1 rounded-full ${
            isConnected ? "bg-red-100 text-red-700 hover:bg-red-200" : "bg-blue-500 text-white hover:bg-blue-600"
        } transition-colors">
            ${isConnected ? "Disconnect" : "Connect Hub"}
        </button>
    `;

    // Event handler
    bar.querySelector("#hubConnectBtn").onclick = isConnected ? onDisconnect : onConnect;

    return bar;
}
