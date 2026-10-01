# Hospital Appointment Platform: Idempotency + Concurrency Test Harness + Duplicate Record Prevention

> **NEXT 35% IMPLEMENTATION DELIVERABLE**  
> Prototype demonstrating strict concurrency control, idempotency key deduplication, request tracing, transaction boundary visibility, transparent non-specialist explanations, and multi-role capabilities.

---

## 1. Project Overview & Architecture

Hospital appointment booking platforms face critical concurrency challenges. When multiple patients simultaneously attempt to reserve the same doctor time slot (or when network retries resend identical requests), standard check-then-insert handlers create duplicate database records.

This prototype provides an **empirical test harness and side-by-side comparative architecture**:
* **Baseline Mode (Unprotected):** Vulnerable to Time-of-Check to Time-of-Use (TOCTOU) race conditions.
* **Protected Prototype:** Employs SQLite WAL Immediate Write Transactions, Database `UNIQUE` constraints on `(doctor_id, appointment_date, appointment_time)` and `idempotency_key`, request tracing, transaction rollback visibility, and a rule-based explanation layer.

```
Incoming Request (Patient / Admin Role)
            │
            ▼
┌───────────────────────────┐
│     FastAPI Router        │ ──► [Request Tracer: REQ-PROT-XXXX]
└─────────────┬─────────────┘
              │
              ├──► [Check MAX_RETRIES & Idempotency Key]
              │          │
              │          ├──► Match Found ──► Return Cached Booking (200 OK)
              │
              ▼
┌───────────────────────────┐
│  Immediate SQLite Lock    │ ──► [TRANSACTION_BEGIN]
└─────────────┬─────────────┘
              │
              ├──► INSERT INTO protected_appointments (UNIQUE slot constraint)
              │          │
              │          ├──► Success ──────► [TRANSACTION_COMMIT] (200 OK)
              │          └──► Constraint Violation (409) ──► [TRANSACTION_ROLLBACK]
              ▼
┌───────────────────────────┐
│    Explanation Layer      │ ──► Human-readable rationale & Fallback suggestions
└───────────────────────────┘
```

---

## 2. Multi-User Roles

The platform implements two operational user roles accessible via the frontend role selector:

1. **Patient Role:**
   * Submit appointment booking requests.
   * View booking response and human-readable explanation rationale.
   * View personal appointment list (`Patient View`).
   * Retry failed requests directly from the UI.
   * View suggested alternative doctor/time slots if slot conflict occurs.

2. **Hospital Staff / Admin Role:**
   * Full visibility into all appointment records.
   * Access to **Staff Audit & Control Center**.
   * View duplicate prevention events, request traces, transaction events, and retry logs.
   * Dynamically update system business rules configuration (`MAX_RETRIES`, `SLOT_CONFLICT_POLICY`, toggles).
   * Execute automated test harness benchmarks.

---

## 3. Configurable Business Rules

Business rules are managed dynamically via `GET /api/config` and `PUT /api/config`:

* `MAX_RETRIES` (default: `3`): Maximum allowed retry attempts per idempotency key.
* `ENABLE_IDEMPOTENCY` (default: `true`): Toggles idempotent deduplication lookup.
* `ENABLE_CONCURRENCY_PROTECTION` (default: `true`): Toggles atomic database write locking.
* `SLOT_CONFLICT_POLICY` (`"REJECT"`, `"RETRY"`, `"FALLBACK"`):
  * `"REJECT"`: Returns HTTP 409 Conflict.
  * `"RETRY"`: Recommends automated client retry.
  * `"FALLBACK"`: Calculates and attaches available alternative doctor slots.
* `ENABLE_REQUEST_TRACING` (default: `true`): Toggles request lifecycle tracing.
* `ENABLE_EXPLANATION_LAYER` (default: `true`): Toggles transparent non-technical explanations.
* `SIMULATED_PROCESSING_DELAY_MS` (default: `30`): Processing delay window to demonstrate baseline race window.

---

## 4. Request Tracing & Transaction Boundary Visibility

Every booking request is assigned a unique `request_id` and tracked through explicit lifecycle steps:

```
REQUEST_RECEIVED ──► VALIDATION ──► IDEMPOTENCY_CHECK ──► SLOT_CHECK ──► TRANSACTION_BEGIN ──► DATABASE_OPERATION ──► TRANSACTION_COMMIT / ROLLBACK ──► RESPONSE_GENERATED
```

Each trace records:
* `request_id`, `role`, `mode`, `patient_id`, `doctor_id`, `appointment_date`, `appointment_time`
* `transaction_status`: `COMMITTED`, `ROLLED_BACK`, or `REJECTED`
* `duplicate_detected`, `duplicate_prevented` flags
* Processing duration in milliseconds and execution steps pipeline.

