"""
Deterministic Validation Dataset Generator and Runner for Next 35% Requirements.
Covers 10 explicit test categories:
1. Normal bookings
2. Repeated retry requests
3. Same idempotency key
4. Different idempotency keys for same slot
5. Concurrent requests
6. Already-booked slots
7. Missing required fields
8. Invalid appointment time
9. Failed transaction simulation
10. Multiple patients competing for the same doctor/time
"""

import json
import os
import asyncio
from typing import List, Dict, Any

VALIDATION_DATASET_FILE = "validation_dataset.json"

def generate_validation_dataset_file() -> List[Dict[str, Any]]:
    """Generates and writes deterministic validation dataset to JSON file."""
    dataset = [
        # Category 1: Normal bookings
        {
            "id": "VAL-CAT-01",
            "category": "Normal Bookings",
            "description": "Standard single appointment request with all valid parameters.",
            "patient_id": "VAL-P-101",
            "doctor_id": "DOC-CARDIOLOGY-01",
            "appointment_date": "2026-11-01",
            "appointment_time": "09:00",
            "idempotency_key": "IDEM-VAL-NORM-01",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 200,
            "expected_booking_status": "CONFIRMED"
        },
        # Category 2: Repeated retry requests
        {
            "id": "VAL-CAT-02",
            "category": "Repeated Retry Requests",
            "description": "Submitting identical retry 3 times with retry counter incrementing.",
            "patient_id": "VAL-P-102",
            "doctor_id": "DOC-NEUROLOGY-02",
            "appointment_date": "2026-11-01",
            "appointment_time": "10:00",
            "idempotency_key": "IDEM-VAL-RETRY-02",
            "retry_number": 1,
            "role": "Patient",
            "expected_status": 200,
            "expected_booking_status": "CONFIRMED"
        },
        # Category 3: Same idempotency key
        {
            "id": "VAL-CAT-03",
            "category": "Same Idempotency Key",
            "description": "Re-using existing idempotency key to test strict cache deduplication.",
            "patient_id": "VAL-P-102",
            "doctor_id": "DOC-NEUROLOGY-02",
            "appointment_date": "2026-11-01",
            "appointment_time": "10:00",
            "idempotency_key": "IDEM-VAL-RETRY-02",
            "retry_number": 2,
            "role": "Patient",
            "expected_status": 200,
            "expected_booking_status": "CONFIRMED"
        },
        # Category 4: Different idempotency keys for same slot
        {
            "id": "VAL-CAT-04",
            "category": "Different Idempotency Keys Same Slot",
            "description": "Patient B tries booking Patient A's slot using a different key.",
            "patient_id": "VAL-P-104",
            "doctor_id": "DOC-CARDIOLOGY-01",
            "appointment_date": "2026-11-01",
            "appointment_time": "09:00",
            "idempotency_key": "IDEM-VAL-DIFFKEY-04",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 409,
            "expected_booking_status": "REJECTED"
        },
        # Category 5: Concurrent requests
        {
            "id": "VAL-CAT-05",
            "category": "Concurrent Requests",
            "description": "Simultaneous execution attempt targeting exact same doctor/slot.",
            "patient_id": "VAL-P-105",
            "doctor_id": "DOC-PEDIATRICS-03",
            "appointment_date": "2026-11-02",
            "appointment_time": "11:00",
            "idempotency_key": "IDEM-VAL-CONC-05",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 200,
            "expected_booking_status": "CONFIRMED"
        },
        # Category 6: Already-booked slots
        {
            "id": "VAL-CAT-06",
            "category": "Already-Booked Slots",
            "description": "Attempting to book a slot that is already confirmed in DB.",
            "patient_id": "VAL-P-106",
            "doctor_id": "DOC-CARDIOLOGY-01",
            "appointment_date": "2026-11-01",
            "appointment_time": "09:00",
            "idempotency_key": "IDEM-VAL-BOOKED-06",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 409,
            "expected_booking_status": "REJECTED"
        },
        # Category 7: Missing required fields
        {
            "id": "VAL-CAT-07",
            "category": "Missing Required Fields",
            "description": "Missing required patient_id field.",
            "patient_id": "",
            "doctor_id": "DOC-ORTHO-04",
            "appointment_date": "2026-11-03",
            "appointment_time": "14:00",
            "idempotency_key": "IDEM-VAL-MISSING-07",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 400,
            "expected_booking_status": "REJECTED"
        },
        # Category 8: Invalid appointment time
        {
            "id": "VAL-CAT-08",
            "category": "Invalid Appointment Time",
            "description": "Submitting malformed date format.",
            "patient_id": "VAL-P-108",
            "doctor_id": "DOC-ORTHO-04",
            "appointment_date": "INVALID-2026-99",
            "appointment_time": "25:99",
            "idempotency_key": "IDEM-VAL-INVTIME-08",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 400,
            "expected_booking_status": "REJECTED"
        },
        # Category 9: Failed transaction simulation
        {
            "id": "VAL-CAT-09",
            "category": "Failed Transaction Simulation",
            "description": "Exceeding MAX_RETRIES limit to trigger controlled transaction rollback.",
            "patient_id": "VAL-P-109",
            "doctor_id": "DOC-GENERAL-05",
            "appointment_date": "2026-11-04",
            "appointment_time": "15:00",
            "idempotency_key": "IDEM-VAL-FAILTRAN-09",
            "retry_number": 10,
            "role": "Patient",
            "expected_status": 400,
            "expected_booking_status": "REJECTED"
        },
        # Category 10: Multiple patients competing for the same doctor/time
        {
            "id": "VAL-CAT-10",
            "category": "Multiple Patients Competing Same Slot",
            "description": "Multiple distinct patients competing for single available slot.",
            "patient_id": "VAL-P-110",
            "doctor_id": "DOC-GENERAL-05",
            "appointment_date": "2026-11-04",
            "appointment_time": "15:00",
            "idempotency_key": "IDEM-VAL-COMPETE-10",
            "retry_number": 0,
            "role": "Patient",
            "expected_status": 200,
            "expected_booking_status": "CONFIRMED"
        }
    ]

    with open(VALIDATION_DATASET_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    return dataset

def load_validation_dataset() -> List[Dict[str, Any]]:
    """Loads validation dataset from file or generates if missing."""
    if not os.path.exists(VALIDATION_DATASET_FILE):
        return generate_validation_dataset_file()
    with open(VALIDATION_DATASET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
