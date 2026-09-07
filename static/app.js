/**
 * Hospital Appointment Duplicate Prevention Platform - Frontend Logic
 */

// Initialize default values on page load
document.addEventListener("DOMContentLoaded", () => {
    // Set default date to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    document.getElementById("appointment_date").value = tomorrow.toISOString().split("T")[0];
    
    // Auto generate initial idempotency key
    generateIdempotencyKey();

    // Initial data fetch
    loadAppointments();
    loadDashboardMetrics();
    loadConfig();
});

// --- Role Switcher ---
function switchRole(role) {
    const staffNav = document.getElementById("staff-attempts-nav");
    if (role === "staff") {
        staffNav.style.display = "inline-block";
        loadStaffFailedAttempts();
    } else {
        staffNav.style.display = "none";
        if (document.getElementById("staff-attempts-tab").classList.contains("active")) {
            switchTab("booking-tab");
        }
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
    if (tabId === "appointments-tab") loadAppointments();
    if (tabId === "staff-attempts-tab") loadStaffFailedAttempts();
    if (tabId === "dashboard-tab") loadDashboardMetrics();
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
        retry_number: 0
    };

    try {
        const response = await fetch(`/api/appointments?mode=${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        renderBookingResult(response.status, data, mode, payload.idempotency_key);
        loadAppointments();
        loadDashboardMetrics();
    } catch (err) {
        alert("Failed to connect to backend server: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "Submit Booking Request";
    }
}

// --- Render Booking Result & Explanation ---
function renderBookingResult(status, data, mode, key) {
    document.getElementById("bookingResultPlaceholder").style.display = "none";
    const resultCard = document.getElementById("bookingResultCard");
    resultCard.style.display = "block";

    let bannerClass = status === 200 || status === 201 ? "banner-success" : (status === 409 ? "banner-rejected" : "banner-danger");
    let statusTitle = status === 200 || status === 201 ? "CONFIRMED" : (status === 409 ? "REJECTED (SLOT BOOKED)" : "FAILED");

    let explanationText = "";
    if (data.message && data.message.includes("idempotency")) {
        explanationText = `🔁 <strong>Idempotency Key Active:</strong> The system recognized key <code>${key}</code> as a request retry. Instead of creating a duplicate appointment, it safely returned the existing confirmed appointment record.`;
    } else if (status === 409) {
        explanationText = `🛡️ <strong>Concurrency Conflict Prevented:</strong> Another request reserved this exact doctor slot. The database UNIQUE constraint blocked this duplicate booking request.`;
    } else if (mode === "baseline") {
        explanationText = `⚠️ <strong>Baseline Mode:</strong> Request checked slot availability and inserted appointment <code>${data.appointment_id}</code>. Warning: Simultaneous concurrent requests in baseline mode can bypass this check and cause double-bookings!`;
    } else {
        explanationText = `✅ <strong>Protected Booking Confirmed:</strong> Slot successfully locked for appointment <code>${data.appointment_id}</code> under strict concurrency control.`;
    }

    resultCard.innerHTML = `
        <div class="result-status-banner ${bannerClass}">
            <span>Status: ${statusTitle} (HTTP ${status})</span>
            <span class="badge ${mode === 'protected' ? 'badge-success' : 'badge-warning'}">${mode.toUpperCase()} MODE</span>
        </div>
        <p><strong>Appointment ID:</strong> <code>${data.appointment_id || 'N/A'}</code></p>
        <p><strong>Patient ID:</strong> ${data.patient_id}</p>
        <p><strong>Doctor Slot:</strong> ${data.doctor_id} @ ${data.appointment_date} ${data.appointment_time}</p>
        <p><strong>Idempotency Key:</strong> <code>${data.idempotency_key || 'None'}</code></p>
        <p><strong>Message:</strong> ${data.message || 'Processed'}</p>

        <div class="explanation-box">
            <div class="explanation-title">Non-Technical Hospital Reviewer Explanation</div>
            <p>${explanationText}</p>
        </div>
    `;
}

// --- Load Confirmed Appointments Table ---
async function loadAppointments() {
    const mode = document.getElementById("appFilterMode").value;
    try {
        const res = await fetch(`/api/appointments?${mode ? 'mode=' + mode : ''}`);
        const appointments = await res.json();

        const tbody = document.getElementById("appointmentsTableBody");
        tbody.innerHTML = "";

        if (appointments.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No appointments booked yet.</td></tr>`;
            return;
        }

        // Count slot duplicates to highlight
        const slotCounts = {};
        appointments.forEach(a => {
            if (a.booking_status === "CONFIRMED") {
                const k = `${a.patient_id}|${a.doctor_id}|${a.appointment_date}|${a.appointment_time}`;
                slotCounts[k] = (slotCounts[k] || 0) + 1;
            }
        });

        appointments.forEach(app => {
            const slotKey = `${app.patient_id}|${app.doctor_id}|${app.appointment_date}|${app.appointment_time}`;
            const isDup = slotCounts[slotKey] > 1;

            const tr = document.createElement("tr");
            if (isDup) tr.classList.add("highlight-row-danger");

            tr.innerHTML = `
                <td><code>${app.appointment_id}</code></td>
                <td>${app.patient_id}</td>
                <td>${app.doctor_id}</td>
                <td>${app.appointment_date} ${app.appointment_time}</td>
                <td><code>${app.idempotency_key || '-'}</code></td>
                <td><span class="badge ${app.mode === 'protected' ? 'badge-info' : 'badge-warning'}">${app.mode}</span></td>
                <td>
                    <span class="badge ${app.booking_status === 'CONFIRMED' ? 'badge-success' : 'badge-danger'}">${app.booking_status}</span>
                    ${isDup ? '<span class="badge badge-danger">⚠️ DUPLICATE ROW!</span>' : ''}
                </td>
                <td>${new Date(app.created_at).toLocaleTimeString()}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading appointments:", err);
    }
}

// --- Load Staff Failed Attempts Audit ---
async function loadStaffFailedAttempts() {
    try {
        const res = await fetch("/api/tests/results");
        const data = await res.json();
        const failedTraces = (data.traces || []).filter(t => !t.success || t.response_status >= 400 || t.database_result === "SLOT_CONFLICT_REJECTED");

        const tbody = document.getElementById("staffFailedTableBody");
        tbody.innerHTML = "";

        if (failedTraces.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No failed or rejected booking attempts recorded.</td></tr>`;
            return;
        }

        failedTraces.forEach(t => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${t.trace_id}</code></td>
                <td>${t.patient_id}</td>
                <td>${t.doctor_id} @ ${t.appointment_date} ${t.appointment_time}</td>
                <td>${new Date(t.request_start_time * 1000).toLocaleTimeString()}</td>
                <td><span class="badge badge-warning">${t.database_result}</span></td>
                <td>${t.explanation}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading staff attempts:", err);
    }
}

// --- Test Harness Triggers ---
async function triggerTest(type) {
    const testSlot = {
        patient_id: "P-SIMULATED",
        doctor_id: "DOC-CARDIOLOGY-01",
        appointment_date: "2026-09-30",
        appointment_time: "10:00",
        idempotency_key: `IDEM-TEST-${Date.now()}`
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
        // Run baseline first to show race condition, then protected
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
    loadAppointments();
}

async function resetAllData() {
    if (confirm("Reset all stored appointments and test traces?")) {
        await fetch("/api/tests/reset", { method: "POST" });
        loadDashboardMetrics();
        loadAppointments();
        loadStaffFailedAttempts();
    }
}

// --- Load Dashboard Metrics & Traces ---
async function loadDashboardMetrics() {
    try {
        const res = await fetch("/api/tests/results");
        const data = await res.json();
        const metrics = data.metrics || {};
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

        renderTracesTable(data.traces || []);
    } catch (err) {
        console.error("Error loading dashboard metrics:", err);
    }
}

// --- Render Traces Table ---
function renderTracesTable(traces) {
    const modeFilter = document.getElementById("traceFilterMode").value;
    let filtered = traces;
    if (modeFilter) filtered = traces.filter(t => t.mode === modeFilter);

    const tbody = document.getElementById("tracesTableBody");
    tbody.innerHTML = "";

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted);">No request traces recorded yet. Run a test to populate traces.</td></tr>`;
        return;
    }

    filtered.forEach(t => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><code>${t.trace_id}</code></td>
            <td><span class="badge ${t.mode === 'protected' ? 'badge-info' : 'badge-warning'}">${t.mode}</span></td>
            <td>${t.test_type}</td>
            <td>${t.doctor_id} @ ${t.appointment_date} ${t.appointment_time}</td>
            <td><code>${t.idempotency_key || '-'}</code></td>
            <td><span class="badge ${t.success ? 'badge-success' : 'badge-danger'}">HTTP ${t.response_status}</span></td>
            <td><code>${t.database_result}</code></td>
            <td>${t.duration_ms} ms</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="openExplanationModal('${t.trace_id}')">💡 Explain</button>
            </td>
        `;
        // Store trace object on row for modal retrieval
        tr.dataset.traceObj = JSON.stringify(t);
        tbody.appendChild(tr);
    });
}

function loadTraces() {
    loadDashboardMetrics();
}

// --- Explanation Modal Layer ---
function openExplanationModal(traceId) {
    const rows = Array.from(document.querySelectorAll("#tracesTableBody tr"));
    const targetRow = rows.find(r => r.dataset.traceObj && JSON.parse(r.dataset.traceObj).trace_id === traceId);
    if (!targetRow) return;

    const t = JSON.parse(targetRow.dataset.traceObj);
    const modal = document.getElementById("explanationModal");
    document.getElementById("modalTitle").innerText = `Trace ${t.trace_id} — Hospital Reviewer Explanation`;

    document.getElementById("modalBody").innerHTML = `
        <div class="explanation-box" style="margin-top:0;">
            <div class="explanation-title">Overview</div>
            <p>${t.explanation}</p>
        </div>
        <br>
        <p><strong>Mode:</strong> ${t.mode.toUpperCase()}</p>
        <p><strong>Test Category:</strong> ${t.test_type}</p>
        <p><strong>Patient & Doctor Slot:</strong> Patient ${t.patient_id} booking ${t.doctor_id} for ${t.appointment_date} at ${t.appointment_time}</p>
        <p><strong>Idempotency Key:</strong> <code>${t.idempotency_key || 'None'}</code></p>
        <p><strong>Database Concurrency Result:</strong> <code>${t.database_result}</code></p>
        <p><strong>Execution Latency:</strong> ${t.duration_ms} ms</p>
        <br>
        <div class="card" style="background:rgba(15,23,42,0.8); font-size:0.85rem;">
            <strong>Why is Protected Safer than Baseline?</strong><br>
            Baseline performs a check before inserting. When 10 concurrent requests arrive in the same millisecond, all 10 read 'slot free' before any insertion completes, creating 10 duplicate rows in SQLite.<br><br>
            The Protected system enforces an atomic database <code>UNIQUE</code> constraint on <code>(patient_id, doctor_id, date, time)</code> inside an immediate transaction, allowing exactly 1 request to succeed and safely rejecting all competing requests.
        </div>
    `;

    modal.classList.add("active");
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
        SIMULATED_PROCESSING_DELAY_MS: parseInt(document.getElementById("cfg_delay").value)
    };

    try {
        await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(newCfg)
        });
        alert("Configuration updated successfully!");
    } catch (err) {
        alert("Failed to save config: " + err.message);
    }
}
