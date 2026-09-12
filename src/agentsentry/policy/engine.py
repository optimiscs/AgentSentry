from __future__ import annotations

from agentsentry.intent.contracts import align, destination_matches
from agentsentry.schemas import ActionIR, Decision, IntentIR, Verdict

from .dsl import Policy


class Engine:
    def __init__(self, text: str):
        self.policy = Policy(text)

    def decide(
        self, intent: IntentIR, action: ActionIR, approved: bool = False
    ) -> Decision:
        alignment = align(intent, action)
        fields = {
            "action.effect": [e.value for e in action.effects],
            "action.tool": action.tool,
            "action.server": action.server_id,
            "resource.class": action.resource_class,
            "resource.valid": action.adapter_valid,
            "resource.scope_valid": action.scope_valid,
            "resource.scope_allowed": action.scope_allowed,
            "resource.path": action.resource,
            "destination.domain": action.destination_domain,
            "destination.trust": action.destination_trust,
            "intent.sensitive_access": intent.sensitive_access,
            "source.type": action.source_type,
            "source.trust": action.source_trust,
            "agent.depth": action.agent_depth,
            "approval.valid": approved,
        }
        functions = {
            "flow.has": lambda label: label in action.labels,
            "intent.allows": lambda e: e in intent.allowed_effects,
            "intent.scope_contains": lambda _: action.scope_allowed,
            "intent.destination_matches": lambda _: destination_matches(intent, action),
        }
        matched = [
            r for r in self.policy.rules if self.policy.matches(r, fields, functions)
        ]
        hard = [r for r in matched if r.decision == "BLOCK" and not r.overridable]
        reasons = []
        rule_ids = []
        if not action.adapter_valid:
            verdict, risk = Verdict.BLOCK, "HIGH"
            reasons = [action.adapter_error or "INVALID_ACTION"]
        elif not action.effects or any(
            e not in intent.maximum_effects for e in action.effects
        ):
            verdict, risk = Verdict.BLOCK, "HIGH"
            reasons = ["STATIC_PERMISSION_CEILING"]
        elif hard:
            verdict, risk = Verdict.BLOCK, "CRITICAL"
            reasons = [r.reason for r in hard]
            rule_ids = [r.name for r in hard]
        elif any(e in intent.forbidden_effects for e in action.effects):
            verdict, risk = Verdict.BLOCK, "HIGH"
            reasons = ["EXPLICIT_DENY"]
        elif any(r.decision == "BLOCK" for r in matched):
            verdict, risk = Verdict.BLOCK, "HIGH"
            reasons = [r.reason for r in matched if r.decision == "BLOCK"]
        elif approved:
            verdict, risk = Verdict.ALLOW, "MEDIUM"
            reasons = ["EXACT_ACTION_APPROVED"]
        elif any(r.decision == "ASK" for r in matched) or not alignment.aligned:
            verdict, risk = Verdict.ASK, "MEDIUM"
            reasons = [
                r.reason for r in matched if r.decision == "ASK"
            ] or alignment.deviation_types
        elif all(e in intent.allowed_effects for e in action.effects):
            verdict, risk = Verdict.ALLOW, "LOW"
            reasons = ["CONTRACT_ALIGNED"]
        else:
            verdict, risk = Verdict.BLOCK, "HIGH"
            reasons = ["DEFAULT_DENY"]
        return Decision(
            action_id=action.action_id,
            decision=verdict,
            risk_level=risk,
            reason_codes=reasons,
            matched_policies=rule_ids or [r.name for r in matched],
            policy_version=self.policy.version,
            intent_version=intent.version,
            alignment=alignment,
        )
