"""
Synthetic Validation Dataset Generator (50-100 items).
Contains realistic synthetic booking requests with normal, retry, concurrent, and invalid patterns.
"""

import uuid
from typing import List, Dict, Any

PATIENTS = [f"P-10{i}" for i in range(1, 15)]
DOCTORS = ["DOC-CARDIOLOGY-01", "DOC-NEUROLOGY-02", "DOC-PEDIATRICS-03", "DOC-ORTHO-04", "DOC-GENERAL-05"]
DATES = ["2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]
TIMES = ["09:00", "09:30", "10:00", "10:30", "11:00", "14:00", "14:30", "15:00"]

def generate_synthetic_dataset() -> List[Dict[str, Any]]:
    """Generates a dataset of 60 synthetic appointment booking requests."""
    dataset = []

    # 1. Normal Requests (20 unique bookings)
    for i in range(20):
        dataset.append({
            "scenario": "normal",
            "patient_id": PATIENTS[i % len(PATIENTS)],
            "doctor_id": DOCTORS[i % len(DOCTORS)],
            "appointment_date": DATES[i % len(DATES)],
            "appointment_time": TIMES[i % len(TIMES)],
            "idempotency_key": f"IDEM-NORM-{i+1:03d}",
            "retry_number": 0
        })

    # 2. Retry Requests (5 original requests, each retried 3 times = 15 total requests)
    for r in range(5):
        key = f"IDEM-RETRY-SET-{r+1}"
        pat = PATIENTS[(r + 3) % len(PATIENTS)]
        doc = DOCTORS[(r + 1) % len(DOCTORS)]
        dt = "2026-09-20"
        tm = f"11:{r*10:02d}"
        for attempt in range(3):
            dataset.append({
                "scenario": "retry",
                "patient_id": pat,
                "doctor_id": doc,
                "appointment_date": dt,
                "appointment_time": tm,
                "idempotency_key": key,
                "retry_number": attempt
            })

    # 3. Concurrent Race Attempt Group 1 (10 requests targeting exact same slot)
    for c in range(10):
        dataset.append({
            "scenario": "concurrent_race_group_1",
            "patient_id": f"P-RACE-10{c}",
            "doctor_id": "DOC-CARDIOLOGY-01",
            "appointment_date": "2026-09-25",
            "appointment_time": "10:00",
            "idempotency_key": f"IDEM-RACE1-{c+1}",
            "retry_number": 0
        })

    # 4. Concurrent Race Attempt Group 2 (10 requests targeting another slot)
    for c in range(10):
        dataset.append({
            "scenario": "concurrent_race_group_2",
            "patient_id": f"P-RACE-20{c}",
            "doctor_id": "DOC-NEUROLOGY-02",
            "appointment_date": "2026-09-25",
            "appointment_time": "14:00",
            "idempotency_key": f"IDEM-RACE2-{c+1}",
            "retry_number": 0
        })

    # 5. Invalid / Missing Key Edge Cases (5 requests)
    for inv in range(5):
        dataset.append({
            "scenario": "invalid_missing_key" if inv % 2 == 0 else "invalid_date",
            "patient_id": PATIENTS[inv % len(PATIENTS)],
            "doctor_id": DOCTORS[inv % len(DOCTORS)],
            "appointment_date": "2026-09-28" if inv % 2 == 0 else "INVALID-DATE",
            "appointment_time": "15:30",
            "idempotency_key": None if inv % 2 == 0 else f"IDEM-INV-{inv}",
            "retry_number": 0
        })

    return dataset
