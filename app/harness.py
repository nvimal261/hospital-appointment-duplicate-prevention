"""
Test Harness for Duplicate Booking Prevention & Concurrency Simulation.
Executes single, retry, 10x concurrent race, and synthetic dataset benchmark runs.
"""

import asyncio
import uuid
import time
from typing import Dict, Any, List

from app.models import AppointmentCreate, TestResultSummary, RequestTrace
from app.baseline import handle_baseline_booking
from app.protected import handle_protected_booking
from app.database import record_trace, fetch_all_traces, reset_database, fetch_all_appointments
from app.synthetic_data import generate_synthetic_dataset

async def run_single_test(mode: str, data: AppointmentCreate) -> Dict[str, Any]:
    """Runs a single booking request in specified mode."""
    if mode == "baseline":
        status, payload, trace = await handle_baseline_booking(data, test_type="normal")
    else:
        status, payload, trace = await handle_protected_booking(data, test_type="normal")

    record_trace(trace)
    return {
        "status_code": status,
        "payload": payload,
        "trace": trace
    }

async def run_retry_test(mode: str, data: AppointmentCreate, retries: int = 3) -> Dict[str, Any]:
    """Sends the identical request `retries` times sequentially using the same idempotency key."""
    if not data.idempotency_key:
        data.idempotency_key = f"IDEM-RETRY-{uuid.uuid4().hex[:6]}"

    results = []
    traces = []
    for i in range(retries):
        data.retry_number = i
        if mode == "baseline":
            status, payload, trace = await handle_baseline_booking(data, test_type="retry")
        else:
            status, payload, trace = await handle_protected_booking(data, test_type="retry")

        record_trace(trace)
        results.append(payload)
        traces.append(trace)

    return {
        "mode": mode,
        "attempts_sent": retries,
        "idempotency_key": data.idempotency_key,
        "results": results,
        "traces": traces
    }

async def run_concurrent_test(mode: str, data: AppointmentCreate, concurrency_count: int = 10) -> Dict[str, Any]:
    """Sends `concurrency_count` requests simultaneously for the identical slot via asyncio.gather."""
    key_prefix = data.idempotency_key or f"IDEM-CONC-{uuid.uuid4().hex[:6]}"

    async def worker(index: int):
        req_copy = AppointmentCreate(
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            appointment_date=data.appointment_date,
            appointment_time=data.appointment_time,
            idempotency_key=f"{key_prefix}-W{index+1}",
            retry_number=0
        )
        if mode == "baseline":
            return await handle_baseline_booking(req_copy, test_type="concurrent")
        else:
            return await handle_protected_booking(req_copy, test_type="concurrent")

    tasks = [worker(i) for i in range(concurrency_count)]
    responses = await asyncio.gather(*tasks)

    results = []
    traces = []
    for status, payload, trace in responses:
        record_trace(trace)
        results.append(payload)
        traces.append(trace)

    return {
        "mode": mode,
        "total_concurrent_requests": concurrency_count,
        "slot": f"{data.doctor_id} @ {data.appointment_date} {data.appointment_time}",
        "results": results,
        "traces": traces
    }

