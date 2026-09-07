"""
Baseline Booking Handler (Vulnerable to Concurrency Race Conditions).
Demonstrates the flaw of check-then-insert without concurrency locks or unique constraints.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple

from app.database import get_db_connection
from app.models import AppointmentCreate
from app.config import get_config

async def handle_baseline_booking(request_data: AppointmentCreate, test_type: str = "manual") -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    """
    Executes the baseline booking workflow:
    1. Check whether slot exists.
    2. Sleep briefly to simulate network/processing latency (expanding the race window).
    3. If no record found during check, insert appointment.
    """
    config = get_config()
    start_time = time.time()
    req_id = f"REQ-BASE-{uuid.uuid4().hex[:8].upper()}"

    # Connect to SQLite
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Step 1: Check whether the doctor appointment slot is already booked
        cursor.execute("""
            SELECT * FROM baseline_appointments 
            WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? AND booking_status = 'CONFIRMED'
        """, (
            request_data.doctor_id,
            request_data.appointment_date,
            request_data.appointment_time
        ))
        existing_slot = cursor.fetchone()

        # Step 2: Artificial delay to widen the Time-of-Check to Time-of-Use (TOCTOU) race window
        if config.SIMULATED_PROCESSING_DELAY_MS > 0:
            await asyncio.sleep(config.SIMULATED_PROCESSING_DELAY_MS / 1000.0)

        end_time = time.time()
        duration_ms = round((end_time - start_time) * 1000, 2)

        if existing_slot:
            # Slot was found during initial check
            response_payload = {
                "appointment_id": existing_slot["appointment_id"],
                "patient_id": existing_slot["patient_id"],
                "doctor_id": existing_slot["doctor_id"],
                "appointment_date": existing_slot["appointment_date"],
                "appointment_time": existing_slot["appointment_time"],
                "idempotency_key": existing_slot["idempotency_key"],
                "booking_status": "REJECTED",
                "mode": "baseline",
                "created_at": existing_slot["created_at"],
                "message": "Appointment slot is already booked."
            }
            trace_info = {
                "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
                "request_id": req_id,
                "mode": "baseline",
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
                "explanation": f"Baseline check found slot already taken for {request_data.doctor_id} on {request_data.appointment_date} {request_data.appointment_time}."
            }
            return 409, response_payload, trace_info

        # Step 3: Slot appeared available during check, so insert new appointment
        new_app_id = f"APP-BASE-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO baseline_appointments (
                appointment_id, patient_id, doctor_id, appointment_date, appointment_time, idempotency_key, booking_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

        # Check if this created a duplicate in baseline table!
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM baseline_appointments
            WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? AND booking_status = 'CONFIRMED'
        """, (
            request_data.doctor_id,
            request_data.appointment_date,
            request_data.appointment_time
        ))
        dup_count = cursor.fetchone()["cnt"]

        db_result = "DUPLICATE_INSERTED" if dup_count > 1 else "INSERTED"
        explanation = (
            f"RACE CONDITION DETECTED! Baseline check did not block simultaneous requests. "
            f"This request inserted duplicate appointment #{dup_count} for slot {request_data.appointment_date} {request_data.appointment_time}."
            if dup_count > 1 else
            f"Baseline inserted new appointment {new_app_id} after checking slot."
        )

        response_payload = {
            "appointment_id": new_app_id,
            "patient_id": request_data.patient_id,
            "doctor_id": request_data.doctor_id,
            "appointment_date": request_data.appointment_date,
            "appointment_time": request_data.appointment_time,
            "idempotency_key": request_data.idempotency_key,
            "booking_status": "CONFIRMED",
            "mode": "baseline",
            "created_at": created_at,
            "message": "Appointment successfully booked (Baseline Mode)."
        }

        trace_info = {
            "trace_id": f"TR-{uuid.uuid4().hex[:8]}",
            "request_id": req_id,
            "mode": "baseline",
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
            "response_status": 200 if dup_count == 1 else 201,
            "database_result": db_result,
            "explanation": explanation
        }

        return (200 if dup_count == 1 else 201), response_payload, trace_info

    finally:
        conn.close()
