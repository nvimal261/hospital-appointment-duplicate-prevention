/**
 * Hospital Appointment Duplicate Prevention Platform - Frontend Logic
 */

let activeRole = "patient";

// Initialize default values on page load
document.addEventListener("DOMContentLoaded", () => {
    // Set default date to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    document.getElementById("appointment_date").value = tomorrow.toISOString().split("T")[0];
    
    // Auto generate initial idempotency key
    generateIdempotencyKey();

    // Initial role setup
    switchRole("patient");

    // Initial data fetch
    loadDashboardMetrics();
    loadConfig();
});

// --- Role Switcher ---
function switchRole(role) {
    activeRole = role;
    const badge = document.getElementById("roleBadge");
    const adminTabs = document.querySelectorAll(".admin-only");

    if (role === "staff") {
        badge.innerText = "Role: Hospital Staff / Admin";
        badge.className = "role-badge badge-staff";
        adminTabs.forEach(el => el.style.display = "inline-block");
        loadStaffView();
    } else {
        badge.innerText = "Role: Patient";
        badge.className = "role-badge badge-patient";
        adminTabs.forEach(el => el.style.display = "none");
        // If currently on an admin tab, switch back to booking tab
        const activeTabEl = document.querySelector(".tab-content.active");
        if (activeTabEl && activeTabEl.classList.contains("admin-only")) {
            switchTab("booking-tab");
        }
        loadPatientAppointments();
    }
}

// --- Navigation Tab Switcher ---
function switchTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

    const targetTab = document.getElementById(tabId);
    if (targetTab) targetTab.classList.add("active");

    // Highlight active nav button
    const activeBtn = Array.from(document.querySelectorAll(".tab-btn")).find(btn => btn.getAttribute("onclick")?.includes(tabId));
    if (activeBtn) activeBtn.classList.add("active");

    // Refresh tab data
    if (tabId === "patient-tab") loadPatientAppointments();
    if (tabId === "staff-tab") loadStaffView();
    if (tabId === "traces-tab") loadTraces();
    if (tabId === "retries-tab") loadRetryEvents();
    if (tabId === "transactions-tab") loadTransactionEvents();
    if (tabId === "metrics-tab") loadDashboardMetrics();
    if (tabId === "config-tab") loadConfig();
}

// --- Idempotency Key Generator ---
function generateIdempotencyKey() {
    const randomHex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
        .map(b => b.toString(16).padStart(2, "0"))
        .join("")
        .toUpperCase();
    document.getElementById("idempotency_key").value = `IDEM-KEY-${randomHex}`;
}

