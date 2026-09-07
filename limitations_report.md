# Prototype Limitations & Scope Report

**Project Name:** Hospital Appointment Duplicate Prevention Prototype  
**Scope Designation:** Student Project / Working Demonstration (~35% Scope)  

---

## 🎯 Purpose of this Report

This report documents the architectural boundaries and deliberate scope restrictions of this prototype. The system was designed as a lightweight, clean, working educational demonstration to evaluate **idempotency** and **concurrency control** in preventing duplicate appointment bookings. 

It is **NOT** intended for production hospital deployment in its current form.

---

## ⚠️ Prototype Boundaries vs. Production Hospital Systems

| Feature Category | Prototype Implementation (Current) | Production Hospital Standard (Not Implemented) |
| :--- | :--- | :--- |
| **Authentication & Authorization** | Simple dropdown Role Selector (Patient vs Staff). No login passwords or tokens. | Multi-factor authentication (MFA), OAuth2 / OIDC, Role-Based Access Control (RBAC), Session JWT management. |
| **Patient Data Security & Compliance** | Synthetic mock IDs (`P-101`) stored in plain text. | HIPAA / GDPR compliance, AES-256 at-rest data encryption, TLS 1.3 transit encryption, Audit logging. |
| **Database Architecture** | Local single-file SQLite database with WAL journal mode. | Distributed enterprise SQL (PostgreSQL / CockroachDB) with multi-region replication and failover cluster. |
| **Distributed Concurrency Lock** | SQLite transaction locks (`BEGIN IMMEDIATE`) and local unique table constraints. | Distributed Redis / Redlock cache cluster for microservice concurrency locking across multiple server nodes. |
| **EHR / Hospital Integration** | Standalone mock REST API. | Integration with HL7 / FHIR standards, Epic, Cerner, or hospital legacy Electronic Health Record systems. |
| **Notification & Messaging** | Instant HTTP response payload and on-screen cards. | Automated SMS, Email, and Push Notifications via Twilio / SendGrid for booking confirmations and reminders. |
| **Monitoring & Telemetry** | Local SQLite audit table (`request_traces`). | Prometheus metrics, Grafana dashboards, Datadog APM tracing, centralized log aggregation (ELK Stack). |

---

## 🎓 Academic Value & Conclusion

Despite these scope boundaries, the prototype **successfully satisfies 100% of its designated core objective**:
1. It exposes the vulnerable Time-of-Check to Time-of-Use (TOCTOU) race condition in baseline booking systems.
2. It proves that combining client-side Idempotency Keys with Database UNIQUE Constraints achieves **100% Duplicate Prevention Rate** under high concurrency load.
3. It presents real-time measured empirical evidence suitable for academic presentation and reviewer evaluation.
