from __future__ import annotations

import re

from agentsentry.schemas import ActionIR, AlignmentResult, Effect, IntentIR, digest, uid

STATIC_EFFECTS = list(Effect)
STATIC_EFFECTS.remove(Effect.OTHER)


def request_positions(task: str, verbs: str) -> set[int]:
    """Supported English request clauses, excluding quoted examples and nouns.

    This is a conservative grammar, not a general semantic intent model. Unknown
    phrasings require approval rather than treating every mentioned verb as consent.
    """
    masked = re.sub(
        r"\"[^\"\n]*\"|(?<!\w)'[^'\n]*'(?!\w)",
        lambda m: " " * len(m.group()),
        task,
    )
    prefix = (
        r"(?:^|[\n.!?;]\s*|\b(?:and|then|please)\s+)\s*"
        r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
        r"i\s+(?:want|need)\s+you\s+to\s+|(?:do not|don't)\s+forget\s+to\s+)?"
    )
    return {
        m.start("verb")
        for m in re.finditer(prefix + r"(?P<verb>" + verbs + r")\b", masked, re.I)
    }


def destination_hash(value: str) -> str:
    """Bind the entire reviewed destination, never just its domain or a substring."""
    return digest({"destination": value})


def explicit_destinations(task: str) -> list[str]:
    """Narrow trusted-user grammar; observations/descriptions are never input here.

    Only a literal destination after a sending verb and 'to' is supported. Indirect
    references and ambiguous recipient lists require approval. Exact spelling is
    deliberate: normalization must not widen an authorization.
    """
    pattern = (
        r"\b(?:send|upload|post|share|forward|transfer)\b[^\n;!?]{0,160}?\bto\s+"
        r"(?:['\"](?P<quoted>[^'\"\n]{1,256})['\"]|"
        r"(?P<literal>https?://[^\s<>'\"]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|[A-Za-z]+))"
        r"(?=\s*(?:[.!?;](?:\s|$)|$))"
    )
    values = []
    positions = request_positions(task, "send|upload|post|share|forward|transfer")
    for match in re.finditer(pattern, task, re.I):
        if match.start() not in positions:
            continue
        value = match.group("quoted") or match.group("literal")
        if value.lower() in {"me", "him", "her", "them", "it", "everyone", "all"}:
            continue
        if value.startswith(("http://", "https://")) and value.endswith("."):
            # Trailing punctuation vs a path ending in '.' is ambiguous.
            continue
        values.append(destination_hash(value))
    return sorted(set(values))


def destination_matches(intent: IntentIR, action: ActionIR) -> bool:
    return (
        Effect.NET_EGRESS in intent.allowed_effects
        and Effect.NET_EGRESS not in intent.forbidden_effects
        and bool(action.destination_hashes)
        and set(action.destination_hashes) <= set(intent.authorized_destination_hashes)
    )


