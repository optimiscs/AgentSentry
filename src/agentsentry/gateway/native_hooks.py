"""Decision-only native client hooks. This module never executes a candidate tool.

Native execution acknowledgements are client reports, not trusted executor receipts.
The first adapter deliberately supports a bounded POSIX file workflow.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import shlex
import time
from pathlib import Path

from pydantic import Field

from agentsentry.adapters.filesystem import BoundaryError, relative_path
from agentsentry.schemas import (
    Model,
    ActionIR,
    CallResult,
    Effect,
    SourceType,
    Verdict,
    canonical,
    digest,
    uid,
)


class NativeCall(Model):
    session_id: str = Field(min_length=1, max_length=128)
    client: str = Field(pattern=r"^(codex|claude-code)$")
    client_session_id: str = Field(min_length=1, max_length=128)
    tool_call_id: str = Field(min_length=1, max_length=128)
    cwd: str = Field(min_length=1, max_length=2048)
    tool_name: str = Field(min_length=1, max_length=128)
    tool_input: dict = Field(default_factory=dict)

    def key(self):
        return "hook:" + digest(
            [self.client, self.client_session_id, self.tool_call_id]
        )


class NativeReport(Model):
    call: NativeCall
    receipt: str = Field(min_length=16, max_length=256)
    output: str = Field(max_length=65536)
    failed: bool = False


class NativeHooks:
    def __init__(self, runtime):
        self.rt = runtime
        with runtime.store.lock:
            runtime.store.db.execute(
                "CREATE TABLE IF NOT EXISTS native_claims("
                "action_id TEXT PRIMARY KEY REFERENCES actions(id), receipt_hash TEXT NOT NULL, "
                "report_hash TEXT, response TEXT)"
            )

    def normalize(self, s, call, action_id=None):
        rt = self.rt
        root = rt.settings.workspace
        # File stamps can only be verified on the actual execution host/workspace.
        # No client-provided remote/local path remapping is trusted.
        if Path(call.cwd) != root or not Path(call.cwd).is_absolute():
            raise BoundaryError("NATIVE_EXECUTION_WORKSPACE_MISMATCH")
        args = call.tool_input
        name = call.tool_name
        targets = []
        if name == "Read":
            if not set(args) <= {"file_path", "offset", "limit", "pages"}:
                raise BoundaryError("UNSUPPORTED_NATIVE_ARGUMENT")
            targets = [("fs.read", {"path": args["file_path"]})]
        elif name in {"Write", "Edit"}:
            allowed = (
                {"file_path", "content"}
                if name == "Write"
                else {"file_path", "old_string", "new_string", "replace_all"}
            )
            if not set(args) <= allowed or (
                name == "Edit" and "old_string" not in args
            ):
                raise BoundaryError("UNSUPPORTED_NATIVE_ARGUMENT")
            content = args["content" if name == "Write" else "new_string"]
            targets = [("fs.write", {"path": args["file_path"], "content": content})]
        elif name in {"apply_patch", "ApplyPatch"}:
            if set(args) != {"command"}:
                raise BoundaryError("UNSUPPORTED_NATIVE_ARGUMENT")
            patch = args["command"]
            if not isinstance(patch, str) or len(patch.encode()) > rt.settings.max_file:
                raise BoundaryError("INVALID_NATIVE_PATCH")
            lines = patch.splitlines()
            if (
                not lines
                or lines[0] != "*** Begin Patch"
                or lines[-1] != "*** End Patch"
            ):
                raise BoundaryError("INVALID_NATIVE_PATCH")
            # Verify every structural target, including moves. The native client parses
            # hunk details; malformed hunks cannot add an uninspected target.
            for line in lines[1:-1]:
                if line.startswith("*** "):
                    match = re.fullmatch(
                        r"\*\*\* (Add File|Update File|Delete File|Move to): (.+)", line
                    )
                    if match:
                        targets.append(
                            ("fs.write", {"path": match[2], "content": patch})
                        )
                    elif line != "*** End of File":
                        raise BoundaryError("INVALID_NATIVE_PATCH_HEADER")
            if not targets or len(targets) > 32:
                raise BoundaryError("NATIVE_PATCH_TARGET_BUDGET")
        elif name in {"Bash", "exec_command"}:
            if not set(args) <= {
                "command",
                "description",
                "timeout",
                "run_in_background",
            }:
                raise BoundaryError("UNSUPPORTED_NATIVE_ARGUMENT")
            if args.get("run_in_background"):
                raise BoundaryError("NATIVE_BACKGROUND_UNSUPPORTED")
            command = args["command"]
            # A precisely bounded read-only pipeline observed in real Codex CLI.
            # Raw grammar deliberately excludes quotes, expansion, extra stages,
            # redirections and newlines; every input file is still normalized.
            if isinstance(command, str) and not re.search(r"[\n\r]", command):
                pipeline = re.fullmatch(
                    r"[ \t]*(?:cat|/bin/cat|/usr/bin/cat)[ \t]+([A-Za-z0-9._/-]+)"
                    r"[ \t]*\|[ \t]*(?:head|/usr/bin/head)[ \t]+-n[ \t]+([1-9][0-9]{0,3})[ \t]*",
                    command,
                )
                if pipeline:
                    command = "cat " + pipeline[1]
            if not isinstance(command, str) or re.search(
                r"[\n\r;&|<>`$(){}*?\[\]\\]", command
            ):
                raise BoundaryError("NATIVE_SHELL_SEMANTICS_UNSUPPORTED")
            words = shlex.split(command)
            if (
                words
                and words[0] in {"cat", "/bin/cat", "/usr/bin/cat"}
                and 1 < len(words) <= 17
            ):
                if any(w.startswith("-") for w in words[1:]):
                    raise BoundaryError("NATIVE_SHELL_OPTIONS_UNSUPPORTED")
                targets = [("fs.read", {"path": path}) for path in words[1:]]
            elif words in [["pwd"], ["/bin/pwd"]]:
                return ActionIR(
                    session_id=s.session_id,
                    tool="native.pwd",
                    effects=[Effect.FILE_READ],
                    resource=".",
                    resource_class="REPO",
                    resource_version=digest(str(root)),
                    args_hash=digest(call.model_dump(mode="json")),
                    scope_valid=True,
                    scope_allowed="." in s.intent.allowed_scopes,
                    server_id="native-hook",
                    adapter_version="native-posix-2",
                    **({"action_id": action_id} if action_id else {}),
                )
            else:
                raise BoundaryError("NATIVE_SHELL_SEMANTICS_UNSUPPORTED")
        else:
            # MCP can be used via the separately configured gateway. Never trust a
            # name prefix as proof that an arbitrary MCP server is our gateway.
            raise BoundaryError("NATIVE_TOOL_UNSUPPORTED")
        actions = []
        for tool, target in targets:
            rel = relative_path(root, target["path"])
            if any(
                p in {".codex", ".claude", ".agents", "runtime-data"}
                for p in Path(rel).parts
            ):
                raise BoundaryError("NATIVE_CONTROL_PLANE_ACCESS_DENIED")
            actions.append(
                rt.registry.normalize(s, tool, target, rt.store.contexts(s.session_id))
            )
        invalid = next((a for a in actions if not a.adapter_valid), None)
        if invalid:
            raise BoundaryError(invalid.adapter_error or "NATIVE_INVALID_RESOURCE")
        classes = {a.resource_class for a in actions}
        return ActionIR(
            session_id=s.session_id,
            tool="native." + name,
            server_id="native-hook",
            effects=list(dict.fromkeys(e for a in actions for e in a.effects)),
            resource=canonical([a.resource for a in actions]),
            resource_class=next(
                (c for c in ["CREDENTIAL", "SYSTEM", "SECRET"] if c in classes), "REPO"
            ),
            resource_version=digest(
                [(a.resource, a.resource_version) for a in actions]
            ),
            args_hash=digest(call.model_dump(mode="json")),
            scope_valid=all(a.scope_valid for a in actions),
            scope_allowed=all(a.scope_allowed for a in actions),
            labels=sorted({l for a in actions for l in a.labels}),
            source_refs=list(dict.fromkeys(r for a in actions for r in a.source_refs)),
            source_type=actions[-1].source_type,
            source_trust=actions[-1].source_trust,
            adapter_version="native-posix-2",
            **({"action_id": action_id} if action_id else {}),
        )

    def evaluate(self, call: NativeCall, owner="local-user"):
        rt = self.rt
        with rt.lock:
            s = rt.session(call.session_id, owner)
            request_hash = digest(call.model_dump(mode="json"))
            cached = rt.store.action_by_key(s.session_id, call.key())
            if cached:
                if cached["request_hash"] != request_hash:
                    raise BoundaryError("NATIVE_CALL_ID_REUSED_WITH_DIFFERENT_ARGS")
                result = CallResult.model_validate_json(cached["result"])
                result.status = cached["status"]
                if result.status not in {"ready", "pending"}:
                    result.decision.decision = Verdict.BLOCK
                    result.decision.reason_codes = ["NATIVE_CALL_ALREADY_FINALIZED"]
                return result
            with rt.store.lock:
                count = rt.store.db.execute(
                    "SELECT COUNT(*) FROM actions WHERE session_id=?", (s.session_id,)
                ).fetchone()[0]
            if count >= rt.settings.max_actions:
                raise BoundaryError("ACTION_BUDGET_EXCEEDED")
            try:
                action = self.normalize(s, call)
            except (ValueError, KeyError, TypeError) as exc:
                action = ActionIR(
                    session_id=s.session_id,
                    tool="native." + call.tool_name,
                    effects=[Effect.OTHER],
                    resource=call.tool_name,
                    args_hash=request_hash,
                    adapter_valid=False,
                    scope_valid=False,
                    adapter_error=str(exc)
                    if isinstance(exc, BoundaryError)
                    else "INVALID_NATIVE_INPUT",
                )
            decision = rt._decision(s, action)
            _, ok = rt.store.emit(
                s,
                "HOOK_CANDIDATE",
                {
                    "action": action.model_dump(mode="json"),
                    "client": call.client,
                    "execution_mode": "native_hook",
                    "source_refs": action.source_refs,
                },
                span=action.action_id,
                parent=s.session_id,
            )
            if not ok:
                decision.decision = Verdict.BLOCK
                decision.reason_codes = ["AUDIT_UNAVAILABLE"]
            result = CallResult(
                action=action,
                decision=decision,
                status="ready"
                if decision.decision == Verdict.ALLOW
                else "pending"
                if decision.decision == Verdict.ASK
                else "blocked",
            )
            expires = time.time() + rt.settings.approval_ttl
            binding = rt._binding(s, action)
            with rt.store.transaction() as db:
                rt.store.add_action(
                    action.action_id,
                    s.session_id,
                    call.key(),
                    request_hash,
                    {
                        "execution_mode": "native_hook",
                        "native_call": call.model_dump(mode="json"),
                        "arguments": call.tool_input,
                        "action": action.model_dump(mode="json"),
                        "intent": s.intent.model_dump(mode="json"),
                        "initial_decision": decision.model_dump(mode="json"),
                        "binding": binding,
                        "expires": expires,
                    },
                    result.model_dump(mode="json"),
                )
                if decision.decision == Verdict.ASK:
                    approval_id = uid("apr")
                    db.execute(
                        "INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?)",
                        (
                            approval_id,
                            action.action_id,
                            s.owner,
                            "pending",
                            canonical(binding),
                            rt._sign(binding, expires),
                            rt.epoch,
                            expires,
                            time.time(),
                        ),
                    )
                    decision.approval_id = approval_id
                    decision.expires_at = expires
                rt.store.finish(
                    action.action_id, result.status, result.model_dump(mode="json")
                )
            _, ok = rt.store.emit(
                s,
                "HOOK_DECISION",
                {"decision": decision.model_dump(mode="json")},
                span=decision.decision_id,
                parent=action.action_id,
            )
            if not ok:
                raise BoundaryError("AUDIT_UNAVAILABLE")
            return result

    def approve(self, row, record, private, approve, owner):
        """Called under Runtime.lock; grant permission only, never execute."""
        rt = self.rt
        s = rt.session(record["session_id"], owner)
        result = CallResult.model_validate_json(record["result"])
        if row["status"] != "pending" or record["status"] != "pending":
            raise BoundaryError("APPROVAL_ALREADY_CONSUMED")
        if not approve:
            result.status = "denied"
            result.decision.decision = Verdict.BLOCK
        else:
            try:
                action = self.normalize(
                    s, NativeCall.model_validate(private["native_call"]), record["id"]
                )
                binding = rt._binding(s, action)
                if (
                    row["expires"] <= time.time()
                    or row["epoch"] != rt.epoch
                    or canonical(binding) != row["binding"]
                    or not hmac.compare_digest(
                        row["signature"], rt._sign(binding, row["expires"])
                    )
                ):
                    raise BoundaryError("NATIVE_APPROVAL_INVALID_OR_CHANGED")
                result.decision = rt._decision(s, action, approved=True)
                result.status = (
                    "ready" if result.decision.decision == Verdict.ALLOW else "blocked"
                )
            except (ValueError, KeyError, TypeError):
                result.status = "expired"
                result.decision.decision = Verdict.BLOCK
                result.decision.reason_codes = ["NATIVE_APPROVAL_INVALID_OR_CHANGED"]
        _, ok = rt.store.emit(
            s,
            "HOOK_APPROVAL",
            {"approval_id": row["id"], "status": result.status},
            parent=record["id"],
        )
        if not ok:
            raise BoundaryError("AUDIT_UNAVAILABLE")
        with rt.store.transaction() as db:
            db.execute(
                "UPDATE approvals SET status=? WHERE id=?",
                ("consumed" if result.status == "ready" else result.status, row["id"]),
            )
            rt.store.finish(record["id"], result.status, result.model_dump(mode="json"))
        return result

    def claim(self, call: NativeCall, owner="local-user"):
        rt = self.rt
        with rt.lock:
            s = rt.session(call.session_id, owner)
            row = rt.store.action_by_key(s.session_id, call.key())
            if row is None or row["request_hash"] != digest(
                call.model_dump(mode="json")
            ):
                raise BoundaryError("NATIVE_CLAIM_MISMATCH")
            if row["status"] != "ready":
                raise BoundaryError("NATIVE_NOT_READY_OR_ALREADY_CLAIMED")
            private = rt.store.open(row["private"])
            action = self.normalize(s, call, row["id"])
            if (
                time.time() >= private["expires"]
                or rt._binding(s, action) != private["binding"]
            ):
                raise BoundaryError("NATIVE_ACTION_EXPIRED_OR_CHANGED")
            # A grant is valid only if the recorded ASK was independently approved.
            with rt.store.lock:
                approved = (
                    rt.store.db.execute(
                        "SELECT 1 FROM approvals WHERE action_id=? AND status='consumed'",
                        (row["id"],),
                    ).fetchone()
                    is not None
                )
            decision = rt._decision(s, action, approved=approved)
            if decision.decision != Verdict.ALLOW:
                raise BoundaryError("NATIVE_DECISION_CHANGED")
            _, ok = rt.store.emit(
                s,
                "HOOK_DISPATCH_AUTHORIZED",
                {"action_id": row["id"], "execution_verified": False},
                parent=row["id"],
            )
            if not ok:
                raise BoundaryError("AUDIT_UNAVAILABLE")
            receipt = secrets.token_urlsafe(32)
            with rt.store.transaction() as db:
                if (
                    db.execute(
                        "UPDATE actions SET status='dispatched' WHERE id=? AND status='ready'",
                        (row["id"],),
                    ).rowcount
                    != 1
                ):
                    raise BoundaryError("NATIVE_ALREADY_CLAIMED")
                db.execute(
                    "INSERT INTO native_claims VALUES(?,?,NULL,NULL)",
                    (row["id"], hashlib.sha256(receipt.encode()).hexdigest()),
                )
            return {
                "action_id": row["id"],
                "receipt": receipt,
                "execution_mode": "native_hook",
                "status": "dispatched",
            }

    def report(self, report: NativeReport, owner="local-user"):
        rt = self.rt
        with rt.lock:
            s = rt.session(report.call.session_id, owner)
            row = rt.store.action_by_key(s.session_id, report.call.key())
            if not row or row["request_hash"] != digest(
                report.call.model_dump(mode="json")
            ):
                raise BoundaryError("NATIVE_REPORT_MISMATCH")
            with rt.store.lock:
                claim = rt.store.db.execute(
                    "SELECT * FROM native_claims WHERE action_id=?", (row["id"],)
                ).fetchone()
            if not claim or not hmac.compare_digest(
                claim["receipt_hash"],
                hashlib.sha256(report.receipt.encode()).hexdigest(),
            ):
                raise BoundaryError("NATIVE_RECEIPT_INVALID")
            report_hash = digest([report.output, report.failed])
            if claim["report_hash"]:
                if claim["report_hash"] != report_hash:
                    raise BoundaryError("NATIVE_REPORT_CHANGED")
                return json.loads(claim["response"])
            if row["status"] != "dispatched":
                raise BoundaryError("NATIVE_EXECUTION_OUTCOME_UNKNOWN")
            context = rt.scan(
                s.session_id,
                owner,
                SourceType.MCP_RESPONSE,
                "native:" + report.call.tool_name,
                report.output,
                parent=row["id"],
            )
            status = (
                "client_reported_failed"
                if report.failed
                else "client_reported_succeeded"
            )
            response = {
                "status": status,
                "context_ref": context["chunk_id"],
                "risk": context["risk"],
                "execution_verified": False,
            }
            _, ok = rt.store.emit(
                s, "HOOK_CLIENT_REPORTED_RESULT", response, parent=row["id"]
            )
            if not ok:
                raise BoundaryError("AUDIT_UNAVAILABLE")
            result = CallResult.model_validate_json(row["result"])
            result.status = status
            result.output = response
            with rt.store.transaction() as db:
                db.execute(
                    "UPDATE native_claims SET report_hash=?,response=? WHERE action_id=?",
                    (report_hash, canonical(response), row["id"]),
                )
                rt.store.finish(row["id"], status, result.model_dump(mode="json"))
            return response
