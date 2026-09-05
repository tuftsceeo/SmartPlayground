/**
 * Tag checklist modal — Box writes cards; app only lists what's needed.
 *
 * Shown AFTER a successful send: at that point the game is on the Box and the
 * list is a genuine to-do ("go write these"). It ticks live from the Box's
 * `card_written` events while the overlay is open; the durable per-game view
 * lives in the My Box overlay.
 */

import { iconSvg } from "./icons.js";

let _live = null; // { tags, render } while the overlay is open

export function showTagChecklist({ title, subtitle, tags, written }) {
    return new Promise((resolve) => {
        const overlay = document.getElementById("tag-checklist-overlay");
        const list = document.getElementById("tag-checklist-list");
        const bars = document.getElementById("tag-checklist-bars");
        const titleEl = document.getElementById("tag-checklist-title");
        const subEl = document.getElementById("tag-checklist-subtitle");

        titleEl.textContent = title;
        subEl.textContent = subtitle || "";

        function render(counts) {
            const done = (t) => (counts && counts[t] > 0);
            const nextIdx = tags.findIndex((t) => !done(t));
            list.innerHTML = "";
            bars.innerHTML = "";
            tags.forEach((tag, i) => {
                const isDone = done(tag);
                const isNext = i === nextIdx;
                const bar = document.createElement("div");
                bar.className = "tag-bar" + (isDone ? " done" : isNext ? " next" : "");
                bars.appendChild(bar);

                const row = document.createElement("div");
                row.className = "tag-row" + (isDone ? " done" : isNext ? " next" : "");
                const iconColor = isDone ? "#22c3a6" : isNext ? "#b36b00" : "#8b859a";
                const statusHtml = isDone
                    ? iconSvg("circle-check", { size: 16 })
                    : isNext
                      ? `<span class="tag-status">next</span>`
                      : `<span class="tag-status">not yet</span>`;
                row.innerHTML =
                    `<span style="color:${iconColor};display:inline-flex">${iconSvg("nfcCard", { size: 16 })}</span>` +
                    `<span class="tag-name">${escapeHtml(tag)}</span>` +
                    statusHtml;
                list.appendChild(row);
            });
        }

        render(written || {});
        _live = { tags, render };
        overlay.classList.remove("hidden");

        function cleanup() {
            _live = null;
            document.getElementById("tag-checklist-continue").removeEventListener("click", onContinue);
            document.getElementById("tag-checklist-back")?.removeEventListener("click", onBack);
        }
        function onContinue() {
            cleanup();
            overlay.classList.add("hidden");
            resolve({ action: "continue" });
        }
        function onBack() {
            cleanup();
            overlay.classList.add("hidden");
            resolve({ action: "back" });
        }

        document.getElementById("tag-checklist-continue").addEventListener("click", onContinue);
        document.getElementById("tag-checklist-back")?.addEventListener("click", onBack);
    });
}

/** Re-tick an open checklist from a live {tagLabel: count} map. No-op when closed. */
export function updateTagChecklist(counts) {
    if (_live) _live.render(counts || {});
}

function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