---

## 5. Non-Technical Explanation & Fallback Layer

Every appointment response includes a transparent, rule-based explanation layer:

* **CONFIRMED:** *"Appointment confirmed because the requested slot was available."*
* **IDEMPOTENT RETRY:** *"This request was already processed. The existing appointment was returned instead of creating another record."*
* **SLOT CONFLICT:** *"The requested doctor/time slot is already booked."*
* **CONCURRENCY CONFLICT:** *"Another request reserved this slot first. This request was rejected to prevent double booking."*
* **FALLBACK WORKFLOW:** Returns alternative available slots (e.g., `DOC-CARDIOLOGY-01 @ 11:30`) and recommended next steps without automatically forcing an unconfirmed booking.

---

## 6. API Integration Examples

### 6.1 Book Appointment (`POST /api/appointments/book` or `/api/appointments`)
**Request:**
```json
POST /api/appointments/book?mode=protected
Content-Type: application/json

{
  "patient_id": "P-101",
  "doctor_id": "DOC-CARDIOLOGY-01",
  "appointment_date": "2026-11-01",
  "appointment_time": "09:00",
  "idempotency_key": "IDEM-KEY-A1B2C3",
  "retry_number": 0,
  "role": "Patient"
}
```

**Response (HTTP 200 OK):**
```json
{
  "appointment_id": "APP-PROT-7AAFC762",
  "patient_id": "P-101",
  "doctor_id": "DOC-CARDIOLOGY-01",
  "appointment_date": "2026-11-01",
  "appointment_time": "09:00",
  "idempotency_key": "IDEM-KEY-A1B2C3",
  "booking_status": "CONFIRMED",
  "mode": "protected",
  "created_at": "2026-09-29T11:48:00.123456",
  "message": "Appointment successfully booked.",
  "request_id": "REQ-PROT-89ABCDEF",
  "status": "CONFIRMED",
  "reason_code": "SLOT_AVAILABLE",
  "human_readable_explanation": "Appointment confirmed because the requested doctor slot was available.",
  "fallback_actions": [],
  "alternative_slots": []
}
```

### 6.2 Retrieve Specific Trace (`GET /api/traces/{request_id}`)
**Response:**
```json
{
  "trace_id": "TR-12345678",
  "request_id": "REQ-PROT-89ABCDEF",
  "mode": "protected",
  "role": "Patient",
  "test_type": "manual",
  "idempotency_key": "IDEM-KEY-A1B2C3",
  "patient_id": "P-101",
  "doctor_id": "DOC-CARDIOLOGY-01",
  "appointment_date": "2026-11-01",
  "appointment_time": "09:00",
  "duration_ms": 14.5,
  "success": 1,
  "response_status": 200,
  "database_result": "INSERTED",
  "transaction_status": "COMMITTED",
  "steps": "REQUEST_RECEIVED -> VALIDATION -> IDEMPOTENCY_CHECK -> SLOT_CHECK -> TRANSACTION_BEGIN -> DATABASE_OPERATION -> TRANSACTION_COMMIT -> RESPONSE_GENERATED",
  "explanation": "Protected booking created appointment APP-PROT-7AAFC762 successfully."
}
```

### 6.3 Read System Configuration (`GET /api/config`)
**Response:**
```json
{
  "MAX_RETRIES": 3,
  "ENABLE_IDEMPOTENCY": true,
  "ENABLE_CONCURRENCY_PROTECTION": true,
  "SLOT_CONFLICT_POLICY": "FALLBACK",
  "ENABLE_REQUEST_TRACING": true,
  "ENABLE_EXPLANATION_LAYER": true,
  "SIMULATED_PROCESSING_DELAY_MS": 30
}
```

### 6.4 Additional Available Endpoints
* `GET /api/appointments/{appointment_id}`
* `GET /api/retries/{request_id}`
* `GET /api/metrics`
* `PUT /api/config`
* `GET /api/validation/results`

---

## 7. Measured Verification Results

### Baseline vs Protected Prototype Comparison (60-Item Benchmark)

| Metric Description | Baseline Mode | Protected Prototype |
| :--- | :--- | :--- |
| **Total Requests Executed** | 60 | 60 |
| **Successful Confirmed Bookings** | 50 | 42 |
| **Duplicate Records Created in DB** | **18** | **0** |
| **Duplicate Records Prevented** | 10 | 28 |
| **Retry Requests Processed** | 15 | 15 |
| **Concurrent Race Attempts** | 20 | 20 |
| **Failed / Rejected Requests** | 10 | 18 |
| **DUPLICATE PREVENTION RATE (%)** | **35.7%** | **100.0%** |

### Next Phase Validation Results (10 Validation Categories)

