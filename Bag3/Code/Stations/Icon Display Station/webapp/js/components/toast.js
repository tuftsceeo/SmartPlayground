/** toast.js -- from Live_Page/WebApp2's pattern: appends itself, self-destructs. */
export function showToast(message, { kind = "info", duration = 3000 } = {}) {
  const colors = {
    info: "bg-slate-800",
    error: "bg-red-700",
    success: "bg-emerald-700",
  };
  const el = document.createElement("div");
  el.className = `fixed bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-lg text-white text-sm shadow-lg ${colors[kind] || colors.info} transition-opacity duration-300`;
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => {
    setTimeout(() => {
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    }, duration);
  });
}
