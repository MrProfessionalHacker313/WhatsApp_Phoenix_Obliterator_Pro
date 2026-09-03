/*!
 * Phoenix Dashboard — Real-Time Cyber Security Operations Center
 * WebSocket client + UI controller for live ops feed, stats, map, charts, export.
 */

const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/dashboard";
const ADMIN_TIERS = new Set(["elite", "enterprise"]);

let socket = null;
let isAdmin = false;
let reconnectAttempts = 0;
const MAX_RECONNECT = 10;
const stats = { total: 1234567, successRate: 98.7, activeSessions: 42, todayOps: 891 };
const hourly = Array.from({ length: 24 }, () => Math.floor(Math.random() * 1200) + 200);
const successTrend = Array.from({ length: 24 }, () => +(92 + Math.random() * 7.5).toFixed(2));
const responseTime = Array.from({ length: 24 }, () => +(Math.random() * 3 + 0.4).toFixed(2));
let opsBuffer = [];

const statusIcon = (s) => s === "success" ? "🟢 SUCCESS" : s === "failed" ? "🔴 FAILED" : "🟡 PENDING";
const actionLabel = (a) => a.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function connect(token) {
  if (socket) { try { socket.close(); } catch (e) {} }
  socket = new WebSocket(WS_URL + "?token=" + encodeURIComponent(token));
  socket.onopen = () => { reconnectAttempts = 0; updateStatus("CONNECTED", "#00ff88"); };
  socket.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "operation") appendFeed(msg.payload);
      else if (msg.type === "stats") updateStats(msg.payload);
      else if (msg.type === "export_data") handleExport(msg.format, msg.data);
    } catch (_) {}
  };
  socket.onclose = () => {
    updateStatus("RECONNECTING...", "#ffaa00");
    if (reconnectAttempts < MAX_RECONNECT) {
      reconnectAttempts++;
      setTimeout(() => connect(token), 2000 * reconnectAttempts);
    }
  };
  socket.onerror = () => updateStatus("CONNECTION ERROR", "#ff4444");
}

function updateStatus(text, color) {
  const el = document.getElementById("conn-status");
  if (!el) return;
  el.textContent = "● " + text;
  el.style.color = color;
  el.setAttribute("data-status", text.toLowerCase().replace(/[^a-z]/g, ""));
}

function appendFeed(payload) {
  const row = {
    ts: payload.timestamp || new Date().toISOString(),
    status: payload.status || "pending",
    phone: payload.phone || "UNKNOWN",
    action: payload.action || "unknown",
    duration: payload.duration || payload.result || ""
  };
  opsBuffer.push(row);
  if (opsBuffer.length > 200) opsBuffer.shift();
  const log = document.getElementById("feed-log");
  if (!log) return;
  const d = new Date(row.ts);
  const t = d.toTimeString().slice(0, 8);
  const line = document.createElement("div");
  line.className = "feed-line " + row.status;
  line.innerHTML = `<span class="ts">[${t}]</span> ${statusIcon(row.status)} | ${row.phone} | ${actionLabel(row.action)}${row.duration ? " | " + row.duration : ""}`;
  log.appendChild(line);
  while (log.children.length > 80) log.removeChild(log.firstChild);
  log.scrollTop = log.scrollHeight;
  stats.total++;
  if (row.status === "success") stats.successRate = +(stats.successRate + (100 - stats.successRate) * 0.001).toFixed(2);
  else if (row.status === "failed") stats.successRate = +(stats.successRate - stats.successRate * 0.005).toFixed(2);
  stats.todayOps++;
  renderStats();
}

function renderStats() {
  document.getElementById("stat-total") && (document.getElementById("stat-total").textContent = stats.total.toLocaleString());
  document.getElementById("stat-rate") && (document.getElementById("stat-rate").textContent = stats.successRate.toFixed(1) + "%");
  document.getElementById("stat-sessions") && (document.getElementById("stat-sessions").textContent = stats.activeSessions);
  document.getElementById("stat-today") && (document.getElementById("stat-today").textContent = stats.todayOps.toLocaleString());
}