def calculate_metrics_for_mode(mode: str, traces: List[Dict[str, Any]], appointments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates strict quantitative metrics and duplicate prevention rates."""
    total_requests = len(traces)
    successful_bookings = sum(1 for t in traces if t["success"] and t["response_status"] in (200, 201))
    failed_requests = sum(1 for t in traces if not t["success"] or t["response_status"] >= 400)
    retry_requests = sum(1 for t in traces if t["test_type"] == "retry" or t["retry_number"] > 0)
    concurrent_requests = sum(1 for t in traces if t["test_type"] == "concurrent" or t["test_type"].startswith("concurrent"))

    # Count duplicate records in database for same doctor+date+time
    slot_counts: Dict[str, int] = {}
    for app in appointments:
        if app.get("mode") == mode and app.get("booking_status") == "CONFIRMED":
            slot_key = f"{app['doctor_id']}|{app['appointment_date']}|{app['appointment_time']}"
            slot_counts[slot_key] = slot_counts.get(slot_key, 0) + 1

    duplicate_records_created = sum(max(0, count - 1) for count in slot_counts.values())

    # Count prevented duplicates (requests that were rejected due to slot conflict or returned via idempotency)
    duplicates_prevented = sum(1 for t in traces if t["database_result"] in ("SLOT_CONFLICT_REJECTED", "RETURNED_IDEMPOTENT"))

    total_duplicate_attempts = duplicate_records_created + duplicates_prevented

    if total_duplicate_attempts > 0:
        prevention_rate = round((duplicates_prevented / total_duplicate_attempts) * 100.0, 1)
    else:
        prevention_rate = 100.0 if duplicate_records_created == 0 else 0.0

    return {
        "mode": mode,
        "total_requests": total_requests,
        "successful_bookings": successful_bookings,
        "duplicate_records_created": duplicate_records_created,
        "duplicate_records_prevented": duplicates_prevented,
        "duplicate_attempts": total_duplicate_attempts,
        "retry_requests": retry_requests,
        "concurrent_requests": concurrent_requests,
        "failed_requests": failed_requests,
        "prevention_rate_percent": prevention_rate
    }

async def run_synthetic_benchmark() -> Dict[str, Any]:
    """Runs full 60-item synthetic dataset test across BOTH Baseline and Protected modes."""
    dataset = generate_synthetic_dataset()

    async def execute_dataset_for_mode(mode: str):
        reset_database()
        sequential_items = []
        concurrent_groups: Dict[str, List[Dict[str, Any]]] = {}

        for item in dataset:
            scenario = item.get("scenario", "")
            if scenario.startswith("concurrent"):
                concurrent_groups.setdefault(scenario, []).append(item)
            else:
                sequential_items.append(item)

        # Execute non-concurrent items sequentially
        for item in sequential_items:
            req = AppointmentCreate(
                patient_id=item["patient_id"],
                doctor_id=item["doctor_id"],
                appointment_date=item["appointment_date"],
                appointment_time=item["appointment_time"],
                idempotency_key=item.get("idempotency_key"),
                retry_number=item.get("retry_number", 0)
            )
            if mode == "baseline":
                status, payload, trace = await handle_baseline_booking(req, test_type=item["scenario"])
            else:
                status, payload, trace = await handle_protected_booking(req, test_type=item["scenario"])
            record_trace(trace)

        # Execute concurrent groups using asyncio.gather
        for group_name, items in concurrent_groups.items():
            async def worker(item):
                req = AppointmentCreate(
                    patient_id=item["patient_id"],
                    doctor_id=item["doctor_id"],
                    appointment_date=item["appointment_date"],
                    appointment_time=item["appointment_time"],
                    idempotency_key=item.get("idempotency_key"),
                    retry_number=item.get("retry_number", 0)
                )
                if mode == "baseline":
                    return await handle_baseline_booking(req, test_type="concurrent")
                else:
                    return await handle_protected_booking(req, test_type="concurrent")

            tasks = [worker(item) for item in items]
            responses = await asyncio.gather(*tasks)
            for status, payload, trace in responses:
                record_trace(trace)

    # 1. Run Baseline Mode
    await execute_dataset_for_mode("baseline")
    baseline_traces = fetch_all_traces(mode="baseline")
    baseline_apps = fetch_all_appointments(mode="baseline")
    baseline_metrics = calculate_metrics_for_mode("baseline", baseline_traces, baseline_apps)

    # 2. Run Protected Mode
    await execute_dataset_for_mode("protected")
    protected_traces = fetch_all_traces(mode="protected")
    protected_apps = fetch_all_appointments(mode="protected")
    protected_metrics = calculate_metrics_for_mode("protected", protected_traces, protected_apps)

    return {
        "baseline": baseline_metrics,
        "protected": protected_metrics,
        "synthetic_items_count": len(dataset)
    }
