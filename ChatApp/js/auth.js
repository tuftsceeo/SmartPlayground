const ENCRYPTED_KEY_URL = "https://raw.githubusercontent.com/tuftsceeo/SmartPlayground/refs/heads/beta_January_2026/Bag2/Utilities/encrypted_key.txt";

let encryptedKey = "";

export function xorDecrypt(encryptedB64, passphrase) {
    const raw = atob(encryptedB64);
    let result = "";
    for (let i = 0; i < raw.length; i++) {
        result += String.fromCharCode(raw.charCodeAt(i) ^ passphrase.charCodeAt(i % passphrase.length));
    }
    return result;
}

export async function loadEncryptedKey() {
    try {
        const resp = await fetch(ENCRYPTED_KEY_URL);
        if (resp.ok) {
            encryptedKey = (await resp.text()).trim();
            console.log("Encrypted key loaded.");
        } else {
            console.log("Failed to load encrypted key: HTTP " + resp.status);
        }
    } catch (e) {
        console.log("Error loading encrypted key: " + e);
    }
}

export function getApiKey(passphrase) {
    if (!passphrase || !encryptedKey) return null;
    try {
        const key = xorDecrypt(encryptedKey, passphrase);
        return key.startsWith("sk-ant-") ? key : null;
    } catch {
        return null;
    }
}

export function hasEncryptedKey() {
    return !!encryptedKey;
}

export function initAuthModal() {
    const overlay = document.getElementById("modal-overlay");
    const unlockBtn = document.getElementById("btn-modal-unlock");
    const passphraseInput = document.getElementById("modal-passphrase");
    const errorEl = document.getElementById("modal-error");
    const hiddenPassphrase = document.getElementById("passphrase");

    function unlock() {
        const passphrase = passphraseInput.value.trim();
        errorEl.textContent = "";
        if (!passphrase) { errorEl.textContent = "Please enter the magic code."; return; }
        if (!encryptedKey) { errorEl.textContent = "No key configured. Contact your instructor."; return; }
        try {
            const key = xorDecrypt(encryptedKey, passphrase);
            if (!key.startsWith("sk-ant-")) { errorEl.textContent = "Wrong code. Try again."; return; }
            hiddenPassphrase.value = passphrase;
            overlay.classList.add("hidden");
            document.dispatchEvent(new CustomEvent("app:unlocked"));
        } catch {
            errorEl.textContent = "Invalid code. Try again.";
        }
    }

    unlockBtn.addEventListener("click", unlock);
    passphraseInput.addEventListener("keydown", e => { if (e.key === "Enter") unlock(); });
}
