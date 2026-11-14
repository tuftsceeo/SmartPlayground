import { dbg, dbgWarn, dbgError } from "./debug.js";

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
    dbg("auth", `fetching encrypted key from ${ENCRYPTED_KEY_URL}`);
    try {
        const resp = await fetch(ENCRYPTED_KEY_URL);
        if (resp.ok) {
            encryptedKey = (await resp.text()).trim();
            dbg("auth", `encrypted key loaded (${encryptedKey.length} chars, base64)`);
        } else {
            dbgWarn("auth", `failed to load encrypted key: HTTP ${resp.status}`);
        }
    } catch (e) {
        dbgError("auth", `error loading encrypted key: ${e}`, e);
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

    dbg("auth", "initAuthModal() wiring unlock button + Enter key", {
        overlayFound: !!overlay,
        overlayHiddenNow: overlay?.classList.contains("hidden"),
        overlayPersistent: overlay?.dataset.persistent,
        hasEncryptedKey: !!encryptedKey,
    });

    function unlock() {
        const passphrase = passphraseInput.value.trim();
        errorEl.textContent = "";
        dbg("auth", `unlock attempt (passphrase length ${passphrase.length})`);
        if (!passphrase) {
            dbgWarn("auth", "unlock rejected: empty passphrase");
            errorEl.textContent = "Please enter the magic code.";
            return;
        }
        if (!encryptedKey) {
            dbgWarn("auth", "unlock rejected: encryptedKey not loaded yet (fetch still pending or failed)");
            errorEl.textContent = "No key configured. Contact your instructor.";
            return;
        }
        try {
            const key = xorDecrypt(encryptedKey, passphrase);
            if (!key.startsWith("sk-ant-")) {
                dbgWarn("auth", "unlock rejected: decrypted key does not look like an Anthropic key");
                errorEl.textContent = "Wrong code. Try again.";
                return;
            }
            dbg("auth", "unlock succeeded — hiding modal, dispatching app:unlocked");
            overlay.classList.add("hidden");
            document.dispatchEvent(new CustomEvent("app:unlocked"));
        } catch (e) {
            dbgError("auth", `unlock threw during decrypt: ${e}`, e);
            errorEl.textContent = "Invalid code. Try again.";
        }
    }

    unlockBtn.addEventListener("click", unlock);
    passphraseInput.addEventListener("keydown", e => { if (e.key === "Enter") unlock(); });
}