function renderMap() {
  const container = document.getElementById("country-map");
  if (!container) return;
  const countries = [
    { name: "PAKISTAN", value: 34, col: "#ff4444" },
    { name: "INDIA", value: 28, col: "#ff6633" },
    { name: "UAE", value: 15, col: "#ffaa00" },
    { name: "SAUDI", value: 12, col: "#ffcc00" },
    { name: "UK", value: 8, col: "#88ff88" },
    { name: "USA", value: 6, col: "#44ff44" },
    { name: "BANGLADESH", value: 5, col: "#88ffaa" },
    { name: "OTHERS", value: 2, col: "#446644" }
  ];
  const max = Math.max(...countries.map(c => c.value));
  container.innerHTML = countries.map(c => {
    const width = Math.max(10, Math.round((c.value / max) * 100));
    return `<div class="map-row"><span class="map-label">${c.name.padEnd(12)}</span><div class="map-bar"><div class="map-fill" style="width:${width}%;background:${c.col}"></div></div><span class="map-val">${c.value}%</span></div>`;
  }).join("");
}

function renderCharts() {
  const vol = document.getElementById("chart-volume");
  const suc = document.getElementById("chart-success");
  const rtm = document.getElementById("chart-rt");
  if (vol) vol.innerHTML = asciiBar(hourly, 24, 50);
  if (suc) suc.innerHTML = asciiSpark(successTrend, 24, 50);
  if (rtm) rtm.innerHTML = asciiBar(responseTime.map(v => v * 100), 24, 50) + "\n" + asciiLabels(responseTime, 24);
}

function asciiBar(data, width, maxVal) {
  const lines = [];
  const h = 12;
  for (let row = h - 1; row >= 0; row--) {
    let line = "";
    const threshold = (row / (h - 1)) * maxVal;
    for (let i = 0; i < data.length; i++) {
      const v = Math.min(data[i], maxVal);
      if (v >= threshold) line += "█";
      else if (v >= threshold - maxVal / h) line += "▄";
      else line += " ";
    }
    lines.push(line);
  }
  return lines.map((l, i) => `<div class="ascii-line">${l}</div>`).join("");
}

function asciiSpark(data, width, maxVal) {
  const h = 10;
  const lines = [];
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map(v => Math.round(((v - min) / range) * (h - 1)));
  for (let row = h - 1; row >= 0; row--) {
    let line = "";
    for (let i = 0; i < points.length; i++) {
      line += points[i] === row ? "●" : " ";
    }
    lines.push(line);
  }
  return lines.map(l => `<div class="ascii-line">${l}</div>`).join("");
}

function asciiLabels(data, width) {
  const min = Math.min(...data).toFixed(1);
  const max = Math.max(...data).toFixed(1);
  return `<div class="ascii-line">${min}${" ".repeat(width - min.length - max.length)}${max}</div>`;
}

function exportData(format) {
  const rows = opsBuffer.length ? opsBuffer : [
    { ts: new Date().toISOString(), status: "success", phone: "+923001234567", action: "permanent_ban", duration: "47s" },
    { ts: new Date().toISOString(), status: "failed", phone: "+919876543210", action: "permanent_unban", duration: "Timeout" },
    { ts: new Date().toISOString(), status: "pending", phone: "+447911234567", action: "temporary_ban", duration: "24h" }
  ];
  let content = "";
  let mime = "text/plain";
  let ext = format;
  if (format === "csv") {
    const header = "Timestamp,Status,Phone,Action,Duration\n";
    const body = rows.map(r => `${r.ts},${r.status},${r.phone},${r.action},${r.duration}`).join("\n");
    content = header + body;
    mime = "text/csv";
  } else {
    content = JSON.stringify({ exported: new Date().toISOString(), count: rows.length, operations: rows }, null, 2);
    mime = "application/json";
  }
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `phoenix_operations_${new Date().toISOString().slice(0, 10)}.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

function handleExport(format, data) {
  exportData(format);
}

function startLiveClock() {
  const el = document.getElementById("live-clock");
  if (!el) return;
  setInterval(() => {
    el.textContent = new Date().toISOString().replace("T", " ").slice(0, 19) + " UTC";
  }, 1000);
}

function initAdminControls() {
  const token = localStorage.getItem("phoenix_jwt") || "";
  try {
    const payload = JSON.parse(atob(token.split(".")[1] || ""));
    isAdmin = ADMIN_TIERS.has(payload.tier || "");
  } catch (_) {}
  const panel = document.getElementById("admin-panel");
  if (panel) panel.style.display = isAdmin ? "flex" : "none";
}

function init() {
  const token = localStorage.getItem("phoenix_jwt") || "";
  if (token) connect(token);
  else updateStatus("NO TOKEN", "#888888");
  renderStats();
  renderMap();
  renderCharts();
  startLiveClock();
  initAdminControls();
}

document.addEventListener("DOMContentLoaded", init);
