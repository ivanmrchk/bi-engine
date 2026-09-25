const API_BASE = "/api";

async function loadHotServices(month) {
  const res = await fetch(`${API_BASE}/analysis/hot-services?month=${encodeURIComponent(month)}`);
  const data = await res.json();
  renderTable("hot-services-table", data.services, ["service", "job_count", "revenue"]);
}

async function loadLagging(month) {
  const res = await fetch(`${API_BASE}/analysis/lagging-locations?month=${encodeURIComponent(month)}`);
  const data = await res.json();
  renderTable("lagging-table", data.locations, ["location_id", "current_revenue", "previous_revenue", "delta"]);
}

async function loadBrief(locationId, month) {
  const out = document.getElementById("brief-output");
  out.textContent = "Generating…";
  const res = await fetch(`${API_BASE}/brief/${encodeURIComponent(locationId)}?month=${encodeURIComponent(month)}`);
  const data = await res.json();
  out.textContent = data.brief ?? JSON.stringify(data);
}

function renderTable(elId, rows, columns) {
  const el = document.getElementById(elId);
  if (!rows || !rows.length) {
    el.innerHTML = '<p class="empty">No data for this month yet.</p>';
    return;
  }
  const head = `<tr>${columns.map((c) => `<th>${c}</th>`).join("")}</tr>`;
  const body = rows
    .map((r) => `<tr>${columns.map((c) => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`)
    .join("");
  el.innerHTML = `<table>${head}${body}</table>`;
}

document.getElementById("load-btn").addEventListener("click", () => {
  const month = document.getElementById("month-input").value.trim();
  if (!month) return;
  loadHotServices(month);
  loadLagging(month);
});

document.getElementById("brief-btn").addEventListener("click", () => {
  const month = document.getElementById("month-input").value.trim();
  const locationId = document.getElementById("location-input").value.trim();
  if (!month || !locationId) return;
  loadBrief(locationId, month);
});
