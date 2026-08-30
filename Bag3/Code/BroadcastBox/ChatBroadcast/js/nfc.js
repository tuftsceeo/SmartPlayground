/**
 * Tag checklist modal (screen 6) — Box writes cards; app only lists what's needed.
 */

export function showTagChecklist({ title, subtitle, tags, writtenCount = 0 }) {
    return new Promise((resolve) => {
        const overlay = document.getElementById("tag-checklist-overlay");
        const list = document.getElementById("tag-checklist-list");
        const bars = document.getElementById("tag-checklist-bars");
        const titleEl = document.getElementById("tag-checklist-title");
        const subEl = document.getElementById("tag-checklist-subtitle");

        titleEl.textContent = title;
        subEl.textContent = subtitle;
        list.innerHTML = "";
        bars.innerHTML = "";

        tags.forEach((tag, i) => {
            const bar = document.createElement("div");
            bar.className = "tag-bar" + (i < writtenCount ? " done" : i === writtenCount ? " next" : "");
            bars.appendChild(bar);

            const row = document.createElement("div");
            row.className = "tag-row" + (i < writtenCount ? " done" : i === writtenCount ? " next" : "");
            const status = i < writtenCount ? "✓" : i === writtenCount ? "→ next" : "not yet";
            row.innerHTML =
                `<span class="tag-name">${escapeHtml(tag)}</span>` +
                `<span class="tag-status">${status}</span>`;
            list.appendChild(row);
        });

        overlay.classList.remove("hidden");

        function cleanup() {
            document.getElementById("tag-checklist-continue").removeEventListener("click", onContinue);
            document.getElementById("tag-checklist-back").removeEventListener("click", onBack);
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
        document.getElementById("tag-checklist-back").addEventListener("click", onBack);
    });
}

function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Parse NFC card names from chat marker or game code heuristics. */
export function deriveRequiredTags(nfcCards, code, gameName) {
    if (nfcCards && nfcCards.length > 0) {
        return nfcCards;
    }
    const src = code || "";
    const notes = src.match(/note_[a-g](?:_high)?/gi);
    if (notes && notes.length > 1) {
        return [...new Set(notes.map((t) => t.toLowerCase()))];
    }
    const recipe = ["flour", "egg", "milk", "butter", "sugar"].filter((t) =>
        new RegExp('"' + t + '"').test(src) || new RegExp("'" + t + "'").test(src)
    );
    if (recipe.length > 1) return recipe;

    if (gameName === "jumpin" || !gameName) {
        return ["jumpin"];
    }
    return [gameName];
}

export function tagCountLabel(n) {
    if (n <= 1) return null;
    return `needs ${n} NFC tags`;
}
