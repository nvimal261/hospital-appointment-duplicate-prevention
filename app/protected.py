"""
Protected Booking Handler (Idempotent & Concurrency Safe).
Employs Idempotency Keys, SQLite Immediate Transactions, Database Unique Constraints,
Request Tracing, Retry Tracking, and Non-Specialist Explanation Layer.
"""

import asyncio
import time
import uuid
import sqlite3
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

from app.database import get_db_connection
from app.models import AppointmentCreate
from app.config import get_config
from app.retry_tracker import record_retry_event
from app.explanation import generate_explanation

def find_alternative_slots(doctor_id: str, appointment_date: str, current_time: str) -> List[Dict[str, str]]:
    """Helper to query available alternate appointment slots for fallback suggestion."""
    potential_times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00", "15:30"]
    alternatives = []
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT appointment_time FROM protected_appointments
            WHERE doctor_id = ? AND appointment_date = ? AND booking_status = 'CONFIRMED';
        """, (doctor_id, appointment_date))
        booked_times = {row["appointment_time"] for row in cursor.fetchall()}

        for t in potential_times:
            if t != current_time and t not in booked_times:
                alternatives.append({
                    "doctor_id": doctor_id,
                    "appointment_date": appointment_date,
                    "appointment_time": t
                })
                if len(alternatives) >= 3:
                    break
    except Exception:
        pass
    finally:
        conn.close()

    # If no alternate times for same doctor, suggest alternate doctor
    if not alternatives:
        alternatives.append({
            "doctor_id": "DOC-GENERAL-05",
            "appointment_date": appointment_date,
            "appointment_time": "14:30"
        })
    return alternatives

async def handle_protected_booking(request_data: AppointmentCreate, test_type: str = "manual") -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    """
    Executes the protected booking workflow:
    1. Check retry limit against MAX_RETRIES.
    2. Idempotency Check: Returns cached booking if idempotency_key matches existing record.
    3. Concurrency Control: Uses SQLite atomic insert inside immediate transaction with UNIQUE constraint.
    4. Records Request Trace, Retry Events, and human-readable explanation layer payload.
    """
    config = get_config()
    start_time = time.time()
    req_id = f"REQ-PROT-{uuid.uuid4().hex[:8].upper()}"
    role = getattr(request_data, "role", "Patient") or "Patient"

    steps = ["REQUEST_RECEIVED", "VALIDATION"]

    # Step 0: Check MAX_RETRIES limit
    if request_data.retry_number > config.MAX_RETRIES:
        end_time = time.time()
        duration_ms = round((end_time - start_time) * 1000, 2)
        steps.extend(["TRANSACTION_ROLLBACK", "RESPONSE_GENERATED"])
        
        explanation_obj = generate_explanation(
            status="REJECTED",
            reason_code="RETRY_LIMIT_EXCEEDED",
            custom_message=f"Maximum retry limit ({config.MAX_RETRIES}) exceeded for attempt #{request_data.retry_number}.",
            request_id=req_id,
            mode="protected"
        )
        
        record_retry_event(
            request_id=req_id,
            original_request_id=req_id,
            retry_number=request_data.retry_number,
            idempotency_key=request_data.idempotency_key,
            retry_reason="MAX_RETRIES_EXCEEDED",
            result="Rejected: Retry count exceeds maximum system policy"
        )

        response_payload = {
            "appointment_id": "",
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "idempotency_key": request_data.idempotency_key,
            "booking_status": "REJECTED",
            "mode": "protected",
            "created_at": datetime.now().isoformat(),
            "message": explanation_obj["human_readable_explanation"],
            "request_id": req_id,
            "status": "REJECTED",
            "reason_code": explanation_obj["reason_code"],
            "human_readable_explanation": explanation_obj["human_readable_explanation"],
            "fallback_actions": explanation_obj["fallback_actions"],
            "alternative_slots": []
        }

        trace_info = {
            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
            "request_id": req_id,
            "mode": "protected",
            "role": role,
            "test_type": test_type,
            "idempotency_key": request_data.idempotency_key,
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "request_start_time": start_time,
            "request_end_time": end_time,
            "duration_ms": duration_ms,
            "retry_number": request_data.retry_number,
            "success": False,
            "response_status": 400,
            "database_result": "RETRY_LIMIT_EXCEEDED",
            "transaction_status": "REJECTED",
            "duplicate_detected": 0,
            "duplicate_prevented": 0,
            "error_message": "Exceeded MAX_RETRIES configuration limit",
            "steps": " -> ".join(steps),
            "explanation": explanation_obj["human_readable_explanation"]
        }
        return 400, response_payload, trace_info

    steps.append("IDEMPOTENCY_CHECK")

    # Step 1: Idempotency Key Lookup (if enabled and key provided)
    if config.ENABLE_IDEMPOTENCY and request_data.idempotency_key:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM protected_appointments WHERE idempotency_key = ?;", (request_data.idempotency_key,))
            existing = cursor.fetchone()

            if existing:
                if existing["booking_status"] == "CONFIRMED":
                    end_time = time.time()
                    duration_ms = round((end_time - start_time) * 1000, 2)
                    steps.extend(["TRANSACTION_COMMIT", "RESPONSE_GENERATED"])
                    
                    explanation_obj = generate_explanation(
                        status="CONFIRMED",
                        reason_code="IDEMPOTENT_RETRY_MATCH",
                        custom_message=f"Idempotent retry recognized! Key '{request_data.idempotency_key}' already has booking {existing['appointment_id']}. System safely returned existing booking without creating duplicates.",
                        request_id=req_id,
                        mode="protected"
                    )

                    record_retry_event(
                        request_id=req_id,
                        original_request_id=existing["appointment_id"],
                        retry_number=request_data.retry_number,
                        idempotency_key=request_data.idempotency_key,
                        retry_reason="Duplicate request detected with matching key",
                        result=f"Returned existing appointment {existing['appointment_id']}"
                    )

                    response_payload = {
                        "appointment_id": existing["appointment_id"],
                        "patient_id": existing["patient_id"],
                        "doctor_id": existing["doctor_id"],
                        "appointment_date": existing["appointment_date"],
                        "appointment_time": existing["appointment_time"],
                        "idempotency_key": existing["idempotency_key"],
                        "booking_status": existing["booking_status"],
                        "mode": "protected",
                        "created_at": existing["created_at"],
                        "message": "Returned existing appointment via idempotency key retry.",
                        "request_id": req_id,
                        "status": "CONFIRMED",
                        "reason_code": "IDEMPOTENT_RETRY_MATCH",
                        "human_readable_explanation": explanation_obj["human_readable_explanation"],
                        "fallback_actions": [],
                        "alternative_slots": []
                    }

                    trace_info = {
                        "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                        "request_id": req_id,
                        "mode": "protected",
                        "role": role,
                        "test_type": test_type,
                        "idempotency_key": request_data.idempotency_key,
                        "patient_id": request_data.patient_id,
                        "doctor_id": request_data.doctor_id,
                        "appointment_date": request_data.appointment_date,
                        "appointment_time": request_data.appointment_time,
                        "request_start_time": start_time,
                        "request_end_time": end_time,
                        "duration_ms": duration_ms,
                        "retry_number": request_data.retry_number,
                        "success": True,
                        "response_status": 200,
                        "database_result": "RETURNED_IDEMPOTENT",
                        "transaction_status": "COMMITTED",
                        "duplicate_detected": 1,
                        "duplicate_prevented": 1,
                        "error_message": "",
                        "steps": " -> ".join(steps),
                        "explanation": explanation_obj["human_readable_explanation"]
                    }
                    return 200, response_payload, trace_info
                else:
                    # Previous attempt failed; remove failed record so retry can succeed
                    cursor.execute("DELETE FROM protected_appointments WHERE idempotency_key = ?;", (request_data.idempotency_key,))
                    conn.commit()
        finally:
            conn.close()

    steps.append("SLOT_CHECK")

    # Step 2: Attempt Atomic Protected Insert with Concurrency Transaction Control
    new_app_id = f"APP-PROT-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now().isoformat()

    if config.SIMULATED_PROCESSING_DELAY_MS > 0:
        await asyncio.sleep(config.SIMULATED_PROCESSING_DELAY_MS / 1000.0)

    conn = get_db_connection()
    try:
        steps.extend(["TRANSACTION_BEGIN", "DATABASE_OPERATION"])
        # Request immediate write lock on SQLite table
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")
        cursor = conn.cursor()

        if config.ENABLE_CONCURRENCY_PROTECTION:
            try:
                cursor.execute("""
                    INSERT INTO protected_appointments (
                        appointment_id, patient_id, doctor_id, appointment_date, appointment_time, idempotency_key, booking_status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    new_app_id,
                    request_data.patient_id,
                    request_data.doctor_id,
                    request_data.appointment_date,
                    request_data.appointment_time,
                    request_data.idempotency_key,
                    "CONFIRMED",
                    created_at
                ))
                conn.commit()
                steps.append("TRANSACTION_COMMIT")
            except sqlite3.IntegrityError as err:
                conn.rollback()
                steps.append("TRANSACTION_ROLLBACK")
                end_time = time.time()
                duration_ms = round((end_time - start_time) * 1000, 2)
                err_str = str(err).lower()

                # Check if idempotency constraint failed or unique slot constraint failed
                if "idempotency_key" in err_str and request_data.idempotency_key:
                    cursor.execute("SELECT * FROM protected_appointments WHERE idempotency_key = ?;", (request_data.idempotency_key,))
                    rec = cursor.fetchone()
                    if rec:
                        record_retry_event(
                            request_id=req_id,
                            original_request_id=rec["appointment_id"],
                            retry_number=request_data.retry_number,
                            idempotency_key=request_data.idempotency_key,
                            retry_reason="Concurrent duplicate request hit DB key constraint",
                            result=f"Returned existing appointment {rec['appointment_id']}"
                        )
                        explanation_obj = generate_explanation(
                            status="CONFIRMED",
                            reason_code="IDEMPOTENT_RETRY_MATCH",
                            custom_message=f"Concurrent retry with key '{request_data.idempotency_key}' hit DB constraint and safely returned existing appointment.",
                            request_id=req_id,
                            mode="protected"
                        )
                        steps.append("RESPONSE_GENERATED")
                        response_payload = {
                            "appointment_id": rec["appointment_id"],
                            "patient_id": rec["patient_id"],
                            "doctor_id": rec["doctor_id"],
                            "appointment_date": rec["appointment_date"],
                            "appointment_time": rec["appointment_time"],
                            "idempotency_key": rec["idempotency_key"],
                            "booking_status": rec["booking_status"],
                            "mode": "protected",
                            "created_at": rec["created_at"],
                            "message": "Returned existing appointment via idempotency key.",
                            "request_id": req_id,
                            "status": "CONFIRMED",
                            "reason_code": "IDEMPOTENT_RETRY_MATCH",
                            "human_readable_explanation": explanation_obj["human_readable_explanation"],
                            "fallback_actions": [],
                            "alternative_slots": []
                        }
                        trace_info = {
                            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                            "request_id": req_id,
                            "mode": "protected",
                            "role": role,
                            "test_type": test_type,
                            "idempotency_key": request_data.idempotency_key,
                            "patient_id": request_data.patient_id,
                            "doctor_id": request_data.doctor_id,
                            "appointment_date": request_data.appointment_date,
                            "appointment_time": request_data.appointment_time,
                            "request_start_time": start_time,
                            "request_end_time": end_time,
                            "duration_ms": duration_ms,
                            "retry_number": request_data.retry_number,
                            "success": True,
                            "response_status": 200,
                            "database_result": "RETURNED_IDEMPOTENT",
                            "transaction_status": "COMMITTED",
                            "duplicate_detected": 1,
                            "duplicate_prevented": 1,
                            "error_message": "",
                            "steps": " -> ".join(steps),
                            "explanation": explanation_obj["human_readable_explanation"]
                        }
                        return 200, response_payload, trace_info

                # Slot Conflict handling with Fallback suggestion workflow
                alternatives = find_alternative_slots(
                    request_data.doctor_id,
                    request_data.appointment_date,
                    request_data.appointment_time
                ) if config.SLOT_CONFLICT_POLICY in ("FALLBACK", "REJECT", "RETRY") else []

                explanation_msg = (
                    f"CONCURRENCY RACE PREVENTED! Slot ({request_data.doctor_id} on "
                    f"{request_data.appointment_date} at {request_data.appointment_time}) was claimed by another request. "
                    f"Database unique constraint rejected duplicate booking."
                )

                explanation_obj = generate_explanation(
                    status="REJECTED",
                    reason_code="RACE_CONDITION_PREVENTED",
                    custom_message=explanation_msg,
                    request_id=req_id,
                    mode="protected",
                    available_alternatives=alternatives
                )

                steps.append("RESPONSE_GENERATED")
                response_payload = {
                    "appointment_id": "",
                    "patient_id": request_data.patient_id,
                    "doctor_id": request_data.doctor_id,
                    "appointment_date": request_data.appointment_date,
                    "appointment_time": request_data.appointment_time,
                    "idempotency_key": request_data.idempotency_key,
                    "booking_status": "REJECTED",
                    "mode": "protected",
                    "created_at": created_at,
                    "message": "Appointment slot is already booked. Please select another date/time.",
                    "request_id": req_id,
                    "status": "REJECTED",
                    "reason_code": "RACE_CONDITION_PREVENTED",
                    "human_readable_explanation": explanation_msg,
                    "fallback_actions": explanation_obj["fallback_actions"],
                    "alternative_slots": alternatives
                }
                trace_info = {
                    "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                    "request_id": req_id,
                    "mode": "protected",
                    "role": role,
                    "test_type": test_type,
                    "idempotency_key": request_data.idempotency_key,
                    "patient_id": request_data.patient_id,
                    "doctor_id": request_data.doctor_id,
                    "appointment_date": request_data.appointment_date,
                    "appointment_time": request_data.appointment_time,
                    "request_start_time": start_time,
                    "request_end_time": end_time,
                    "duration_ms": duration_ms,
                    "retry_number": request_data.retry_number,
                    "success": False,
                    "response_status": 409,
                    "database_result": "SLOT_CONFLICT_REJECTED",
                    "transaction_status": "ROLLED_BACK",
                    "duplicate_detected": 1,
                    "duplicate_prevented": 1,
                    "error_message": "SQLite UNIQUE slot constraint violation",
                    "steps": " -> ".join(steps),
                    "explanation": explanation_msg
                }
                return 409, response_payload, trace_info
        else:
            # Protection disabled
            cursor.execute("""
                INSERT INTO protected_appointments (
                    appointment_id, patient_id, doctor_id, appointment_date, appointment_time, idempotency_key, booking_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                new_app_id,
                request_data.patient_id,
                request_data.doctor_id,
                request_data.appointment_date,
                request_data.appointment_time,
                request_data.idempotency_key,
                "CONFIRMED",
                created_at
            ))
            conn.commit()
            steps.append("TRANSACTION_COMMIT")

        end_time = time.time()
        duration_ms = round((end_time - start_time) * 1000, 2)
        steps.append("RESPONSE_GENERATED")

        explanation_obj = generate_explanation(
            status="CONFIRMED",
            reason_code="SLOT_AVAILABLE",
            custom_message=f"Protected booking created appointment {new_app_id} successfully for slot {request_data.appointment_date} {request_data.appointment_time}.",
            request_id=req_id,
            mode="protected"
        )

        response_payload = {
            "appointment_id": new_app_id,
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "idempotency_key": request_data.idempotency_key,
            "booking_status": "CONFIRMED",
            "mode": "protected",
            "created_at": created_at,
            "message": "Appointment successfully booked.",
            "request_id": req_id,
            "status": "CONFIRMED",
            "reason_code": "SLOT_AVAILABLE",
            "human_readable_explanation": explanation_obj["human_readable_explanation"],
            "fallback_actions": [],
            "alternative_slots": []
        }

        trace_info = {
            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
            "request_id": req_id,
            "mode": "protected",
            "role": role,
            "test_type": test_type,
            "idempotency_key": request_data.idempotency_key,
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "request_start_time": start_time,
            "request_end_time": end_time,
            "duration_ms": duration_ms,
            "retry_number": request_data.retry_number,
            "success": True,
            "response_status": 200,
            "database_result": "INSERTED",
            "transaction_status": "COMMITTED",
            "duplicate_detected": 0,
            "duplicate_prevented": 0,
            "error_message": "",
            "steps": " -> ".join(steps),
            "explanation": explanation_obj["human_readable_explanation"]
        }

        return 200, response_payload, trace_info

    except Exception as ex:
        conn.rollback()
        steps.extend(["TRANSACTION_ROLLBACK", "RESPONSE_GENERATED"])
        end_time = time.time()
        duration_ms = round((end_time - start_time) * 1000, 2)
        
        explanation_obj = generate_explanation(
            status="FAILED",
            reason_code="TRANSACTION_ROLLED_BACK",
            custom_message=f"Booking could not be safely completed: {str(ex)}",
            request_id=req_id,
            mode="protected"
        )

        response_payload = {
            "appointment_id": "",
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "idempotency_key": request_data.idempotency_key,
            "booking_status": "FAILED",
            "mode": "protected",
            "created_at": created_at,
            "message": f"Booking could not be completed: {str(ex)}",
            "request_id": req_id,
            "status": "FAILED",
            "reason_code": "TRANSACTION_ROLLED_BACK",
            "human_readable_explanation": explanation_obj["human_readable_explanation"],
            "fallback_actions": explanation_obj["fallback_actions"],
            "alternative_slots": []
        }
        trace_info = {
            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
            "request_id": req_id,
            "mode": "protected",
            "role": role,
            "test_type": test_type,
            "idempotency_key": request_data.idempotency_key,
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "request_start_time": start_time,
            "request_end_time": end_time,
            "duration_ms": duration_ms,
            "retry_number": request_data.retry_number,
            "success": False,
            "response_status": 500,
            "database_result": "FAILED",
            "transaction_status": "ROLLED_BACK",
            "duplicate_detected": 0,
            "duplicate_prevented": 0,
            "error_message": str(ex),
            "steps": " -> ".join(steps),
            "explanation": explanation_obj["human_readable_explanation"]
        }
        return 500, response_payload, trace_info
    finally:
        conn.close()
