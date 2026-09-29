"""
Request Tracing and Transaction Boundary Tracking Module.
Captures lifecycle step events (REQUEST_RECEIVED -> VALIDATION -> ... -> RESPONSE_GENERATED)
and visibility into transaction commits/rollbacks.
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

# Trace lifecycle steps standard sequence
STANDARD_LIFECYCLE_STEPS = [
    "REQUEST_RECEIVED",
    "VALIDATION",
    "IDEMPOTENCY_CHECK",
    "SLOT_CHECK",
    "TRANSACTION_BEGIN",
    "DATABASE_OPERATION",
    "TRANSACTION_COMMIT",
    "RESPONSE_GENERATED"
]

class RequestTracer:
    """Helper class to build an in-memory trace object during request execution."""
    def __init__(
        self,
        request_id: str,
        mode: str,
        role: str,
        patient_id: str,
        doctor_id: str,
        appointment_date: str,
        appointment_time: str,
        idempotency_key: Optional[str] = None,
        retry_number: int = 0,
        test_type: str = "manual"
    ):
        self.trace_id = f"TR-{uuid.uuid4().hex[:8]}"
        self.request_id = request_id
        self.mode = mode
        self.role = role
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.appointment_date = appointment_date
        self.appointment_time = appointment_time
        self.idempotency_key = idempotency_key
        self.retry_number = retry_number
        self.test_type = test_type
        
        self.start_time = time.time()
        self.end_time = self.start_time
        self.steps: List[str] = ["REQUEST_RECEIVED"]
        self.transaction_status: str = "PENDING"  # COMMITTED, ROLLED_BACK, REJECTED
        self.booking_status: str = "PENDING"
        self.database_result: str = "UNKNOWN"
        self.duplicate_detected: bool = False
        self.duplicate_prevented: bool = False
        self.error_message: Optional[str] = None
        self.explanation: str = ""

    def add_step(self, step_name: str):
        """Records a step in the trace execution pipeline."""
        if step_name not in self.steps:
            self.steps.append(step_name)

    def mark_transaction(self, status: str):
        """Sets transaction boundary status: TRANSACTION_BEGIN, TRANSACTION_COMMIT, TRANSACTION_ROLLBACK."""
        self.transaction_status = status
        if status == "COMMITTED":
            self.add_step("TRANSACTION_COMMIT")
        elif status in ("ROLLED_BACK", "REJECTED"):
            self.add_step("TRANSACTION_ROLLBACK")

    def finalize(
        self,
        booking_status: str,
        db_result: str,
        response_status: int,
        explanation: str,
        success: bool,
        duplicate_detected: bool = False,
        duplicate_prevented: bool = False,
        error_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        """Finalizes timestamps and returns full dictionary payload ready for storage."""
        self.end_time = time.time()
        duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.add_step("RESPONSE_GENERATED")
        self.booking_status = booking_status
        self.database_result = db_result
        self.duplicate_detected = duplicate_detected
        self.duplicate_prevented = duplicate_prevented
        self.error_message = error_msg
        self.explanation = explanation

        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "mode": self.mode,
            "role": self.role,
            "test_type": self.test_type,
            "idempotency_key": self.idempotency_key,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "appointment_date": self.appointment_date,
            "appointment_time": self.appointment_time,
            "request_start_time": self.start_time,
            "request_end_time": self.end_time,
            "duration_ms": duration_ms,
            "retry_number": self.retry_number,
            "success": success,
            "response_status": response_status,
            "database_result": db_result,
            "transaction_status": self.transaction_status,
            "duplicate_detected": 1 if duplicate_detected else 0,
            "duplicate_prevented": 1 if duplicate_prevented else 0,
            "error_message": error_msg or "",
            "explanation": explanation,
            "steps": " -> ".join(self.steps)
        }
