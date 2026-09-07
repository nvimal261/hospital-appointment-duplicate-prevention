"""
Protected Booking Handler (Idempotent & Concurrency Safe).
Employs Idempotency Keys, SQLite Immediate Transactions, and Database Unique Constraints.
"""

import asyncio
import time
import uuid
import sqlite3
from datetime import datetime
from typing import Dict, Any, Tuple

from app.database import get_db_connection
from app.models import AppointmentCreate
from app.config import get_config

async def handle_protected_booking(request_data: AppointmentCreate, test_type: str = "manual") -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    """
    Executes the protected booking workflow:
    1. Idempotency Check: Returns cached booking if idempotency_key matches existing record.
    2. Concurrency Control: Uses SQLite atomic insert inside immediate transaction with UNIQUE constraint.
    """
    config = get_config()
    start_time = time.time()
    req_id = f"REQ-PROT-{uuid.uuid4().hex[:8].upper()}"

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
                        "message": "Returned existing appointment via idempotency key retry."
                    }

                    trace_info = {
                        "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                        "request_id": req_id,
                        "mode": "protected",
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
                        "explanation": f"Idempotent retry recognized! Key '{request_data.idempotency_key}' already has booking {existing['appointment_id']}. System safely returned existing booking without creating duplicates."
                    }
                    return 200, response_payload, trace_info
                else:
                    # Previous attempt failed; remove failed record so retry can succeed
                    cursor.execute("DELETE FROM protected_appointments WHERE idempotency_key = ?;", (request_data.idempotency_key,))
                    conn.commit()
        finally:
            conn.close()

    # Step 2: Attempt Atomic Protected Insert with Concurrency Transaction Control
    new_app_id = f"APP-PROT-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now().isoformat()

    # Optional processing delay simulation
    if config.SIMULATED_PROCESSING_DELAY_MS > 0:
        await asyncio.sleep(config.SIMULATED_PROCESSING_DELAY_MS / 1000.0)

    conn = get_db_connection()
    try:
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
            except sqlite3.IntegrityError as err:
                conn.rollback()
                end_time = time.time()
                duration_ms = round((end_time - start_time) * 1000, 2)
                err_str = str(err).lower()

                # Check if idempotency constraint failed or unique slot constraint failed
                if "idempotency_key" in err_str and request_data.idempotency_key:
                    cursor.execute("SELECT * FROM protected_appointments WHERE idempotency_key = ?;", (request_data.idempotency_key,))
                    rec = cursor.fetchone()
                    if rec:
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
                            "message": "Returned existing appointment via idempotency key."
                        }
                        trace_info = {
                            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                            "request_id": req_id,
                            "mode": "protected",
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
                            "explanation": f"Concurrent retry with key '{request_data.idempotency_key}' hit DB constraint and safely returned existing appointment."
                        }
                        return 200, response_payload, trace_info

                # Slot Conflict handling
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
                    "message": "Appointment slot is already booked. Please select another date/time."
                }
                trace_info = {
                    "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                    "request_id": req_id,
                    "mode": "protected",
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
                    "explanation": f"CONCURRENCY RACE PREVENTED! Slot ({request_data.doctor_id} on {request_data.appointment_date} at {request_data.appointment_time}) was claimed by another request. Database unique constraint rejected duplicate booking."
                }
                return 409, response_payload, trace_info
        else:
            # Fallback if protection disabled in config
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

        end_time = time.time()
        duration_ms = round((end_time - start_time) * 1000, 2)

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
            "message": "Appointment successfully booked."
        }

        trace_info = {
            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
            "request_id": req_id,
            "mode": "protected",
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
            "explanation": f"Protected booking created appointment {new_app_id} successfully for slot {request_data.appointment_date} {request_data.appointment_time}."
        }

        return 200, response_payload, trace_info

    except Exception as ex:
        conn.rollback()
        end_time = time.time()
        duration_ms = round((end_time - start_time) * 1000, 2)
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
            "message": f"Booking could not be completed: {str(ex)}"
        }
        trace_info = {
            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
            "request_id": req_id,
            "mode": "protected",
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
            "explanation": f"Unhandled error during protected booking: {str(ex)}"
        }
        return 500, response_payload, trace_info
    finally:
        conn.close()
