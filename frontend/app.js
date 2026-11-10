const API = "/api";

async function fetchJSON(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function $(id) { return document.getElementById(id); }

function badge(text, cls) {
  return `<span class="badge ${cls}">${text}</span>`;
}

// Navigation
document.querySelectorAll("#nav .nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#nav .nav-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));
    $(`view-${btn.dataset.view}`).classList.remove("hidden");
    if (btn.dataset.view === "dashboard") loadDashboard();
    if (btn.dataset.view === "routes") loadCapacity();
    if (btn.dataset.view === "students") loadStudents();
    if (btn.dataset.view === "assignments") loadAssignments();
    if (btn.dataset.view === "exceptions") loadExceptions();
    if (btn.dataset.view === "attendance") loadAttendance();
    if (btn.dataset.view === "notifications") loadNotifications();
  });
});

// Attendance filter buttons
document.querySelectorAll("#view-attendance .nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#view-attendance .nav-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadAttendance(btn.dataset.status || null);
  });
});

// Student search
const searchEl = $("student-search");
if (searchEl) {
  let timer;
  searchEl.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(loadStudents, 300);
  });
}

let capChart, issueChart;

async function loadDashboard() {
  const stats = await fetchJSON("/stats");
  const cards = [
    { label: "Students", value: stats.student, color: "text-indigo-600" },
    { label: "Active Routes", value: stats.route, color: "text-blue-600" },
    { label: "Assignments", value: stats.assignment, color: "text-emerald-600" },
    { label: "Buses", value: stats.bus, color: "text-slate-700" },
    { label: "Capacity Exceeded", value: stats.capacity_exceeded, color: "text-amber-600" },
    { label: "Incompatible", value: stats.incompatible_assignments, color: "text-red-600" },
    { label: "Missed Pickups", value: stats.missed_pickups, color: "text-orange-600" },
    { label: "High-Severity Issues", value: stats.high_severity_issues, color: "text-rose-600" },
  ];
  $("stats-cards").innerHTML = cards.map(c => `
    <div class="card p-4">
      <div class="stat-label">${c.label}</div>
      <div class="stat-value ${c.color}">${Number(c.value).toLocaleString()}</div>
    </div>
  `).join("");

  // Capacity chart
  const cap = await fetchJSON("/capacity_overview");
  const top = cap.slice(0, 12);
  if (capChart) capChart.destroy();
  capChart = new Chart($("capChart"), {
    type: "bar",
    data: {
      labels: top.map(r => r.route_name || r.route_id),
      datasets: [{
        label: "Load",
        data: top.map(r => r.load),
        backgroundColor: top.map(r => r.over_capacity ? "#f87171" : "#818cf8")
      }, {
        label: "Capacity",
        data: top.map(r => r.effective_cap),
        backgroundColor: "#e2e8f0"
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
      scales: { x: { ticks: { maxRotation: 45, font: { size: 10 } } } }
    }
  });

  // Issue severity
  const gt = await fetchJSON("/exceptions?limit=500");
  const sev = { high: 0, medium: 0, low: 0 };
  gt.forEach(g => { sev[g.severity] = (sev[g.severity] || 0) + 1; });
  if (issueChart) issueChart.destroy();
  issueChart = new Chart($("issueChart"), {
    type: "doughnut",
    data: {
      labels: Object.keys(sev),
      datasets: [{ data: Object.values(sev), backgroundColor: ["#f43f5e", "#f59e0b", "#94a3b8"] }]
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } }
  });
}

async function loadCapacity() {
  const rows = await fetchJSON("/capacity_overview");
  const tbody = $("capacity-table").querySelector("tbody");
  tbody.innerHTML = rows.map(r => {
    const util = r.effective_cap ? Math.round(100 * r.load / r.effective_cap) : 0;
    const status = r.over_capacity
      ? badge("OVER", "badge-red")
      : util > 90 ? badge("High", "badge-amber") : badge("OK", "badge-green");
    return `<tr>
      <td style="font-weight:500;color:#4f46e5">${r.route_name || r.route_id}</td>
      <td>${r.bus_id}</td>
      <td>${r.load}</td>
      <td>${r.effective_cap}</td>
      <td>${util}%</td>
      <td>${status}</td>
    </tr>`;
  }).join("");
}

async function loadStudents() {
  const q = ($("student-search") && $("student-search").value.trim()) || "";
  const rows = await fetchJSON(`/students?limit=100&q=${encodeURIComponent(q)}`);
  $("students-table").querySelector("tbody").innerHTML = rows.map(s => `
    <tr>
      <td style="font-family:monospace;font-size:0.75rem">${s.student_id}</td>
      <td>${s.first_name} ${s.last_name}</td>
      <td>${s.grade}</td>
      <td>${s.accessibility_needs === "none" ? "—" : badge(s.accessibility_needs, "badge-blue")}</td>
      <td style="font-size:0.75rem">${s.address_zone_id}</td>
      <td>${s.is_active ? badge("Active", "badge-green") : badge("Inactive", "badge-slate")}</td>
    </tr>
  `).join("") || `<tr><td colspan="6" class="empty">No students found</td></tr>`;
}

async function loadAssignments() {
  const rows = await fetchJSON("/assignments?limit=80");
  $("assignments-table").querySelector("tbody").innerHTML = rows.map(a => `
    <tr>
      <td style="font-family:monospace;font-size:0.75rem">${a.assignment_id}</td>
      <td>${a.first_name} ${a.last_name}<div style="font-size:0.75rem;color:#64748b">${a.student_id}</div></td>
      <td>${a.grade}</td>
      <td>${a.accessibility_needs === "none" ? "—" : badge(a.accessibility_needs, "badge-blue")}</td>
      <td>${a.route_name || a.route_id}</td>
      <td style="font-size:0.75rem">${a.stop_name || a.stop_id}</td>
      <td>${a.is_compatible ? badge("Yes", "badge-green") : badge("No", "badge-red")}</td>
      <td style="font-size:0.75rem;color:#64748b">${a.notes || "—"}</td>
    </tr>
  `).join("");
}

async function loadExceptions() {
  const rows = await fetchJSON("/exceptions?limit=100");
  $("exceptions-table").querySelector("tbody").innerHTML = rows.map(g => {
    const sev = g.severity === "high" ? "badge-red" : g.severity === "medium" ? "badge-amber" : "badge-slate";
    return `<tr>
      <td>${g.entity_type}</td>
      <td style="font-family:monospace;font-size:0.75rem">${g.entity_id}</td>
      <td style="font-weight:500">${g.issue_type}</td>
      <td style="font-size:0.875rem">${g.description}</td>
      <td style="font-size:0.875rem;color:#475569">${g.expected_decision}</td>
      <td>${badge(g.severity, sev)}</td>
    </tr>`;
  }).join("");
}

async function loadAttendance(status) {
  const path = status ? `/attendance?status=${status}&limit=80` : "/attendance?limit=80";
  const rows = await fetchJSON(path);
  const color = { present: "badge-green", late: "badge-amber", missed_pickup: "badge-red", absent: "badge-slate" };
  $("attendance-table").querySelector("tbody").innerHTML = rows.map(e => `
    <tr>
      <td style="font-family:monospace;font-size:0.75rem">${e.event_id}</td>
      <td style="font-family:monospace;font-size:0.75rem">${e.student_id}</td>
      <td>${e.event_date}</td>
      <td>${badge(e.status, color[e.status] || "badge-slate")}</td>
      <td style="font-size:0.75rem;color:#64748b">${e.notes || e.recorded_at || "—"}</td>
    </tr>
  `).join("") || `<tr><td colspan="5" class="empty">No events</td></tr>`;
}

async function loadNotifications() {
  const rows = await fetchJSON("/notifications?limit=80");
  $("notifications-table").querySelector("tbody").innerHTML = rows.map(n => `
    <tr>
      <td style="font-family:monospace;font-size:0.75rem">${n.notification_id}</td>
      <td style="font-family:monospace;font-size:0.75rem">${n.student_id}</td>
      <td style="font-size:0.75rem">${n.contact_id || "—"}</td>
      <td>${n.event_type}</td>
      <td style="font-size:0.875rem;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${n.message || "—"}</td>
      <td style="font-size:0.75rem">${n.sent_at || "—"}</td>
      <td>${n.delivery_status === "sent" ? badge("sent", "badge-green") : badge(n.delivery_status || "unknown", "badge-red")}</td>
    </tr>
  `).join("");
}

// Initial load
loadDashboard().catch(err => console.error("Dashboard load failed:", err));

// Operational workflow actions (server-side validation is authoritative).
async function postJSON(path, body) {
  const res = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok) throw new Error((data.errors || [data.error || "Request failed"]).join(", "));
  return data;
}
function showOperationResult(data) {
  $("operation-result").textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}
