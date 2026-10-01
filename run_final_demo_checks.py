"""
Final Verification & Demonstration Test Suite.
Verifies all 9 final-demo checks required for the final 30% project completion:
1. Patient booking workflow
2. Admin dashboard & metrics calculation
3. Role switching & staff data listing
4. Request trace retrieval & steps format
5. Explanation display & catalog
6. API responses for HTTP 200, HTTP 400, and HTTP 409
7. Baseline vs protected comparative metrics calculation
8. Responsible-AI documentation presence & content
9. Final requirements checklist presence & PASS status
"""

import asyncio
import os
import httpx
from app.main import app
from app.database import init_db, reset_database

async def run_final_checks():
    print("================================================================================")
    print("         FINAL DEMONSTRATION & VERIFICATION CHECKS (FINAL 30% SCOPE)           ")
    print("================================================================================")

    init_db()
    reset_database()

    total_checks = 9
    passed_checks = 0
    failed_checks = 0

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # ------------------------------------------------------------------------------
        # CHECK 1: Patient Booking Workflow (HTTP 200)
        # ------------------------------------------------------------------------------
        try:
            req_data = {
                "patient_id": "P-FINAL-101",
                "doctor_id": "DOC-CARDIOLOGY-01",
                "appointment_date": "2026-11-10",
                "appointment_time": "09:00",
                "idempotency_key": "IDEM-FINAL-KEY-101",
                "retry_number": 0,
                "role": "Patient"
            }
            res = await client.post("/api/appointments?mode=protected", json=req_data)
            data = res.json()
            if res.status_code == 200 and data.get("booking_status") == "CONFIRMED" and data.get("appointment_id"):
                passed_checks += 1
                print(f"[CHECK 1] Patient Booking Workflow            | Status: HTTP {res.status_code} ({data['booking_status']}) -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 1] Patient Booking Workflow            | Unexpected response: {res.status_code} {data} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 1] Patient Booking Workflow            | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 2: Admin Dashboard & Telemetry
        # ------------------------------------------------------------------------------
        try:
            res_m = await client.get("/api/metrics")
            data_m = res_m.json()
            if res_m.status_code == 200 and "protected" in data_m and "baseline" in data_m:
                passed_checks += 1
                print(f"[CHECK 2] Admin Dashboard Telemetry API      | Status: HTTP {res_m.status_code} -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 2] Admin Dashboard Telemetry API      | Response: {res_m.status_code} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 2] Admin Dashboard Telemetry API      | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 3: Role Switching & Staff Data Listing
        # ------------------------------------------------------------------------------
        try:
            res_apps = await client.get("/api/appointments")
            apps = res_apps.json()
            if res_apps.status_code == 200 and isinstance(apps, list) and len(apps) > 0:
                passed_checks += 1
                print(f"[CHECK 3] Staff View Data Retrieval          | Status: HTTP {res_apps.status_code} ({len(apps)} records) -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 3] Staff View Data Retrieval          | Response: {res_apps.status_code} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 3] Staff View Data Retrieval          | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 4: Request Trace System & Steps Formatting
        # ------------------------------------------------------------------------------
        try:
            res_tr = await client.get("/api/traces")
            traces = res_tr.json()
            if res_tr.status_code == 200 and isinstance(traces, list) and len(traces) > 0 and "steps" in traces[0]:
                passed_checks += 1
                print(f"[CHECK 4] Request Trace System               | Status: HTTP {res_tr.status_code} (Steps: {traces[0]['steps'][:30]}...) -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 4] Request Trace System               | Response: {res_tr.status_code} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 4] Request Trace System               | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 5: Decision Explanation Layer Display
        # ------------------------------------------------------------------------------
        try:
            from app.explanation import generate_explanation
            exp = generate_explanation("CONFIRMED", "SLOT_AVAILABLE")
            if exp.get("reason_code") == "SLOT_AVAILABLE" and exp.get("human_readable_explanation"):
                passed_checks += 1
                print(f"[CHECK 5] Decision Explanation Layer Display | Reason Code: {exp['reason_code']} -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 5] Decision Explanation Layer Display | Invalid payload: {exp} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 5] Decision Explanation Layer Display | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 6: API Integration Responses (HTTP 200, HTTP 400, HTTP 409)
        # ------------------------------------------------------------------------------
        try:
            # 200 OK tested in Check 1
            # 400 Validation
            res_400 = await client.post("/api/appointments?mode=protected", json={"patient_id": "", "doctor_id": "DOC-1", "appointment_date": "INVALID", "appointment_time": "10:00"})
            # 409 Conflict (Patient B books Patient A's slot)
            res_409 = await client.post("/api/appointments?mode=protected", json={
                "patient_id": "P-FINAL-102",
                "doctor_id": "DOC-CARDIOLOGY-01",
                "appointment_date": "2026-11-10",
                "appointment_time": "09:00",
                "idempotency_key": "IDEM-FINAL-KEY-DIFF",
                "retry_number": 0,
                "role": "Patient"
            })
            if res_400.status_code == 400 and res_409.status_code == 409:
                passed_checks += 1
                print(f"[CHECK 6] API Integration Responses          | HTTP 200, 400, 409 Verified -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 6] API Integration Responses          | Got 400: {res_400.status_code}, 409: {res_409.status_code} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 6] API Integration Responses          | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 7: Baseline vs Protected Metrics Comparative Calculation
        # ------------------------------------------------------------------------------
        try:
            res_s = await client.post("/api/tests/synthetic")
            bench = res_s.json()
            if bench.get("protected", {}).get("prevention_rate_percent") == 100.0 and bench.get("protected", {}).get("duplicate_records_created") == 0:
                passed_checks += 1
                print(f"[CHECK 7] Baseline vs Protected Metrics      | Protected Duplicates: 0, Rate: 100.0% -> PASSED")
            else:
                failed_checks += 1
                print(f"[CHECK 7] Baseline vs Protected Metrics      | Unexpected benchmark: {bench} -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 7] Baseline vs Protected Metrics      | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 8: Responsible AI & Governance Document Presence
        # ------------------------------------------------------------------------------
        try:
            if os.path.exists("responsible_ai.md"):
                with open("responsible_ai.md", "r", encoding="utf-8") as f:
                    content = f.read()
                if "Purpose of Automation" in content and "No Clinical Decisions" in content:
                    passed_checks += 1
                    print(f"[CHECK 8] Responsible-AI Documentation       | File present & validated -> PASSED")
                else:
                    failed_checks += 1
                    print(f"[CHECK 8] Responsible-AI Documentation       | Missing key sections -> FAILED")
            else:
                failed_checks += 1
                print(f"[CHECK 8] Responsible-AI Documentation       | File missing -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 8] Responsible-AI Documentation       | Error: {ex} -> FAILED")

        # ------------------------------------------------------------------------------
        # CHECK 9: Final Requirements Checklist Presence & PASS Status
        # ------------------------------------------------------------------------------
        try:
            if os.path.exists("final_requirements_checklist.md"):
                with open("final_requirements_checklist.md", "r", encoding="utf-8") as f:
                    content = f.read()
                if "100% PASS" in content:
                    passed_checks += 1
                    print(f"[CHECK 9] Final Requirements Checklist      | File present & status PASS -> PASSED")
                else:
                    failed_checks += 1
                    print(f"[CHECK 9] Final Requirements Checklist      | Status not PASS -> FAILED")
            else:
                failed_checks += 1
                print(f"[CHECK 9] Final Requirements Checklist      | File missing -> FAILED")
        except Exception as ex:
            failed_checks += 1
            print(f"[CHECK 9] Final Requirements Checklist      | Error: {ex} -> FAILED")

    print("\n==================================================")
    print("FINAL DEMONSTRATION VERIFICATION SUMMARY")
    print("==================================================")
    print(f"Total checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {failed_checks}")
    print(f"Success Rate: {(passed_checks / total_checks) * 100:.1f}%")
    print("==================================================\n")

    if failed_checks > 0:
        raise RuntimeError(f"Final demonstration verification failed: {failed_checks} check(s) failed.")

if __name__ == "__main__":
    asyncio.run(run_final_checks())