// --- Handle Single Booking Submit ---
async function handleBookingSubmit(event) {
    event.preventDefault();
    const btn = document.getElementById("bookSubmitBtn");
    btn.disabled = true;
    btn.innerHTML = "⏳ Processing Request...";

    const mode = document.querySelector('input[name="bookingMode"]:checked').value;
    const payload = {
        patient_id: document.getElementById("patient_id").value.trim(),
        doctor_id: document.getElementById("doctor_id").value,
        appointment_date: document.getElementById("appointment_date").value,
        appointment_time: document.getElementById("appointment_time").value,
        idempotency_key: document.getElementById("idempotency_key").value.trim() || null,
        retry_number: 0,
        role: activeRole === "staff" ? "Hospital Staff" : "Patient"
    };

    try {
        const response = await fetch(`/api/appointments?mode=${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        renderBookingResult(response.status, data, mode, payload.idempotency_key);
        loadDashboardMetrics();
    } catch (err) {
        alert("Failed to connect to backend server: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "Submit Booking Request";
    }
}

// --- Render Booking Result & Rationale ---
function renderBookingResult(status, data, mode, key) {
    document.getElementById("bookingResultPlaceholder").style.display = "none";
    const resultCard = document.getElementById("bookingResultCard");
    resultCard.style.display = "block";

    let bannerClass = status === 200 || status === 201 ? "banner-success" : (status === 409 ? "banner-rejected" : "banner-danger");
    let statusTitle = data.booking_status || (status === 200 || status === 201 ? "CONFIRMED" : (status === 409 ? "REJECTED (SLOT BOOKED)" : "FAILED"));

    let fallbackHtml = "";
    if (data.alternative_slots && data.alternative_slots.length > 0) {
        fallbackHtml = `
            <div class="fallback-box">
                <strong>💡 Available Alternative Slots (Fallback Suggestion):</strong>
                <div class="fallback-slots-list margin-top">
                    ${data.alternative_slots.map(s => `
                        <button class="btn btn-secondary btn-sm" onclick="selectAlternateSlot('${s.doctor_id}', '${s.appointment_date}', '${s.appointment_time}')">
                            ${s.doctor_id} @ ${s.appointment_time}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    let actionsHtml = "";
    if (data.fallback_actions && data.fallback_actions.length > 0) {
        actionsHtml = `
            <div class="margin-top">
                <small><strong>Suggested Next Steps:</strong></small>
                <ul style="margin-top:4px; padding-left:18px; font-size:0.85rem; color:var(--text-muted);">
                    ${data.fallback_actions.map(a => `<li>${a}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    resultCard.innerHTML = `
        <div class="result-status-banner ${bannerClass}">
            <span>Status: ${statusTitle} (HTTP ${status})</span>
            <span class="badge ${mode === 'protected' ? 'badge-success' : 'badge-warning'}">${mode.toUpperCase()} MODE</span>
        </div>
        <p><strong>Request ID:</strong> <code>${data.request_id || 'REQ-N/A'}</code></p>
        <p><strong>Appointment ID:</strong> <code>${data.appointment_id || 'None'}</code></p>
        <p><strong>Patient ID:</strong> ${data.patient_id}</p>
        <p><strong>Doctor Slot:</strong> ${data.doctor_id} @ ${data.appointment_date} ${data.appointment_time}</p>
        <p><strong>Reason Code:</strong> <code>${data.reason_code || 'N/A'}</code></p>
        <p><strong>Message:</strong> ${data.message || 'Processed'}</p>

        <div class="explanation-box">
            <div class="explanation-title">Human-Readable Explanation (Non-Specialist View)</div>
            <p>${data.human_readable_explanation || data.message || 'No specific explanation provided.'}</p>
            ${actionsHtml}
        </div>

        ${fallbackHtml}
    `;
}

function selectAlternateSlot(docId, dateStr, timeStr) {
    document.getElementById("doctor_id").value = docId;
    document.getElementById("appointment_date").value = dateStr;
    document.getElementById("appointment_time").value = timeStr;
    generateIdempotencyKey();
    alert(`Updated slot to ${docId} @ ${dateStr} ${timeStr}. Click Submit to book!`);
}

// --- Load Patient View Appointments ---
async function loadPatientAppointments() {
    try {
        const res = await fetch("/api/traces");
        const traces = await res.json();

        const tbody = document.getElementById("patientAppointmentsBody");
        tbody.innerHTML = "";

        if (traces.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No appointment requests recorded for patient.</td></tr>`;
            return;
        }

        traces.slice(0, 20).forEach(t => {
            const tr = document.createElement("tr");
            const isConfirmed = t.database_result === "INSERTED" || t.database_result === "RETURNED_IDEMPOTENT" || t.response_status === 200;
            
            tr.innerHTML = `
                <td><code>${t.request_id}</code></td>
                <td>${t.doctor_id}</td>
                <td>${t.appointment_date} ${t.appointment_time}</td>
                <td><span class="badge ${isConfirmed ? 'badge-success' : 'badge-danger'}">${isConfirmed ? 'CONFIRMED' : 'REJECTED'}</span></td>
                <td><code>${t.database_result}</code></td>
                <td>${t.explanation}</td>
                <td>
                    ${!isConfirmed ? `
                        <button class="btn btn-secondary btn-sm" onclick="retryAppointment('${t.patient_id}', '${t.doctor_id}', '${t.appointment_date}', '${t.appointment_time}', '${t.idempotency_key}')">
                            🔄 Retry Request
                        </button>
                    ` : '<span class="text-success">Confirmed</span>'}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading patient appointments:", err);
    }
}

function retryAppointment(patId, docId, dateStr, timeStr, oldKey) {
    switchTab("booking-tab");
    document.getElementById("patient_id").value = patId;
    document.getElementById("doctor_id").value = docId;
    document.getElementById("appointment_date").value = dateStr;
    document.getElementById("appointment_time").value = timeStr;
    document.getElementById("idempotency_key").value = oldKey || `IDEM-RETRY-${Date.now()}`;
    alert("Loaded request details into Booking Form. Click 'Submit Booking Request' to execute retry.");
}

// --- Load Staff/Admin View ---
async function loadStaffView() {
    const filter = document.getElementById("staffFilterMode").value;
    try {
        const resApps = await fetch(`/api/appointments${filter ? '?mode=' + filter : ''}`);
        const apps = await resApps.json();

        const resMetrics = await fetch("/api/metrics");
        const metrics = await resMetrics.json();
        const p = metrics.protected || {};

        document.getElementById("staff-total-apps").innerText = apps.length;
        document.getElementById("staff-prevented-count").innerText = p.duplicate_records_prevented || 0;
        document.getElementById("staff-prevention-rate").innerText = `${(p.prevention_rate_percent || 100.0).toFixed(1)}%`;

        const tbody = document.getElementById("staffAppointmentsTableBody");
        tbody.innerHTML = "";

        if (apps.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No stored appointment records found.</td></tr>`;
            return;
        }

        apps.forEach(app => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${app.appointment_id}</code></td>
                <td>${app.patient_id}</td>
                <td>${app.doctor_id}</td>
                <td>${app.appointment_date} ${app.appointment_time}</td>
                <td><code>${app.idempotency_key || '-'}</code></td>
                <td><span class="badge ${app.mode === 'protected' ? 'badge-info' : 'badge-warning'}">${app.mode}</span></td>
                <td><span class="badge ${app.booking_status === 'CONFIRMED' ? 'badge-success' : 'badge-danger'}">${app.booking_status}</span></td>
                <td>${new Date(app.created_at).toLocaleTimeString()}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading staff view:", err);
    }
}

// --- Load Request Traces ---
async function loadTraces() {
    try {
        const res = await fetch("/api/traces");
        const traces = await res.json();

        const tbody = document.getElementById("tracesTableBody");
        tbody.innerHTML = "";

        if (traces.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted);">No request traces recorded. Run test harness to generate traces.</td></tr>`;
            return;
        }

        traces.forEach(t => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${t.trace_id}</code></td>
                <td><code>${t.request_id}</code></td>
                <td><span class="badge badge-info">${t.role || 'Patient'}</span></td>
                <td><span class="badge ${t.mode === 'protected' ? 'badge-success' : 'badge-warning'}">${t.mode}</span></td>
                <td>${t.patient_id} / ${t.doctor_id}</td>
                <td>${t.appointment_date} ${t.appointment_time}</td>
                <td><span class="badge ${t.transaction_status === 'COMMITTED' ? 'badge-success' : 'badge-danger'}">${t.transaction_status || 'COMMITTED'}</span></td>
                <td>${t.duration_ms} ms</td>
                <td><small><code>${t.steps || 'REQUEST_RECEIVED'}</code></small></td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="openExplanationModal('${t.trace_id}')">💡 Explain</button>
                </td>
            `;
            tr.dataset.traceObj = JSON.stringify(t);
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading traces:", err);
    }
}

// --- Load Retry Events ---
async function loadRetryEvents() {
    try {
        const res = await fetch("/api/retries");
        const retries = await res.json();

        const tbody = document.getElementById("retryEventsTableBody");
        tbody.innerHTML = "";

        if (retries.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No retry events recorded yet.</td></tr>`;
            return;
        }

        retries.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${r.retry_id}</code></td>
                <td><code>${r.request_id}</code></td>
                <td><code>${r.original_request_id || '-'}</code></td>
                <td><span class="badge badge-info">Attempt #${r.retry_number}</span></td>
                <td><code>${r.idempotency_key || '-'}</code></td>
                <td>${r.retry_reason}</td>
                <td>${r.result}</td>
                <td>${new Date(r.timestamp).toLocaleTimeString()}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading retry events:", err);
    }
}

// --- Load Transaction Events ---
async function loadTransactionEvents() {
    try {
        const res = await fetch("/api/traces");
        const traces = await res.json();

        const tbody = document.getElementById("transactionEventsTableBody");
        tbody.innerHTML = "";

        if (traces.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No transaction events recorded.</td></tr>`;
            return;
        }

        traces.forEach(t => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${t.request_id}</code></td>
                <td><span class="badge ${t.mode === 'protected' ? 'badge-info' : 'badge-warning'}">${t.mode}</span></td>
                <td><span class="badge ${t.transaction_status === 'COMMITTED' ? 'badge-success' : 'badge-danger'}">${t.transaction_status || 'COMMITTED'}</span></td>
                <td><code>${t.database_result}</code></td>
                <td>${t.duplicate_detected ? '⚠️ Yes' : 'No'}</td>
                <td>${t.duplicate_prevented ? '🛡️ Yes' : 'No'}</td>
                <td><code>${t.steps || 'REQUEST_RECEIVED -> TRANSACTION_COMMIT'}</code></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading transaction events:", err);
    }
}

// --- Test Harness Triggers ---
async function triggerTest(type) {
    const testSlot = {
        patient_id: "P-SIMULATED",
        doctor_id: "DOC-CARDIOLOGY-01",
        appointment_date: "2026-09-30",
        appointment_time: "10:00",
        idempotency_key: `IDEM-TEST-${Date.now()}`,
        role: activeRole === "staff" ? "Hospital Staff" : "Patient"
    };

    if (type === 'normal') {
        alert("Running Test Case 1: Sending 1 Single Request in Protected Mode...");
        await fetch("/api/tests/normal?mode=protected", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testSlot)
        });
    } else if (type === 'retry') {
        alert("Running Test Case 2: Sending same request 3 times sequentially with identical Idempotency Key...");
        await fetch("/api/tests/retry?mode=protected&retries=3", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testSlot)
        });
    } else if (type === 'concurrent') {
        alert("Running Test Case 3: Launching 10 concurrent requests for exact same slot simultaneously across both Baseline & Protected modes...");
        await fetch("/api/tests/concurrent?mode=baseline&count=10", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testSlot)
        });
        await fetch("/api/tests/concurrent?mode=protected&count=10", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testSlot)
        });
    } else if (type === 'synthetic') {
        alert("Running Test Case 4: Running full 60-item synthetic benchmark dataset across Baseline & Protected modes...");
        await fetch("/api/tests/synthetic", { method: "POST" });
    }

    loadDashboardMetrics();
}

async function resetAllData() {
    if (confirm("Reset all stored appointments and test traces?")) {
        await fetch("/api/tests/reset", { method: "POST" });
        loadDashboardMetrics();
    }
}

// --- Load Dashboard Metrics ---
async function loadDashboardMetrics() {
    try {
        const res = await fetch("/api/metrics");
        const metrics = await res.json();
        const b = metrics.baseline || {};
        const p = metrics.protected || {};

        document.getElementById("m-base-total").innerText = b.total_requests || 0;
        document.getElementById("m-prot-total").innerText = p.total_requests || 0;

        document.getElementById("m-base-success").innerText = b.successful_bookings || 0;
        document.getElementById("m-prot-success").innerText = p.successful_bookings || 0;

        document.getElementById("m-base-dup-created").innerText = b.duplicate_records_created || 0;
        document.getElementById("m-prot-dup-created").innerText = p.duplicate_records_created || 0;

        document.getElementById("m-base-dup-prevented").innerText = b.duplicate_records_prevented || 0;
        document.getElementById("m-prot-dup-prevented").innerText = p.duplicate_records_prevented || 0;

        document.getElementById("m-base-retry").innerText = b.retry_requests || 0;
        document.getElementById("m-prot-retry").innerText = p.retry_requests || 0;

        document.getElementById("m-base-concurrent").innerText = b.concurrent_requests || 0;
        document.getElementById("m-prot-concurrent").innerText = p.concurrent_requests || 0;

        const bRate = (b.prevention_rate_percent !== undefined) ? b.prevention_rate_percent : 0.0;
        const pRate = (p.prevention_rate_percent !== undefined) ? p.prevention_rate_percent : 100.0;

        document.getElementById("m-base-rate").innerText = `${bRate.toFixed(1)}%`;
        document.getElementById("m-prot-rate").innerText = `${pRate.toFixed(1)}%`;
    } catch (err) {
        console.error("Error loading dashboard metrics:", err);
    }
}

// --- Explanation Modal Layer ---
function openExplanationModal(traceId) {
    fetch(`/api/traces/${traceId}`).then(res => res.json()).then(t => {
        const modal = document.getElementById("explanationModal");
        document.getElementById("modalTitle").innerText = `Trace ${t.trace_id} — Hospital Reviewer Rationale`;

        document.getElementById("modalBody").innerHTML = `
            <div class="explanation-box" style="margin-top:0;">
                <div class="explanation-title">Overview Rationale</div>
                <p>${t.explanation}</p>
            </div>
            <br>
            <p><strong>Request ID:</strong> <code>${t.request_id}</code></p>
            <p><strong>Role:</strong> ${t.role || 'Patient'}</p>
            <p><strong>Mode:</strong> ${(t.mode || 'protected').toUpperCase()}</p>
            <p><strong>Doctor Slot:</strong> ${t.doctor_id} @ ${t.appointment_date} ${t.appointment_time}</p>
            <p><strong>Idempotency Key:</strong> <code>${t.idempotency_key || 'None'}</code></p>
            <p><strong>Transaction Status:</strong> <span class="badge ${t.transaction_status === 'COMMITTED' ? 'badge-success' : 'badge-danger'}">${t.transaction_status || 'COMMITTED'}</span></p>
            <p><strong>Database Result:</strong> <code>${t.database_result}</code></p>
            <p><strong>Pipeline Steps:</strong> <code>${t.steps || 'N/A'}</code></p>
            <p><strong>Execution Latency:</strong> ${t.duration_ms} ms</p>
        `;

        modal.classList.add("active");
    }).catch(err => alert("Trace detail failed to load: " + err.message));
}

function closeExplanationModalDirect() {
    document.getElementById("explanationModal").classList.remove("active");
}

function closeExplanationModal(event) {
    if (event.target.classList.contains("modal-overlay")) {
        closeExplanationModalDirect();
    }
}

// --- Config Form ---
async function loadConfig() {
    try {
        const res = await fetch("/api/config");
        const cfg = await res.json();
        document.getElementById("cfg_max_retries").value = cfg.MAX_RETRIES;
        document.getElementById("cfg_enable_idempotency").checked = cfg.ENABLE_IDEMPOTENCY;
        document.getElementById("cfg_enable_concurrency").checked = cfg.ENABLE_CONCURRENCY_PROTECTION;
        document.getElementById("cfg_policy").value = cfg.SLOT_CONFLICT_POLICY;
        document.getElementById("cfg_enable_tracing").checked = cfg.ENABLE_REQUEST_TRACING !== false;
        document.getElementById("cfg_enable_explanation").checked = cfg.ENABLE_EXPLANATION_LAYER !== false;
        document.getElementById("cfg_delay").value = cfg.SIMULATED_PROCESSING_DELAY_MS;
    } catch (err) {
        console.error("Error loading config:", err);
    }
}

async function handleConfigSubmit(event) {
    event.preventDefault();
    const newCfg = {
        MAX_RETRIES: parseInt(document.getElementById("cfg_max_retries").value),
        ENABLE_IDEMPOTENCY: document.getElementById("cfg_enable_idempotency").checked,
        ENABLE_CONCURRENCY_PROTECTION: document.getElementById("cfg_enable_concurrency").checked,
        SLOT_CONFLICT_POLICY: document.getElementById("cfg_policy").value,
        ENABLE_REQUEST_TRACING: document.getElementById("cfg_enable_tracing").checked,
        ENABLE_EXPLANATION_LAYER: document.getElementById("cfg_enable_explanation").checked,
        SIMULATED_PROCESSING_DELAY_MS: parseInt(document.getElementById("cfg_delay").value)
    };

    try {
        await fetch("/api/config", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(newCfg)
        });
        alert("System business rules updated successfully!");
    } catch (err) {
        alert("Failed to save config: " + err.message);
    }
}
