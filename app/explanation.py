"""
Rule-Based Explanation Layer for Non-Specialist Hospital Staff & Patients.
Generates human-readable, transparent decision rationales and fallback suggestions for appointment requests.
"""

from typing import Dict, Any, List, Optional

# Predefined transparent rule explanations
EXPLANATION_CATALOG = {
    "CONFIRMED": {
        "reason_code": "SLOT_AVAILABLE",
        "human_readable_explanation": "Appointment confirmed because the requested doctor slot was available."
    },
    "DUPLICATE_RETURNED": {
        "reason_code": "IDEMPOTENT_RETRY_MATCH",
        "human_readable_explanation": "This request was already processed. The existing appointment was returned instead of creating another record."
    },
    "SLOT_CONFLICT": {
        "reason_code": "SLOT_ALREADY_BOOKED",
        "human_readable_explanation": "The requested doctor and time slot is already booked by another patient."
    },
    "CONCURRENCY_CONFLICT": {
        "reason_code": "RACE_CONDITION_PREVENTED",
        "human_readable_explanation": "Another request reserved this slot first. This request was rejected to prevent double booking."
    },
    "TRANSACTION_FAILURE": {
        "reason_code": "TRANSACTION_ROLLED_BACK",
        "human_readable_explanation": "The appointment could not be safely completed. Transaction was rolled back, so no inconsistent booking was created."
    },
    "MAX_RETRIES_EXCEEDED": {
        "reason_code": "RETRY_LIMIT_EXCEEDED",
        "human_readable_explanation": "Maximum retry limit exceeded for this request key. Please submit a new request."
    },
    "VALIDATION_ERROR": {
        "reason_code": "INVALID_INPUT_DATA",
        "human_readable_explanation": "Validation failed: Request contains invalid fields or missing required appointment details."
    }
}

def generate_explanation(
    status: str,
    reason_code: Optional[str] = None,
    custom_message: Optional[str] = None,
    request_id: str = "",
    mode: str = "protected",
    available_alternatives: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Constructs a structured explanation payload understandable by hospital staff and patients.
    """
    catalog_item = EXPLANATION_CATALOG.get(reason_code or status, {
        "reason_code": reason_code or "GENERAL_INFO",
        "human_readable_explanation": custom_message or "Request processed by hospital appointment system."
    })

    explanation_text = custom_message if custom_message else catalog_item["human_readable_explanation"]
    code = catalog_item["reason_code"] if not reason_code else reason_code

    # Build clear fallback guidance if rejected/conflict
    fallback_actions = []
    if status in ("REJECTED", "SLOT_CONFLICT", "CONCURRENCY_CONFLICT", "TRANSACTION_FAILURE", "VALIDATION_ERROR"):
        fallback_actions.append("Select an alternative time slot for the same doctor.")
        fallback_actions.append("Choose a different available doctor for the requested date.")
        fallback_actions.append("Retry the booking request with a new idempotency key if appropriate.")
        fallback_actions.append("Contact hospital front-desk staff for manual scheduling assistance.")

    return {
        "status": status,
        "reason_code": code,
        "human_readable_explanation": explanation_text,
        "request_id": request_id,
        "mode": mode,
        "fallback_actions": fallback_actions,
        "alternative_slots": available_alternatives or []
    }
