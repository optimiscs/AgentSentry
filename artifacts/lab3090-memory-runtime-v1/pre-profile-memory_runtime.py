"""Isolated memory benchmark adapter backed by the actual product Runtime.

The trusted harness exposes only memory tools. Baseline deliberately disables
their policy gate inside this adapter; it is never installed in the product API.
No actor or semantic evaluator is implemented here.
"""

import copy
import json
from pathlib import Path

from agentsentry.config import Settings
from agentsentry.gateway.runtime import Runtime
from agentsentry.intent.contracts import align
from agentsentry.schemas import Decision, Effect, SourceType, ToolCall, Verdict, uid


class UnguardedMemory:
    def __init__(self, engine):
        self.original = engine
        self.policy = engine.policy

    def decide(self, intent, action, approved=False):
        allowed = {"memory.write": Effect.MEMORY_WRITE, "memory.read": Effect.MEMORY_READ}
        if not action.adapter_valid or allowed.get(action.tool) not in action.effects:
            return self.original.decide(intent, action, approved)
        if len(action.effects) != 1:
            raise ValueError("BENCHMARK_MEMORY_EFFECT_MISMATCH")
        return Decision(action_id=action.action_id, decision=Verdict.ALLOW, risk_level="LOW",
                        reason_codes=["BENCHMARK_MEMORY_GATE_DISABLED"],
                        matched_policies=[],
                        policy_version="benchmark-memory-no-gate-v1", intent_version=intent.version,
                        alignment=align(intent, action))


class MemoryRuntime:
    """One case, one fresh database; owner and state path are harness-controlled."""

    def __init__(self, directory, policy_path, configuration="runtime_rules"):
        if configuration not in {"baseline", "runtime_rules"}:
            raise ValueError("UNKNOWN_MEMORY_CONFIGURATION")
        policy = Path(policy_path).read_bytes()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        local_policy = self.directory / "policy.aspolicy"
        local_policy.write_bytes(policy)
        self.settings = Settings(self.directory / "state", self.directory / "workspace",
                                 local_policy, demo=False, external_mcp={}, network_allowlist=())
        self.configuration, self.owner = configuration, "memory-benchmark-user"
        self.phase, self.session, self.runtime = "NEW", None, None
        self.calls, self.sessions = [], []
        self._external = []
        self._open()

    def _open(self):
        self.runtime = Runtime(self.settings)
        if self.configuration == "baseline":
            if self.runtime.engine is None:
                self.close()
                raise ValueError("BENCHMARK_POLICY_UNAVAILABLE")
            self.runtime.engine = UnguardedMemory(self.runtime.engine)

    def close(self):
        if self.runtime is not None:
            self.runtime.close()
            self.runtime = None

    def begin(self, user_query, external_content):
        if self.phase != "NEW":
            raise ValueError("MEMORY_FIRST_SESSION_ALREADY_STARTED")
        if any(set(f) != {"field", "text"} or f["field"] not in {"context", "skill_md"}
               or not isinstance(f["text"], str) for f in external_content):
            raise ValueError("INVALID_MEMORY_EXTERNAL_FIELDS")
        self.session = self.runtime.create_session(user_query, self.owner)
        self.sessions.append(self.session.session_id)
        self._external = copy.deepcopy(external_content)
        for item in self._external:
            self.runtime.scan(self.session.session_id, self.owner, SourceType.DOCUMENT,
                              item["field"], item["text"])
        self.phase = "WRITE"

    def external(self):
        if self.phase != "WRITE":
            raise ValueError("ORIGINAL_CONTEXT_UNAVAILABLE_IN_FOLLOWUP")
        return copy.deepcopy(self._external)

    def call(self, tool, arguments, request_id=None):
        if self.runtime is None or self.phase not in {"WRITE", "RECALL"}:
            raise ValueError("MEMORY_SESSION_NOT_ACTIVE")
        if tool not in {"memory.write", "memory.read"}:
            raise ValueError("ONLY_MEMORY_TOOLS_EXPOSED")
        result = self.runtime.call(ToolCall(session_id=self.session.session_id,
                                           idempotency_key=request_id or uid("request"),
                                           tool=tool, arguments=arguments), self.owner)
        self.calls.append({"phase": self.phase, "request_id": request_id,
                           "result": result.model_dump(mode="json")})
        return result

    def snapshot(self):
        """Private evaluator view, including quarantined entries; never an actor input."""
        with self.runtime.store.lock:
            rows = self.runtime.store.db.execute(
                "SELECT id,name,private,metadata,status FROM memories WHERE owner=? ORDER BY created,id",
                (self.owner,),
            ).fetchall()
        return [{"memory_id": row["id"], "name": row["name"], "status": row["status"],
                 "text": self.runtime.store.open(row["private"])["text"],
                 "metadata": json.loads(row["metadata"])} for row in rows]

    def followup(self, user_query):
        if self.phase != "WRITE" or not isinstance(user_query, str) or not 1 <= len(user_query) <= 8192 or not user_query.strip():
            raise ValueError("VALID_FOLLOWUP_QUERY_REQUIRED")
        before, original_epoch = self.snapshot(), self.runtime.epoch
        first_session = self.session.session_id
        self.close()
        self._open()
        if self.snapshot() != before or self.runtime.epoch == original_epoch:
            raise ValueError("MEMORY_REOPEN_EVIDENCE_MISMATCH")
        self.session = self.runtime.create_session(user_query, self.owner)
        if self.session.session_id == first_session or self.runtime.store.contexts(self.session.session_id):
            raise ValueError("FOLLOWUP_MUST_START_WITH_EMPTY_CONTEXT")
        self.sessions.append(self.session.session_id)
        self._external = []
        self.phase = "RECALL"
        return {"first_session": first_session, "followup_session": self.session.session_id,
                "runtime_recreated": True, "persisted_entries_unchanged": True,
                "initial_contexts": 0}

    def recall_active(self):
        """Explicit all-active retrieval profile, through the product read gate.

        This is not a native agent's vector retriever. Excluded quarantined rows
        remain visible to the evaluator, but are never passed to the actor.
        """
        if self.phase != "RECALL":
            raise ValueError("RECALL_REQUIRES_FOLLOWUP_SESSION")
        with self.runtime.store.lock:
            ids = [r[0] for r in self.runtime.store.db.execute(
                "SELECT id FROM memories WHERE owner=? AND status='active' ORDER BY created,id", (self.owner,))]
        observed = []
        for memory_id in ids:
            result = self.call("memory.read", {"memory_id": memory_id})
            observed.append({"memory_id": memory_id, "status": result.status,
                             "decision": result.decision.decision.value,
                             "output": result.output if result.status == "succeeded" else None})
        return observed
