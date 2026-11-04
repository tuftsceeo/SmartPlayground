export function setStatus(connected) {
    const dot = document.getElementById("serial-status");
    const txt = document.getElementById("status-text");
    const btn = document.getElementById("btn-connect");
    const uploadBtn = document.getElementById("btn-upload");

    if (connected) {
        dot.classList.add("connected");
        txt.textContent = "Connected";
        btn.textContent = "Disconnect";
        btn.classList.add("on");
        uploadBtn.disabled = false;
    } else {
        dot.classList.remove("connected");
        txt.textContent = "Disconnected";
        btn.textContent = "Connect";
        btn.classList.remove("on");
        uploadBtn.disabled = true;
    }
}

export function showStop(show) {
    document.getElementById("btn-send").style.display = show ? "none" : "block";
    document.getElementById("btn-stop").style.display = show ? "block" : "none";
}

export function initResizer() {
    let resizing = false;
    document.getElementById("resizer").addEventListener("mousedown", () => {
        resizing = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });
    document.addEventListener("mousemove", e => {
        if (!resizing) return;
        const layout = document.getElementById("main-layout");
        const left = document.getElementById("left-panel");
        const rect = layout.getBoundingClientRect();
        let pct = ((e.clientX - rect.left) / rect.width) * 100;
        pct = Math.max(25, Math.min(75, pct));
        left.style.width = `${pct}%`;
    });
    document.addEventListener("mouseup", () => {
        if (resizing) {
            resizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}