```
==================================================
NEXT PHASE VERIFICATION
==================================================
Total validation cases: 10
Passed: 10
Failed: 0

Retry scenarios: 3
Concurrent scenarios: 2
Duplicate scenarios: 3
Validation errors: 2
Transaction rollbacks: 2
Fallback responses: 3

Duplicate records: 0
Duplicate prevention rate: 100.0%
==================================================
```

---

## 8. Limitations & Future Scope

1. **Local SQLite Storage:** Designed for local prototype verification; multi-region production systems require PostgreSQL with Serializable isolation.
2. **In-Memory Configuration:** Config updates apply globally to the active process.
3. **Authentication:** Uses simple frontend role selectors suitable for reviewer demonstration.

---

## 9. How to Run the Application & Verification Suite

### Prerequisites
* Python 3.9+
* Required packages listed in `requirements.txt` (`fastapi`, `uvicorn`, `httpx`, `pydantic`)

### Installation
```bash
pip install -r requirements.txt
```

### Run Web Application
```bash
python -m uvicorn app.main:app --reload --port 8000
```
Open browser at: `http://127.0.0.1:8000`

### Run Complete Verification Suite
```bash
python run_verification_suite.py
```

### Run Final Demonstration Verification Checks
```bash
python run_final_demo_checks.py
```

---

## 10. FINAL PROJECT DEMONSTRATION

### Objective
The objective of this project is to guarantee that the **SafeBook Hospital Appointment Platform** never tolerates double bookings, race condition duplicates, or retry duplicates under concurrent patient load or network re-transmissions.

### Core Architecture
- **Baseline Mode:** Vulnerable check-then-insert execution flow exposing Time-of-Check to Time-of-Use (TOCTOU) race windows.
- **Protected Prototype:** Employs atomic SQLite `BEGIN IMMEDIATE TRANSACTION` write locks, database `UNIQUE (doctor_id, appointment_date, appointment_time)` constraints, client `idempotency_key` cache deduplication, request lifecycle tracing, transaction rollback visibility, and non-specialist rule-based decision explanations.

### Patient & Hospital Staff Workflows
- **Patient Workflow:** 8-step visual workflow (`Select Doctor` → `Select Date` → `Select Time Slot` → `Enter Details` → `Idempotency Key` → `Validation` → `Atomic Lock` → `Confirmation/Fallback`). Displays booking status, appointment ID, human explanation, and quick retry actions.
- **Hospital Staff / Admin Role:** Comprehensive control center offering filtering by status/mode, detailed appointment logs, dynamic business rules configuration (`MAX_RETRIES`, `SLOT_CONFLICT_POLICY`), request trace pipeline visualizer, transaction event logs, and operational telemetry.

### Key Capabilities Summary
1. **Idempotency Deduplication:** Re-sent requests with matching key return cached appointment without inserting duplicate DB rows.
2. **Concurrency Protection:** Simultaneous requests targeting identical slots trigger SQLite UNIQUE constraint, ensuring 1 confirmed booking and N-1 safe HTTP 409 rejections.
3. **Request Tracing:** Audit pipeline recording `request_id`, execution steps (`REQUEST_RECEIVED` → ... → `RESPONSE_GENERATED`), duration, and transaction state (`COMMITTED` / `ROLLED_BACK`).
4. **Transparent Explanations:** Non-technical explanations (`SLOT_AVAILABLE`, `IDEMPOTENT_RETRY_MATCH`, `RACE_CONDITION_PREVENTED`) explaining rule-based decisions.
5. **Admin Monitoring Dashboard:** Live cards and visual CSS comparison bars comparing Baseline vs Protected performance.
6. **API Integration & Inspector:** Interactive tester executing live HTTP 200 (Success), HTTP 400 (Validation Error), and HTTP 409 (Conflict) payloads.
7. **Guided End-to-End Demo Mode:** Prominent `▶ Launch Automated End-to-End Demo` running all 13 demonstration steps sequentially live in the browser UI.

### Measured Results & Evidence
- **Verification Suite (`python run_verification_suite.py`):** 10/10 validation cases passed (100.0% duplicate prevention rate, 0 duplicate records in Protected Mode).
- **Final Demonstration Checks (`python run_final_demo_checks.py`):** 9/9 final demo checks passed (100.0% success rate).

### How to Demonstrate
1. Start application: `python -m uvicorn app.main:app --port 8000`
2. Open `http://127.0.0.1:8000` in browser.
3. Click **▶ L. End-to-End Demo** tab in top navbar.
4. Click **▶ Launch Automated End-to-End Demo** button to run live 13-step demonstration sequence.
5. Inspect **📈 D. Monitoring Dashboard** and **🔍 F. Request Traces** for live telemetry.

