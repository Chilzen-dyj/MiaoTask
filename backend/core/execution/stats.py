"""Execution support."""
from dataclasses import dataclass

@dataclass
class RunStats:
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    claims: int = 0
    cross_app: int = 0
    attempts: int = 0
    elapsed: int = 0
