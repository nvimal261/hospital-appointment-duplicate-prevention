# SafeBook Hospital — Appointment Duplicate Prevention Platform

A lightweight, working prototype for a hospital appointment platform focused on **preventing duplicate appointment bookings** caused by request retries and concurrent race conditions.

---

## 🎯 Project Objective

When multiple appointment booking requests are submitted simultaneously or retried over unstable networks, standard check-then-insert backend logic often suffers from **Time-of-Check to Time-of-Use (TOCTOU)** race conditions, resulting in duplicate double-booked appointments.

This prototype demonstrates how combining **Client Idempotency Keys**, **Atomic SQLite Transactions**, and **Database Unique Constraints** prevents double-booking while comparing measured results against an unprotected baseline approach.

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│              Web Frontend (HTML5 / Vanilla JS / Glassmorphism)  │
│          - Patient Booking Screen  - Appointment List           │
│          - Staff Failed Audit      - Test Harness & Dashboard   │
└────────────────────────────────┬────────────────────────────────┘
                                 │ REST API (JSON)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Python FastAPI Backend                      │
│   ┌──────────────────────────┐   ┌──────────────────────────┐   │
│   │ Baseline Handler (Race) │   │ Protected Handler (Safe) │   │
│   └────────────┬─────────────┘   └────────────┬─────────────┘   │
└────────────────┼──────────────────────────────┼─────────────────┘
                 │ Check & Widen Delay          │ Atomic Transaction
                 ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SQLite Database WAL Mode                       │
│   - baseline_appointments (No UNIQUE Constraints)               │
│   - protected_appointments (UNIQUE: Patient+Doctor+Date+Time)   │
│   - request_traces (Millisecond Audit Log)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Setup & Execution Instructions

### Prerequisites
- Python 3.10+ installed on system.

### 1. Installation
Clone/extract project repository into local workspace directory and install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Run Backend & Frontend (Single Command)
Start the FastAPI server via Uvicorn:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
or run directly:
```bash
python -m app.main
```

### 3. Access Web Interface
Open your web browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## 🧪 How to Run Automated Concurrency & Retry Tests

### Option A: From Web Interface Dashboard
1. Open `http://127.0.0.1:8000` and click the **📊 Test Harness & Metrics** tab.
2. Click **Test 1: Normal Single Request** — Sends 1 request.
3. Click **Test 2: 3x Retry Simulation** — Sends the same request 3 times with identical `idempotency_key`.
4. Click **Test 3: 10x Concurrent Race Condition** — Sends 10 simultaneous requests targeting the identical doctor slot.
5. Click **Test 4: Run 60-Item Synthetic Benchmark** — Executes full dataset benchmark comparing Baseline vs Protected prototype.
6. Inspect measured metrics in side-by-side comparison table and click **💡 Explain** on any trace for non-technical breakdown.

### Option B: Direct API Curl Command
Run a 10x concurrent test via curl:
```bash
curl -X POST "http://127.0.0.1:8000/api/tests/concurrent?mode=protected&count=10" \
     -H "Content-Type: application/json" \
     -d "{\"patient_id\":\"P-999\",\"doctor_id\":\"DOC-CARDIOLOGY-01\",\"appointment_date\":\"2026-09-30\",\"appointment_time\":\"10:00\",\"idempotency_key\":\"IDEM-CLI-100\"}"
```

---

## 💡 Idempotency & Concurrency Protection Explained

### 1. What is Idempotency?
An operation is **idempotent** if executing it multiple times produces the exact same outcome as executing it once.
- **Problem**: On slow mobile networks, a patient clicks "Book", the backend creates the appointment, but the response drops. The client retries. Without idempotency, a second appointment row is created!
- **Protected Solution**: Each request carries a unique `idempotency_key`. The backend checks if this key was already processed. If found, it returns the cached existing appointment without inserting a duplicate.

### 2. How Concurrency Protection Works
- **Baseline Flaw**:
  ```text
  Request A → Check Slot (Free) ───────> Insert Appointment
  Request B → Check Slot (Free) ───────> Insert Appointment  <-- DOUBLE BOOKING!
  ```
- **Protected Implementation**:
  ```text
  Request A & B → SQLite BEGIN IMMEDIATE TRANSACTION
  Request A → INSERT INTO protected_appointments (UNIQUE constraint) → SUCCEEDED (200 OK)
  Request B → INSERT INTO protected_appointments (UNIQUE constraint) → IntegrityError Caught → REJECTED (409 Conflict)
  ```

---

## 📊 Measured Prevention Rate Formula

$$\text{Duplicate Prevention Rate (\%)} = \left( \frac{\text{Duplicates Prevented}}{\text{Duplicates Prevented} + \text{Duplicate Records Created}} \right) \times 100$$
