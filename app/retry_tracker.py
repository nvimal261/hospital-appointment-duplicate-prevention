"""
Retry Event Tracking Module.
Records, categorizes, and audits retry requests, deduplication events, and client retry counts.
"""

from typing import Dict, Any, List, Optional
import time
from datetime import datetime
from app.database import get_db_connection

def record_retry_event(
    request_id: str,
    original_request_id: Optional[str],
    retry_number: int,
    idempotency_key: Optional[str],
    retry_reason: str,
    result: str
) -> Dict[str, Any]:
    """Stores a retry attempt event into the retry_events table."""
    timestamp = datetime.now().isoformat()
    retry_id = f"RTRY-{int(time.time()*1000)}"

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO retry_events (
                retry_id, request_id, original_request_id, retry_number,
                idempotency_key, retry_reason, timestamp, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            retry_id,
            request_id,
            original_request_id or request_id,
            retry_number,
            idempotency_key,
            retry_reason,
            timestamp,
            result
        ))
        conn.commit()
    finally:
        conn.close()

    return {
        "retry_id": retry_id,
        "request_id": request_id,
        "original_request_id": original_request_id or request_id,
        "retry_number": retry_number,
        "idempotency_key": idempotency_key,
        "retry_reason": retry_reason,
        "timestamp": timestamp,
        "result": result
    }

def fetch_all_retries(request_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recorded retry events, optionally filtered by request_id or original_request_id."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if request_id:
            cursor.execute("""
                SELECT * FROM retry_events 
                WHERE request_id = ? OR original_request_id = ?
                ORDER BY timestamp DESC;
            """, (request_id, request_id))
        else:
            cursor.execute("SELECT * FROM retry_events ORDER BY timestamp DESC;")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
