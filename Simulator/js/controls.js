/**
 * Simulator control panel: button, tilt pad, shake, jump, battery,
 * ambient lux, NFC tags, teacher stop / start_game.
 */

export function createControls(container, handlers = {}) {
  const root = container;
  root.classList.add("wand-controls");
  root.innerHTML = `
    <div class="ctrl-row">
      <button type="button" data-act="button" class="ctrl-btn">Button</button>
      <button type="button" data-act="jump" class="ctrl-btn">Jump</button>
      <button type="button" data-act="stop" class="ctrl-btn">Teacher stop</button>
      <button type="button" data-act="start_game" class="ctrl-btn">start_game</button>
      <button type="button" data-act="mute" class="ctrl-btn" aria-pressed="false">🔊 Mute</button>
    </div>
    <div class="ctrl-row">
      <label>Shake <input type="range" data-act="shake" min="0" max="100" value="0"></label>
      <label>Battery <input type="range" data-act="battery" min="0" max="100" value="85"></label>
      <label>Ambient lux <input type="range" data-act="lux" min="10" max="20000" value="500"></label>
    </div>
    <div class="ctrl-row">
      <div class="tilt-pad" data-act="tilt" title="Tilt pad">
        <div class="tilt-knob"></div>
      </div>
      <div class="nfc-tags" data-act="nfc-tags"></div>
    </div>
  `;

  const btn = root.querySelector('[data-act="button"]');
  const shake = root.querySelector('[data-act="shake"]');
  const battery = root.querySelector('[data-act="battery"]');
  const lux = root.querySelector('[data-act="lux"]');
  const tilt = root.querySelector('[data-act="tilt"]');
  const knob = tilt.querySelector(".tilt-knob");
  const nfcBox = root.querySelector('[data-act="nfc-tags"]');

  let tilting = false;

  function setKnob(nx, ny) {
    knob.style.left = `${50 + nx * 40}%`;
    knob.style.top = `${50 + ny * 40}%`;
  }
  setKnob(0, 0);

  btn.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    btn.classList.add("down");
    handlers.onButton?.(true);
  });
  const releaseBtn = () => {
    btn.classList.remove("down");
    handlers.onButton?.(false);
  };
  btn.addEventListener("pointerup", releaseBtn);
  btn.addEventListener("pointerleave", releaseBtn);
  btn.addEventListener("pointercancel", releaseBtn);

  root.querySelector('[data-act="jump"]').addEventListener("click", () => {
    handlers.onJump?.();
  });
  root.querySelector('[data-act="stop"]').addEventListener("click", () => {
    handlers.onEnow?.("stop");
  });
  root.querySelector('[data-act="start_game"]').addEventListener("click", () => {
    handlers.onEnow?.("start_game");
  });

  const muteBtn = root.querySelector('[data-act="mute"]');
  let muted = false;
  function applyMuteVisual() {
    muteBtn.classList.toggle("down", muted);
    muteBtn.setAttribute("aria-pressed", String(muted));
    muteBtn.textContent = muted ? "🔇 Muted" : "🔊 Mute";
  }
  muteBtn.addEventListener("click", () => {
    muted = !muted;
    applyMuteVisual();
    handlers.onMute?.(muted);
  });
  function setMuted(v) {
    muted = !!v;
    applyMuteVisual();
  }

  shake.addEventListener("input", () => {
    const v = Number(shake.value) / 100;
    if (v <= 0) handlers.onShake?.(false, 0);
    else handlers.onShake?.(true, v);
  });

  battery.addEventListener("input", () => {
    handlers.onBattery?.(Number(battery.value));
  });
  lux.addEventListener("input", () => {
    handlers.onLux?.(Number(lux.value));
  });

  function tiltFromEvent(e) {
    const rect = tilt.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    const nx = Math.max(-1, Math.min(1, x));
    const ny = Math.max(-1, Math.min(1, y));
    setKnob(nx, ny);
    handlers.onTilt?.(nx, ny);
  }

  tilt.addEventListener("pointerdown", (e) => {
    tilting = true;
    tilt.setPointerCapture(e.pointerId);
    tiltFromEvent(e);
  });
  tilt.addEventListener("pointermove", (e) => {
    if (tilting) tiltFromEvent(e);
  });
  tilt.addEventListener("pointerup", () => { tilting = false; });
  tilt.addEventListener("pointercancel", () => { tilting = false; });

  function setNfcTags(commands) {
    nfcBox.innerHTML = "";
    const tags = Array.from(commands || []);
    if (!tags.length) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ctrl-btn";
      b.textContent = "Exit tag";
      b.addEventListener("click", () => handlers.onNfc?.("stop"));
      nfcBox.appendChild(b);
      return;
    }
    for (const cmd of tags) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ctrl-btn";
      b.textContent = cmd;
      b.addEventListener("click", () => handlers.onNfc?.(cmd));
      nfcBox.appendChild(b);
    }
  }

  return { setNfcTags, setMuted, root };
}
