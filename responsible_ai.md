# Responsible AI & Governance Documentation
## SafeBook Hospital Appointment Platform

### 1. Purpose of Automation
The **SafeBook Hospital Appointment Platform** automates appointment scheduling, conflict resolution, idempotency deduplication, and concurrency safety. The core objective of this system is to prevent double-booking incidents and ensure that appointment availability records remain strictly consistent under high concurrent traffic and network retries.

---

### 2. Decision System Boundaries

#### What the System Decides (Automated System Scope)
* **Slot Availability:** Determines if a specified doctor, appointment date, and time slot is currently unreserved.
* **Idempotency Deduplication:** Checks incoming requests against client idempotency keys (`idempotency_key`) to recognize retries and return previous booking records without creating duplicate database rows.
* **Concurrency Locking:** Executes atomic SQLite `BEGIN IMMEDIATE TRANSACTION` operations and enforces `UNIQUE (doctor_id, appointment_date, appointment_time)` schema constraints to reject competing simultaneous requests.
* **Retry Counter Validation:** Validates `retry_number` against configured `MAX_RETRIES` policy parameters.

#### What the System Does NOT Decide (Explicit Non-Scope)
* ❌ **No Clinical Decisions:** The system does NOT perform clinical triage, assess medical urgency, or prioritize patients based on medical conditions.
* ❌ **No Medical Diagnoses:** The system does NOT render medical opinions, symptom assessments, or treatment recommendations.
* ❌ **No Doctor Schedule Manipulation:** The system does NOT alter physician working hours, override doctor leave, or adjust appointment durations based on medical complexity.

---

### 3. Rule-Based Decision Logic
All system decisions are governed by **100% deterministic, rule-based backend algorithms**. No non-deterministic machine learning model, probabilistic inference engine, or LLM AI agent is used to decide whether an appointment is booked or rejected.

Decision criteria are transparently defined:
1. `SLOT_AVAILABLE`: Slot exists and no database lock violation occurs -> Booking **CONFIRMED** (HTTP 200).
2. `IDEMPOTENT_RETRY_MATCH`: Request matches existing idempotency key -> Cached Record **RETURNED** (HTTP 200).
3. `RACE_CONDITION_PREVENTED`: Concurrent request attempts to write to locked slot -> Request **REJECTED** (HTTP 409).
4. `RETRY_LIMIT_EXCEEDED`: Retry counter exceeds system configuration -> Request **REJECTED** (HTTP 400).
5. `INVALID_INPUT_DATA`: Request missing required fields or malformed date -> Request **REJECTED** (HTTP 400).

---

### 4. Transparent Explanation Layer
Every appointment response payload includes a non-specialist, human-readable explanation designed for hospital staff and patients.

Example explanations:
* **Slot Available:** *"Appointment confirmed because the requested doctor slot was available."*
* **Idempotent Match:** *"This request was already processed. The existing appointment was returned instead of creating another record."*
* **Concurrency Conflict:** *"Another request reserved this slot first. This request was rejected to prevent double booking."*

No response claims that an "AI model made the decision." All explanations describe the exact rule-based database outcome.

---

### 5. Fallback & Human Oversight
When a conflict or rejection occurs, the system automatically provides fallback recommendations:
* Alternative available time slots for the same doctor.
* Alternative available doctors for the same date.
* Actionable next steps (e.g., retrying with a fresh key or contacting front-desk reception).

Hospital staff maintain full human oversight through the **Hospital Staff & Admin Control Center**, allowing manual overrides, trace auditing, and patient support when required.

---

### 6. Limitations & Disclaimer
* **Prototype Demonstration:** This software is a reliability demonstration prototype for concurrency control and duplicate prevention algorithms.
* **Not Medical Advice:** This application is NOT certified for direct clinical diagnosis or triage.
* **Demonstration Environment:** Authentication and roles are provided for demonstration purposes.

