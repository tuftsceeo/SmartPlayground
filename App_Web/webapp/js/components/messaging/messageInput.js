/**
 * Message Input Component
 * 
 * Command input with expandable palette. Click to select command, send button to transmit.
 */

import { getCommandIcon, createIcon } from "../common/icons.js";
import { COMMANDS, getCommandLabel, getCommandById, getFilteredCommands } from "../../utils/constants.js";
import { createCommandInfoOverlay } from "../overlays/commandInfoOverlay.js";

export function createMessageInput(currentMessage, showPalette, canSend, hubConnected, onInputClick, onCommandSelect, onClearMessage, onSendMessage, flashMessageBox) {
    const container = document.createElement("div");
    container.className = "bg-white border-t border-gray-200";

    container.innerHTML = `
    <div class="flex items-center gap-2 p-3">
      <div class="flex-1 rounded-full px-4 py-2.5 flex items-center gap-2 transition-all ${
        hubConnected 
          ? 'bg-gray-200 cursor-text' 
          : 'bg-gray-100 cursor-not-allowed'
      } ${
        flashMessageBox ? 'ring-2 ring-amber-400 bg-amber-50' : ''
      }" id="messageInput">
        ${
            currentMessage
                ? `<div id="commandIcon"></div><span class="${hubConnected ? 'text-gray-900' : 'text-gray-500'} text-sm flex-1 font-medium">${getCommandLabel(currentMessage)}</span><button class="w-5 h-5 rounded-full bg-gray-300 hover:bg-gray-400 flex items-center justify-center transition-colors flex-shrink-0 ${hubConnected ? '' : 'cursor-not-allowed'}" id="clearBtn" ${hubConnected ? '' : 'disabled'}><i data-lucide="x" class="w-3 h-3 text-gray-700"></i></button>`
                : `<span class="${hubConnected ? 'text-gray-600' : 'text-gray-400'} text-sm">${hubConnected ? 'Select a command...' : 'Connect controller to send commands'}</span>`
        }
      </div>
      <button class="w-10 h-10 rounded-full flex items-center justify-center transition-all ${
          canSend 
            ? "bg-blue-400 hover:bg-blue-500 text-white" 
            : "bg-gray-300 text-gray-500 cursor-not-allowed"
      }" id="sendBtn">
        <i data-lucide="send" class="w-4 h-4"></i>
      </button>
    </div>
    <div class="command-palette transition-all duration-300 ease-out ${showPalette && hubConnected ? "max-h-80 opacity-100" : "max-h-0 opacity-0 overflow-hidden"}">
      <div class="flex flex-wrap justify-evenly gap-3 px-2 pb-3 max-h-80 overflow-y-auto" id="commands"></div>
    </div>
  `;

    // Add command icon if message selected
    if (currentMessage) {
        const iconContainer = container.querySelector("#commandIcon");
        const commandLabel = getCommandLabel(currentMessage);
        const icon = getCommandIcon(commandLabel, "small");
        if (icon) {
            iconContainer.appendChild(icon);
        }
    }

    // Event handlers
    container.querySelector("#messageInput").onclick = () => {
        if (hubConnected) {
            onInputClick();
        }
    };

    if (currentMessage) {
        container.querySelector("#clearBtn").onclick = (e) => {
            e.stopPropagation();
            if (hubConnected) {
                onClearMessage();
            }
        };
    }

    container.querySelector("#sendBtn").onclick = onSendMessage;

    // Add command buttons
    const commandsContainer = container.querySelector("#commands");
    const commandsToShow = getFilteredCommands();

    commandsToShow.forEach((command, index) => {
        // Create wrapper for button and info icon
        const wrapper = document.createElement("div");
        wrapper.className = "relative flex flex-col items-center gap-2";
        
        const btn = document.createElement("button");
        btn.className = `bg-gray-100 rounded-2xl p-3 flex-shrink-0 transition-all flex flex-col items-center gap-2 w-[88px] ${
            hubConnected ? 'hover:bg-gray-200 active:scale-95' : 'cursor-not-allowed'
        }`;
        btn.onclick = () => {
            if (hubConnected) {
                onCommandSelect(command);
            }
        };
        if (!hubConnected) {
            btn.disabled = true;
        }

        const icon = getCommandIcon(command.label, "large");

        if (icon) {
            btn.appendChild(icon);
        } else {
            console.log("No icon found for command:", command.label);
        }

        const label = document.createElement("span");
        label.className = "text-xs text-gray-600 font-medium text-center leading-tight";
        label.textContent = command.label;
        btn.appendChild(label);

        wrapper.appendChild(btn);

        // Add info icon if description exists
        if (command.description) {
            const infoBtn = document.createElement("button");
            infoBtn.className = "absolute top-1 right-1 w-5 h-5 rounded-full bg-slate-400 flex items-center justify-center transition-all hover:bg-slate-500 active:scale-95 z-10";
            
            let overlay = null;
            
            const closeOverlay = () => {
                if (overlay && document.body.contains(overlay)) {
                    document.body.removeChild(overlay);
                    overlay = null;
                }
            };
            
            infoBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                if (overlay) return;
                
                const commandIcon = getCommandIcon(command.label, "large");
                
                overlay = createCommandInfoOverlay(
                    command.label,
                    command.description,
                    commandIcon,
                    closeOverlay
                );
                
                document.body.appendChild(overlay);
                
                if (window.lucide) {
                    window.lucide.createIcons();
                }
            };
            
            const infoIcon = createIcon("info", "w-3 h-3 text-white");
            infoBtn.appendChild(infoIcon);
            wrapper.appendChild(infoBtn);
        }

        commandsContainer.appendChild(wrapper);
    });

    return container;
}