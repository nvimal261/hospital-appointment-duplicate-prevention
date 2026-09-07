# Requirements Specification Document

**Project Title:** Hospital Appointment Platform — Concurrency & Duplicate Prevention Prototype  
**Scope Level:** 35% Academic / Demonstration Prototype  

---

## 📋 Requirement Compliance & Functional Matrix

| Req # | Requirement Name | Specification Details | Implementation File / Endpoint | Compliance Status |
| :--- | :--- | :--- | :--- | :---: |
| **1** | **Basic Requirements** | Patient booking screen, Appointment list screen, Admin/Staff screen, FastAPI backend, SQLite DB, Idempotency, Concurrency harness, Metrics dashboard. Role selector (Patient vs Staff). No complex auth. | [index.html](file:///c:/Users/Vimal%20N/New%20folder/static/index.html)<br>[app.js](file:///c:/Users/Vimal%20N/New%20folder/static/app.js) | ✅ Fully Implemented |
| **2** | **Appointment Data Schema** | Fields: `appointment_id`, `patient_id`, `doctor_id`, `appointment_date`, `appointment_time`, `idempotency_key`, `booking_status`, `created_at`. Unique constraint on patient+doctor+date+time. | [database.py](file:///c:/Users/Vimal%20N/New%20folder/app/database.py)<br>[models.py](file:///c:/Users/Vimal%20N/New%20folder/app/models.py) | ✅ Fully Implemented |
| **3** | **Baseline Booking Method** | Unprotected booking logic. Check slot -> simulate latency -> insert. Exposes Time-of-Check to Time-of-Use (TOCTOU) race conditions resulting in duplicate insertions under concurrent load. | [baseline.py](file:///c:/Users/Vimal%20N/New%20folder/app/baseline.py) | ✅ Fully Implemented |
| **4** | **Improved Protected Prototype** | Employs Idempotency key lookup, SQLite `BEGIN IMMEDIATE` transaction, DB UNIQUE constraint, and handles `sqlite3.IntegrityError` to safely reject conflicting slots (409 Conflict). | [protected.py](file:///c:/Users/Vimal%20N/New%20folder/app/protected.py) | ✅ Fully Implemented |
| **5** | **Configurable Rules** | Dynamic configuration settings: `MAX_RETRIES=3`, `ENABLE_IDEMPOTENCY=True`, `ENABLE_CONCURRENCY_PROTECTION=True`, `SLOT_CONFLICT_POLICY="reject"`. Exposed via API GET/POST. | [config.py](file:///c:/Users/Vimal%20N/New%20folder/app/config.py) | ✅ Fully Implemented |
| **6** | **Automated Test Harness** | Test Case 1: Normal 1 request.<br>Test Case 2: Retry 3 identical requests.<br>Test Case 3: 10 concurrent race requests.<br>Test Case 4: 60-item synthetic benchmark. | [harness.py](file:///c:/Users/Vimal%20N/New%20folder/app/harness.py) | ✅ Fully Implemented |
| **7** | **Request Traces Log** | Logs `request_id`, `idempotency_key`, `patient_id`, `doctor_id`, slot, start/end timestamps, latency, retry number, success flag, response code, DB result, explanation. | [database.py](file:///c:/Users/Vimal%20N/New%20folder/app/database.py) | ✅ Fully Implemented |
| **8** | **Metrics & Dashboard** | Calculates Total Requests, Successful Bookings, Duplicate Records Created/Prevented, Prevention Rate %, and comparative Baseline vs Protected table. | [harness.py](file:///c:/Users/Vimal%20N/New%20folder/app/harness.py)<br>[app.js](file:///c:/Users/Vimal%20N/New%20folder/static/app.js) | ✅ Fully Implemented |
| **9** | **Explanation Layer** | Plain English explanation for non-technical hospital reviewers explaining why duplicate was prevented or why baseline failed. Modal drawer inspector. | [app.js](file:///c:/Users/Vimal%20N/New%20folder/static/app.js) | ✅ Fully Implemented |
| **10** | **Failure / Edge Cases** | Handles duplicate submissions, simultaneous multi-user bookings, network retries, missing keys, and invalid date parameters with HTTP 409 / 400 error payloads. | [protected.py](file:///c:/Users/Vimal%20N/New%20folder/app/protected.py) | ✅ Fully Implemented |
| **11** | **Fallback Workflow** | Clear error response: *"Booking could not be confirmed. Please retry or contact hospital staff."* Staff role view of failed attempts. | [index.html](file:///c:/Users/Vimal%20N/New%20folder/static/index.html) | ✅ Fully Implemented |
| **12** | **Prototype Screens** | Screen 1: Booking Form.<br>Screen 2: Appointment List.<br>Screen 3: Test Dashboard & Metrics.<br>Screen 4: Staff Audit & Config. | [index.html](file:///c:/Users/Vimal%20N/New%20folder/static/index.html) | ✅ Fully Implemented |
| **13** | **REST API Endpoints** | `POST /appointments`, `GET /appointments`, `POST /tests/retry`, `POST /tests/concurrent`, `GET /tests/results`. | [main.py](file:///c:/Users/Vimal%20N/New%20folder/app/main.py) | ✅ Fully Implemented |
| **14** | **Synthetic Dataset** | 60 realistic synthetic appointment requests covering normal, retries, 10x concurrent race groups, and invalid payload edge cases. | [synthetic_data.py](file:///c:/Users/Vimal%20N/New%20folder/app/synthetic_data.py) | ✅ Fully Implemented |
| **15** | **Final Demonstration** | Interactive end-to-end flow demonstrating single booking, retry deduplication, 10x concurrent race comparison, and live metrics update. | [index.html](file:///c:/Users/Vimal%20N/New%20folder/static/index.html) | ✅ Fully Implemented |
| **16** | **Documentation** | Generation of `README.md`, `requirements.txt`, `requirements_specification.md`, and `limitations_report.md`. | Workspace Root | ✅ Fully Implemented |
