// ─── Lucide Icons ────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (typeof lucide !== "undefined") lucide.createIcons();
});

// ─── Clock ────────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById("clockDisplay");
  if (el) el.textContent = new Date().toLocaleString("id-ID", {
    weekday: "short", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  });
}
updateClock();
setInterval(updateClock, 1000);

// ─── Sidebar toggle ───────────────────────────────────────────────────────────
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebar = document.getElementById("sidebar");
if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener("click", () => sidebar.classList.toggle("open"));
  document.addEventListener("click", e => {
    if (window.innerWidth <= 960 && !sidebar.contains(e.target) && e.target !== sidebarToggle) {
      sidebar.classList.remove("open");
    }
  });
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(msg, type = "info", duration = 3500) {
  const icons = { success: "✅", error: "❌", info: "ℹ️" };
  const c = document.getElementById("toastContainer");
  const t = document.createElement("div");
  t.className = `toast toast-${type}`;
  t.innerHTML = `<span class="toast-icon">${icons[type] || "ℹ️"}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => {
    t.style.animation = "none";
    t.style.opacity = "0";
    t.style.transform = "translateX(40px)";
    t.style.transition = "all .25s ease";
    setTimeout(() => t.remove(), 250);
  }, duration);
}

// ─── Simulate button ──────────────────────────────────────────────────────────
const btnSim = document.getElementById("btnSimulate");
if (btnSim) {
  btnSim.addEventListener("click", async () => {
    btnSim.disabled = true;
    btnSim.textContent = "⏳ ...";
    try {
      const res = await fetch("/api/simulate", { method: "POST" });
      const d = await res.json();
      if (d.ok) showToast(`⚡ Event terkirim: ${d.tag} → ${d.gateway}`, "success");
      else showToast("Simulasi gagal: " + d.reason, "error");
    } catch {
      showToast("Koneksi gagal", "error");
    } finally {
      setTimeout(() => { btnSim.disabled = false; btnSim.textContent = "⚡ Simulasi"; }, 1500);
    }
  });
}

// ─── WebSocket ────────────────────────────────────────────────────────────────
const wsDot  = document.getElementById("wsDot");
const wsLabel = document.getElementById("wsLabel");

function setWsStatus(state, label) {
  if (wsDot) wsDot.className = "ws-dot" + (state === "ok" ? " connected" : state === "err" ? " error" : "");
  if (wsLabel) wsLabel.textContent = label;
}

try {
  const socket = io({ transports: ["websocket", "polling"], reconnectionDelay: 2000 });
  socket.on("connect", () => setWsStatus("ok", "Live"));
  socket.on("disconnect", () => setWsStatus("", "Terputus"));
  socket.on("connect_error", () => setWsStatus("err", "Error"));
  socket.on("new_event", data => {
    const isIn = data.event_type === "IN";
    showToast(
      `${isIn ? "↓ IN" : "↑ OUT"} — <strong>${data.container_id}</strong> @ ${data.gateway_id}`,
      isIn ? "success" : "error", 4000
    );
    if (typeof window._onNewEvent === "function") window._onNewEvent(data);
  });
} catch {
  setWsStatus("err", "WS Error");
}
