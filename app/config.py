"""
Configurable system rules for duplicate prevention prototype.
"""

from pydantic import BaseModel
from typing import Literal

class SystemConfig(BaseModel):
    MAX_RETRIES: int = 3
    ENABLE_IDEMPOTENCY: bool = True
    ENABLE_CONCURRENCY_PROTECTION: bool = True
    SLOT_CONFLICT_POLICY: Literal["reject", "queue", "log_only"] = "reject"
    SIMULATED_PROCESSING_DELAY_MS: int = 30  # Processing delay to demonstrate baseline race window

# Global active configuration instance
active_config = SystemConfig()

def get_config() -> SystemConfig:
    return active_config

def update_config(new_config: SystemConfig) -> SystemConfig:
    global active_config
    active_config = new_config
    return active_config