async function loadOperations() {
  const [events, disruptions] = await Promise.all([fetchJSON("/operational_events?limit=100"), fetchJSON("/disruptions?limit=100")]);
  $("audit-table").querySelector("tbody").innerHTML = events.map(e => `<tr><td>${e.event_at}</td><td>${e.entity_type}</td><td>${e.entity_id}</td><td>${e.event_type}</td><td>${e.actor}</td><td>${e.details_json}</td></tr>`).join("") || `<tr><td colspan="6">No audit events yet</td></tr>`;
  $("disruptions-table").querySelector("tbody").innerHTML = disruptions.map(d => `<tr><td>${d.route_id}</td><td>${d.disruption_type}</td><td>${d.starts_at}</td><td>${d.status}</td><td>${d.notes || "—"}</td></tr>`).join("") || `<tr><td colspan="5">No disruptions recorded</td></tr>`;
}
$("assign-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  try { const r = await postJSON("/assign", { student_id: $("op-student").value.trim(), route_id: $("op-route").value.trim(), stop_id: $("op-stop").value.trim() }); showOperationResult(r); await loadOperations(); }
  catch (err) { showOperationResult(`Assignment rejected: ${err.message}`); }
});
$("attendance-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  try { const r = await postJSON("/attendance", { student_id: $("att-student").value.trim(), event_date: $("att-date").value, status: $("att-status").value }); showOperationResult(r); await loadOperations(); }
  catch (err) { showOperationResult(`Attendance rejected: ${err.message}`); }
});
$("disruption-form")?.addEventListener("submit", async e => {
  e.preventDefault();
  try { const r = await postJSON("/disruptions", { route_id: $("dis-route").value.trim(), disruption_type: $("dis-type").value, starts_at: $("dis-start").value, notes: $("dis-notes").value }); showOperationResult(r); await loadOperations(); }
  catch (err) { showOperationResult(`Disruption rejected: ${err.message}`); }
});
// Hook into the existing navigation without changing the dashboard behavior.
document.querySelector('[data-view="operations"]')?.addEventListener("click", loadOperations);
