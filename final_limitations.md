# Final System Limitations Document
## SafeBook Hospital Appointment Platform

### Overview
The **SafeBook Hospital Appointment Platform** successfully demonstrates concurrency race protection, idempotency deduplication, request tracing, rule-based decision explanations, and monitoring telemetry. 

While the prototype achieves a **100.0% duplicate prevention rate** in synthetic benchmarks and verification suites, realistic technical and operational limitations of the current prototype implementation are documented below.

---

### 1. Architectural & Database Limitations
* **Local SQLite Database:** The prototype uses SQLite (`hospital_appointments.db`) with `BEGIN IMMEDIATE TRANSACTION` locks. While highly efficient for single-instance applications, multi-node cloud deployments require distributed lock managers (e.g., PostgreSQL `SELECT FOR UPDATE`, Redis Redlock, or Amazon DynamoDB conditional writes).
* **Single-Process Execution:** The current application runs on a single FastAPI worker instance. Distributed environments require distributed tracing headers (e.g., OpenTelemetry trace contexts).

---

### 2. Operational & Security Scope Limitations
* **Demonstration-Level Authentication:** Role switching (Patient vs Hospital Staff / Admin) is implemented as a client-side demonstration switcher. Production deployments require secure OAuth2 / OpenID Connect JWT token authentication with Role-Based Access Control (RBAC).
* **No Real EMR Integration:** The system operates standalone and is NOT connected to live Electronic Medical Record (EMR) or Hospital Information Systems (HIS) such as Epic, Cerner, or FHIR APIs.

---

### 3. Testing & Workload Scope Limitations
* **Synthetic Workloads:** Performance metrics were gathered using synthetic benchmarks (60-item workload and 10x concurrent race tests). Multi-region load testing under thousands of requests per second was not performed.
* **Network Latency Simulation:** Concurrency race windows were evaluated using simulated millisecond processing delays (`SIMULATED_PROCESSING_DELAY_MS`). Real-world network jitter and database connection pool contention may introduce additional latency dynamics.

---

### 4. Non-Clinical Governance Scope
* **No Medical Triage or Diagnosis:** The system handles appointment slot allocation ONLY. It does NOT evaluate clinical urgency, triage medical conditions, or provide medical advice.

---

### 5. Recommended Next Steps for Production Readiness
1. **Database Migration:** Migrate SQLite schema to PostgreSQL with row-level locking.
2. **Authentication Infrastructure:** Implement OAuth2 / JWT authentication with HTTPS transport security.
3. **Production Load Testing:** Perform distributed load testing with tools like Locust or k6.
4. **FHIR / EMR Integration:** Integrate standard HL7 FHIR scheduling APIs.

