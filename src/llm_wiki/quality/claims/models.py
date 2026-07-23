"""Claim, EpistemicEvent, Contradiction dataclasses."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Claim:
    claim_id: str
    statement: str
    confidence: str
    status: str
    sources: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    claim_type: str = "fact"
    schema_version: str = "v0.2.1"
    created_at: str = ""
    updated_at: str = ""
    first_seen_operation_id: str = ""
    last_seen_operation_id: str = ""
    depends_on: list[str] = field(default_factory=list)
    contradicted_by: list[str] = field(default_factory=list)

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class EpistemicEvent:
    claim_id: str
    event_type: str
    source: str
    timestamp: str = ""
    event_id: str = ""
    operation_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"


@dataclass
class Contradiction:
    contradiction_id: str
    claim_ids: list[str]
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    resolution: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.contradiction_id:
            self.contradiction_id = f"ctr_{uuid.uuid4().hex[:12]}"
