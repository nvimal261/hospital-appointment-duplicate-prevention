"""
Pydantic data models for the Hospital Appointment Platform.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AppointmentCreate(BaseModel):
    patient_id: str = Field(..., example="P-101", description="Unique Patient Identifier")
    doctor_id: str = Field(..., example="DOC-01", description="Doctor Identifier")
    appointment_date: str = Field(..., example="2026-09-10", description="Date YYYY-MM-DD")
    appointment_time: str = Field(..., example="10:00", description="Time HH:MM (24h format)")
    idempotency_key: Optional[str] = Field(None, description="Unique client key for retries")
    retry_number: int = Field(0, description="Attempt number for retries")

class AppointmentResponse(BaseModel):
    appointment_id: str
    patient_id: str
    doctor_id: str
    appointment_date: str
    appointment_time: str
    idempotency_key: Optional[str] = None
    booking_status: str  # CONFIRMED, REJECTED, FAILED
    mode: str            # baseline, protected
    created_at: str
    message: Optional[str] = None

class RequestTrace(BaseModel):
    trace_id: str
    request_id: str
    mode: str                     # baseline or protected
    test_type: str                # normal, retry, concurrent, synthetic
    idempotency_key: Optional[str]
    patient_id: str
    doctor_id: str
    appointment_date: str
    appointment_time: str
    request_start_time: float     # timestamp in seconds
    request_end_time: float       # timestamp in seconds
    duration_ms: float
    retry_number: int
    success: bool
    response_status: int          # HTTP Status Code
    database_result: str          # INSERTED, RETURNED_IDEMPOTENT, SLOT_CONFLICT_REJECTED, DUPLICATE_INSERTED
    explanation: str

class ComparativeMetrics(BaseModel):
    baseline: Dict[str, Any]
    protected: Dict[str, Any]

class TestResultSummary(BaseModel):
    test_type: str
    mode: str
    total_requests: int
    successful_bookings: int
    duplicate_records_created: int
    duplicate_records_prevented: int
    retry_requests: int
    concurrent_requests: int
    failed_requests: int
    prevention_rate_percent: float
    traces: List[RequestTrace]
