"""
SQLite Database Layer for Hospital Appointment Platform.
Implements connection pooling, table schemas, WAL mode for concurrency, and transaction utilities.
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_FILE = "hospital_appointments.db"

def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with WAL mode and row factory."""
    conn = sqlite3.connect(DB_FILE, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable Write-Ahead Logging for better concurrency handling
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """Initializes schema for baseline, protected, and trace audit tables."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Baseline Appointments Table (NO unique constraints, allowing race conditions to create duplicates)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS baseline_appointments (
                appointment_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                idempotency_key TEXT,
                booking_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # 2. Protected Appointments Table (Strict UNIQUE constraints on doctor slot and idempotency_key)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS protected_appointments (
                appointment_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                booking_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                CONSTRAINT unique_doctor_slot UNIQUE (doctor_id, appointment_date, appointment_time)
            );
        """)

        # 3. Request Traces Audit Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_traces (
                trace_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                test_type TEXT NOT NULL,
                idempotency_key TEXT,
                patient_id TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                request_start_time REAL NOT NULL,
                request_end_time REAL NOT NULL,
                duration_ms REAL NOT NULL,
                retry_number INTEGER NOT NULL,
                success INTEGER NOT NULL,
                response_status INTEGER NOT NULL,
                database_result TEXT NOT NULL,
                explanation TEXT NOT NULL
            );
        """)

        conn.commit()
    finally:
        conn.close()

def reset_database():
    """Wipes all tables and re-initializes schema for clean testing."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS baseline_appointments;")
        cursor.execute("DROP TABLE IF EXISTS protected_appointments;")
        cursor.execute("DROP TABLE IF EXISTS request_traces;")
        conn.commit()
    finally:
        conn.close()
    init_db()

def record_trace(trace_data: Dict[str, Any]):
    """Records a single request execution trace into the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO request_traces (
                trace_id, request_id, mode, test_type, idempotency_key,
                patient_id, doctor_id, appointment_date, appointment_time,
                request_start_time, request_end_time, duration_ms,
                retry_number, success, response_status, database_result, explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            trace_data["trace_id"],
            trace_data["request_id"],
            trace_data["mode"],
            trace_data["test_type"],
            trace_data.get("idempotency_key"),
            trace_data["patient_id"],
            trace_data["doctor_id"],
            trace_data["appointment_date"],
            trace_data["appointment_time"],
            trace_data["request_start_time"],
            trace_data["request_end_time"],
            trace_data["duration_ms"],
            trace_data["retry_number"],
            1 if trace_data["success"] else 0,
            trace_data["response_status"],
            trace_data["database_result"],
            trace_data["explanation"]
        ))
        conn.commit()
    finally:
        conn.close()

def fetch_all_appointments(mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all appointments from baseline and/or protected tables."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        results = []
        if mode in (None, "baseline"):
            cursor.execute("SELECT *, 'baseline' as mode FROM baseline_appointments ORDER BY created_at DESC;")
            results.extend([dict(row) for row in cursor.fetchall()])
        if mode in (None, "protected"):
            cursor.execute("SELECT *, 'protected' as mode FROM protected_appointments ORDER BY created_at DESC;")
            results.extend([dict(row) for row in cursor.fetchall()])
        return results
    finally:
        conn.close()

def fetch_all_traces(mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all request traces."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if mode:
            cursor.execute("SELECT * FROM request_traces WHERE mode = ? ORDER BY request_start_time DESC;", (mode,))
        else:
            cursor.execute("SELECT * FROM request_traces ORDER BY request_start_time DESC;")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
