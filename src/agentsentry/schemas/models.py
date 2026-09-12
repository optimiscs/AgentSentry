from __future__ import annotations

import hashlib
import json
import time
import uuid
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Effect(StrEnum):
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    NET_EGRESS = "NET_EGRESS"
    EXEC = "EXEC"
    GIT_COMMIT = "GIT_COMMIT"
    GIT_PUSH = "GIT_PUSH"
    DELEGATE = "DELEGATE"
    MEMORY_READ = "MEMORY_READ"
    MEMORY_WRITE = "MEMORY_WRITE"
    OTHER = "OTHER"


class Verdict(StrEnum):
    ALLOW = "ALLOW"
    ASK = "ASK"
    BLOCK = "BLOCK"


class SourceType(StrEnum):
    USER = "USER"
    WEB = "WEB"
    DOCUMENT = "DOCUMENT"
    ISSUE = "ISSUE"
    MCP_DESCRIPTION = "MCP_DESCRIPTION"
    MCP_RESPONSE = "MCP_RESPONSE"
    MEMORY = "MEMORY"
    SUB_AGENT = "SUB_AGENT"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal["1.0"] = "1.0"


class IntentIR(Model):
    intent_id: str = Field(default_factory=lambda: uid("int"))
    version: int = 1
    actor: str
    permission_snapshot_hash: str
    goal: str
    allowed_scopes: list[str]
    allowed_effects: list[Effect]
    maximum_effects: list[Effect]
    forbidden_effects: list[Effect] = Field(default_factory=list)
    sensitive_access: Literal["DENY", "ALLOW"] = "DENY"
    unresolved: list[str] = Field(default_factory=list)
    evidence_source_refs: list[str] = Field(default_factory=list)
    parser_version: str = "templates-1.0"
    authorized_destination_hashes: list[str] = Field(default_factory=list)


class Session(Model):
    session_id: str = Field(default_factory=lambda: uid("sess"))
    trace_id: str = Field(default_factory=lambda: uid("tr"))
    agent_id: str = Field(default_factory=lambda: uid("agent"))
    owner: str
    task: str
    intent: IntentIR
    depth: int = 0
    parent_session_id: str | None = None
    guard_failure: str | None = None
    created_at: float = Field(default_factory=time.time)


class ContextChunk(Model):
    chunk_id: str = Field(default_factory=lambda: uid("ctx"))
    session_id: str
    source_type: SourceType
    source_id: str = Field(max_length=2048)
    trust: Literal["TRUSTED", "UNTRUSTED", "UNKNOWN"] = "UNTRUSTED"
    text: str = Field(max_length=65536)
    canonical_text: str = ""
    labels: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class RiskSignal(Model):
    chunk_id: str
    risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    score: float = Field(ge=0, le=1)
    attack_types: list[str]
    evidence: list[dict[str, Any]]
    labels: list[str]
    source_type: SourceType
    model_version: str = "rules-1.0"
    normalizer_version: str = "unicode-1.0"
    scanned_characters: int
    latency_ms: float


class ActionIR(Model):
    action_id: str = Field(default_factory=lambda: uid("act"))
    session_id: str
    tool: str
    server_id: str = "builtin"
    tool_version: str = "1.0"
    effects: list[Effect]
    resource: str
    resource_class: str = "UNKNOWN"
    resource_version: str = ""
    args_hash: str
    destination_domain: str = ""
    destination_trust: str = "UNKNOWN"
    destination_hashes: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    source_type: str = "USER"
    data_refs: list[str] = Field(default_factory=list)
    source_trust: str = "UNKNOWN"
    scope_valid: bool = False
    scope_allowed: bool = False
    adapter_valid: bool = True
    adapter_error: str | None = None
    agent_depth: int = 0
    adapter_version: str = "builtin-1.0"


class AlignmentResult(Model):
    aligned: bool
    deviation_types: list[str]
    explanation: str


class Decision(Model):
    decision_id: str = Field(default_factory=lambda: uid("dec"))
    action_id: str
    decision: Verdict
    risk_level: str
    reason_codes: list[str]
    matched_policies: list[str]
    policy_version: str
    intent_version: int
    alignment: AlignmentResult
    latency_ms: float = 0
    approval_id: str | None = None
    expires_at: float = Field(default_factory=lambda: time.time() + 600)


class ToolCall(Model):
    session_id: str
    tool: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list, max_length=128)
    idempotency_key: str = Field(
        default_factory=lambda: uid("req"), min_length=1, max_length=128
    )


class CallResult(Model):
    action: ActionIR
    decision: Decision
    status: str
    output: Any = None
    error: str | None = None


class SessionInput(Model):
    task: str = Field(min_length=1, max_length=8192)
    scope: str = Field(default=".", max_length=1024)


class ScanInput(Model):
    session_id: str
    source_type: SourceType
    source_id: str = Field(max_length=2048)
    text: str = Field(max_length=65536)


class ScanBatchInput(Model):
    chunks: list[ScanInput] = Field(min_length=1, max_length=16)


class ApprovalInput(Model):
    approval_id: str
    approve: bool