def resolve(
    task: str, actor: str, scope: str, ceiling: list[Effect] | None = None
) -> IntentIR:
    maximum = ceiling if ceiling is not None else STATIC_EFFECTS
    effects = [Effect.FILE_READ, Effect.MEMORY_READ]
    goal = "code_review"
    if re.search(
        r"修复|修改|编写|创建|添加|删除|预约|预订|邀请|更新", task
    ) or request_positions(
        task,
        r"fix|edit|write|implement|create|add|append|delete|remove|reserve|book|invite|update|schedule|reschedule|cancel|make\s+(?:a\s+)?reservation",
    ):
        goal = "code_change"
        effects.append(Effect.FILE_WRITE)
    if re.search(r"测试|运行|执行", task) or request_positions(
        task, "test|execute|run"
    ):
        effects.append(Effect.EXEC)
    if re.search(r"上传|发送|访问", task) or request_positions(
        task, "upload|send|fetch|post|share|forward|transfer|pay"
    ):
        effects.append(Effect.NET_EGRESS)
        goal = "report_transfer"
    # Explicit negative language always overrides positive keyword matches.
    forbidden = []
    negatives = {
        Effect.FILE_READ: r"(?:不要|禁止|不得|不允许|别|勿|不许).{0,8}(?:读取|读文件)|(?:do not|don't|never).{0,8}read",
        Effect.FILE_WRITE: r"(?:不要|禁止|不得|不允许|别|勿|不许).{0,8}(?:修改|写入|写文件|改动|编辑|删除|创建|添加|预订)|(?:do not|don't|never)(?!\s+forget).{0,8}\b(?:write|modify|edit|change|delete|create|add|append|remove|reserve|book|invite|update|schedule|reschedule|cancel)\b",
        Effect.GIT_COMMIT: r"(?:不要|禁止|不得|不允许|别|勿|不许).{0,8}(?:commit|提交)|(?:do not|don't|never).{0,8}commit",
        Effect.DELEGATE: r"(?:不要|禁止|不得|不允许|别|勿|不许).{0,8}(?:委派|委托|子.?agent)|(?:do not|don't|never).{0,8}delegate",
        Effect.MEMORY_WRITE: r"(?:不要|禁止|不得|不允许).{0,12}(?:保存记忆|写入记忆|持久化)|(?:do not|don't|never).{0,8}(?:persist|remember|save memory)",
        Effect.MEMORY_READ: r"(?:不要|禁止|不得|不允许).{0,8}(?:读取记忆|读取memory)|(?:do not|don't|never).{0,8}(?:recall|read memory)",
        Effect.GIT_PUSH: r"(?:不要|禁止|不得|不允许).{0,8}(?:push|推送)|(?:do not|don't|never).{0,8}push",
        Effect.NET_EGRESS: r"(?:不要|禁止|不得|不允许).{0,8}(?:上传|发送|外发|联网)|(?:do not|don't|never)(?!\s+forget).{0,8}\b(?:upload|send|network|post|share|forward|transfer|pay)\b",
        Effect.EXEC: r"(?:不要|禁止|不得|不允许).{0,8}(?:执行|运行)|(?:do not|don't|never).{0,8}(?:execute|run)",
    }
    for effect, pattern in negatives.items():
        if re.search(pattern, task, re.I):
            forbidden.append(effect)
    if re.search(r"只读|read[- ]only|no changes", task, re.I):
        forbidden.extend(
            [Effect.FILE_WRITE, Effect.GIT_COMMIT, Effect.GIT_PUSH, Effect.MEMORY_WRITE]
        )
    if re.search(r"离线|offline|no network|不联网", task, re.I):
        forbidden.append(Effect.NET_EGRESS)
    forbidden = list(dict.fromkeys(forbidden))
    effects = [e for e in effects if e in maximum and e not in forbidden]
    unresolved = [e.value for e in maximum if e not in effects and e not in forbidden]
    return IntentIR(
        actor=actor,
        permission_snapshot_hash=digest(
            {
                "actor": actor,
                "scopes": [scope],
                "ceiling": [e.value for e in maximum],
                "sensitive_access": "DENY",
            }
        ),
        goal=goal,
        allowed_scopes=[scope],
        allowed_effects=effects,
        maximum_effects=maximum,
        forbidden_effects=forbidden,
        unresolved=unresolved,
        evidence_source_refs=[uid("user")],
        parser_version="templates-1.2",
        authorized_destination_hashes=explicit_destinations(task)
        if Effect.NET_EGRESS in effects
        else [],
    )


def align(intent: IntentIR, action: ActionIR) -> AlignmentResult:
    errors = []
    if not action.scope_allowed and any(
        e
        in {
            Effect.FILE_READ,
            Effect.FILE_WRITE,
            Effect.GIT_COMMIT,
            Effect.GIT_PUSH,
            Effect.EXEC,
        }
        for e in action.effects
    ):
        errors.append("SCOPE_VIOLATION")
    missing = [e for e in action.effects if e not in intent.allowed_effects]
    if missing:
        errors.append("EFFECT_ESCALATION")
    if (
        action.resource_class in {"SECRET", "CREDENTIAL"}
        and intent.sensitive_access != "ALLOW"
    ):
        errors.append("SENSITIVE_ACCESS_NOT_AUTHORIZED")
    if any(e in intent.forbidden_effects for e in action.effects):
        errors.append("EXPLICIT_DENY")
    return AlignmentResult(
        aligned=not errors,
        deviation_types=errors,
        explanation="任务范围与动作一致"
        if not errors
        else "；".join(
            {
                "SCOPE_VIOLATION": "动作超出当前任务范围",
                "EFFECT_ESCALATION": "候选动作包含尚未明确授权的副作用",
                "SENSITIVE_ACCESS_NOT_AUTHORIZED": "任务未授权读取敏感凭据",
                "EXPLICIT_DENY": "动作违反任务中明确的禁止要求",
            }[e]
            for e in errors
        ),
    )
