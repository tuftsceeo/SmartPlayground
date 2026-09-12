/** toast.js -- lavender pill toast. */
export function showToast(message, { kind = "info", duration = 3000 } = {}) {
  const el = document.createElement("div");
  el.className = `toast toast-${kind}`;
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => {
    setTimeout(() => {
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    }, duration);
  });
}
