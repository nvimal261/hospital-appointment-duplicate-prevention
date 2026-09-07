"""
FastAPI Main Application and REST API Router.
Mounts endpoints for appointment bookings, test harness triggers, dynamic rules config, and static web UI.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional, List, Dict, Any

from app.config import get_config, update_config, SystemConfig
from app.database import init_db, fetch_all_appointments, fetch_all_traces, reset_database
from app.models import AppointmentCreate, AppointmentResponse, RequestTrace
from app.baseline import handle_baseline_booking
from app.protected import handle_protected_booking
from app.harness import (
    run_single_test, run_retry_test, run_concurrent_test,
    run_synthetic_benchmark, calculate_metrics_for_mode
)

app = FastAPI(
    title="Hospital Appointment Duplicate Prevention Platform",
    description="Prototype demonstrating Idempotency & Concurrency Protection",
    version="1.0.0"
)

# Enable CORS for convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """Initialize SQLite tables on application startup."""
    init_db()

# --- Config Endpoints ---
@app.get("/api/config", response_model=SystemConfig)
def read_config():
    """Get active configurable system rules."""
    return get_config()

@app.post("/api/config", response_model=SystemConfig)
def save_config(config: SystemConfig):
    """Update active configurable system rules."""
    return update_config(config)

# --- Appointment Endpoints ---
@app.post("/api/appointments")
async def create_appointment(
    data: AppointmentCreate,
    mode: str = Query("protected", description="Booking mode: 'protected' or 'baseline'")
):
    """
    Core Appointment Booking Endpoint.
    Supports both Protected (Idempotent + Atomic UNIQUE constraint) and Baseline (Vulnerable Check-then-Insert).
    """
    if mode == "baseline":
        status_code, payload, trace = await handle_baseline_booking(data, test_type="manual")
    else:
        status_code, payload, trace = await handle_protected_booking(data, test_type="manual")

    from app.database import record_trace
    record_trace(trace)
    return JSONResponse(status_code=status_code, content=payload)

@app.get("/api/appointments")
def list_appointments(
    mode: Optional[str] = Query(None, description="Filter by mode: 'protected', 'baseline', or all"),
    status: Optional[str] = Query(None, description="Filter by status: 'CONFIRMED', 'REJECTED', 'FAILED'")
):
    """List stored appointments from database."""
    apps = fetch_all_appointments(mode=mode)
    if status:
        apps = [a for a in apps if a.get("booking_status") == status]
    return apps

# --- Test Harness Endpoints ---
@app.post("/api/tests/normal")
async def test_normal(
    data: AppointmentCreate,
    mode: str = Query("protected")
):
    """Runs Test Case 1: Normal Single Booking."""
    return await run_single_test(mode=mode, data=data)

@app.post("/api/tests/retry")
async def test_retry(
    data: AppointmentCreate,
    mode: str = Query("protected"),
    retries: int = Query(3, ge=1, le=10)
):
    """Runs Test Case 2: Send same request `retries` times using same idempotency key."""
    return await run_retry_test(mode=mode, data=data, retries=retries)

@app.post("/api/tests/concurrent")
async def test_concurrent(
    data: AppointmentCreate,
    mode: str = Query("protected"),
    count: int = Query(10, ge=2, le=50)
):
    """Runs Test Case 3: Send `count` concurrent requests for exact same slot simultaneously."""
    return await run_concurrent_test(mode=mode, data=data, concurrency_count=count)

@app.post("/api/tests/synthetic")
async def test_synthetic():
    """Runs Test Case 4: Full 60-item synthetic benchmark comparing Baseline vs Protected prototype."""
    return await run_synthetic_benchmark()

@app.get("/api/tests/results")
def get_test_results(mode: Optional[str] = None):
    """Returns comparative metrics and audit traces."""
    traces = fetch_all_traces(mode=mode)
    apps = fetch_all_appointments(mode=mode)

    baseline_traces = [t for t in traces if t["mode"] == "baseline"]
    baseline_apps = [a for a in apps if a.get("mode") == "baseline"]
    baseline_metrics = calculate_metrics_for_mode("baseline", baseline_traces, baseline_apps)

    protected_traces = [t for t in traces if t["mode"] == "protected"]
    protected_apps = [a for a in apps if a.get("mode") == "protected"]
    protected_metrics = calculate_metrics_for_mode("protected", protected_traces, protected_apps)

    return {
        "metrics": {
            "baseline": baseline_metrics,
            "protected": protected_metrics
        },
        "traces": traces,
        "total_traces": len(traces)
    }

@app.post("/api/tests/reset")
def reset_all_data():
    """Reset database tables and traces for a clean state."""
    reset_database()
    return {"message": "Database and test traces reset successfully."}

# --- Static Frontend Delivery ---
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    """Serve the main Single Page Application index.html."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Hospital Appointment Duplicate Prevention API is running. UI static files missing."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
