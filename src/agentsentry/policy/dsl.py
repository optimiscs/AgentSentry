from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass

from lark import Lark, Transformer, v_args

GRAMMAR = r"""
start: rule+
rule: "rule" NAME "severity" NAME "overridable" BOOL "{" "when" expr "then" NAME "(" ESCAPED_STRING ")" "}"
?expr: expr "or" conjunction -> or_expr
     | conjunction
?conjunction: conjunction "and" unary -> and_expr
            | unary
?unary: "not" unary -> not_expr
      | "(" expr ")"
      | term COMP value -> compare
      | term -> truth
?term: PATH "(" [arguments] ")" -> call
     | PATH -> field
arguments: value ("," value)*
?value: ESCAPED_STRING -> string
      | SIGNED_NUMBER -> number
      | NAME -> symbol
COMP: "==" | "!=" | ">=" | "<=" | ">" | "<"
BOOL: "true" | "false"
PATH: /[a-z_]+(?:\.[a-z_]+)+/
NAME: /[A-Za-z_][A-Za-z_0-9-]*/
%import common.ESCAPED_STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
%ignore /#[^\n]*/
"""
FIELDS = {
    "action.effect",
    "action.tool",
    "action.server",
    "resource.class",
    "resource.valid",
    "resource.scope_valid",
    "resource.scope_allowed",
    "destination.domain",
    "destination.trust",
    "intent.sensitive_access",
    "source.type",
    "source.trust",
    "agent.depth",
    "approval.valid",
}
CALLS = {
    "resource.matches",
    "intent.allows",
    "intent.scope_contains",
    "intent.destination_matches",
    "flow.has",
}


@dataclass(frozen=True)
class Rule:
    name: str
    severity: str
    overridable: bool
    expression: tuple
    decision: str
    reason: str


@v_args(inline=True)
class Build(Transformer):
    def start(self, *rules):
        return list(rules)

    def rule(self, name, severity, override, expression, decision, reason):
        if str(decision) not in {"ALLOW", "ASK", "BLOCK"} or str(severity) not in {
            "low",
            "medium",
            "high",
            "critical",
        }:
            raise ValueError("Invalid rule decision or severity")
        return Rule(
            str(name),
            str(severity),
            str(override) == "true",
            expression,
            str(decision),
            json.loads(reason),
        )

    def string(self, token):
        return json.loads(token)

    def number(self, token):
        return float(token)

    def symbol(self, token):
        return {"true": True, "false": False}.get(str(token), str(token))

    def field(self, name):
        if str(name) not in FIELDS:
            raise ValueError(f"Unknown field: {name}")
        return ("field", str(name))

    def arguments(self, *args):
        return list(args)

    def call(self, name, args=None):
        if str(name) not in CALLS or not args or len(args) != 1:
            raise ValueError(f"Unknown predicate or arity: {name}")
        return ("call", str(name), args[0])

    def compare(self, left, op, right):
        return ("compare", left, str(op), right)

    def truth(self, term):
        return ("truth", term)

    def and_expr(self, a, b):
        return ("and", a, b)

    def or_expr(self, a, b):
        return ("or", a, b)

    def not_expr(self, a):
        return ("not", a)


class PolicySyntaxError(ValueError):
    pass


class Policy:
    def __init__(self, text: str):
        if len(text) > 65536:
            raise PolicySyntaxError("Policy too large")
        try:
            self.rules = Build().transform(Lark(GRAMMAR, parser="lalr").parse(text))
        except Exception as exc:
            raise PolicySyntaxError(str(exc)) from exc
        if len({r.name for r in self.rules}) != len(self.rules):
            raise PolicySyntaxError("Duplicate rule names")
        enums = {
            "action.effect": {
                "FILE_READ",
                "FILE_WRITE",
                "NET_EGRESS",
                "EXEC",
                "GIT_COMMIT",
                "GIT_PUSH",
                "DELEGATE",
                "MEMORY_READ",
                "MEMORY_WRITE",
                "OTHER",
            },
            "resource.class": {
                "UNKNOWN",
                "PUBLIC",
                "REPO",
                "SECRET",
                "CREDENTIAL",
                "SYSTEM",
                "EXTERNAL",
            },
            "destination.trust": {"UNKNOWN", "UNTRUSTED", "TRUSTED"},
            "source.trust": {"UNKNOWN", "UNTRUSTED", "TRUSTED"},
            "source.type": {
                "USER",
                "WEB",
                "DOCUMENT",
                "ISSUE",
                "MCP_DESCRIPTION",
                "MCP_RESPONSE",
                "MEMORY",
                "SUB_AGENT",
            },
            "intent.sensitive_access": {"ALLOW", "DENY"},
        }
        booleans = {
            "resource.valid",
            "resource.scope_valid",
            "resource.scope_allowed",
            "approval.valid",
        }

        def validate(node):
            kind = node[0]
            if kind in {"and", "or"}:
                validate(node[1])
                validate(node[2])
            elif kind == "not":
                validate(node[1])
            elif kind == "truth":
                if node[1][0] == "field" and node[1][1] not in booleans:
                    raise PolicySyntaxError("Boolean predicate required")
            elif kind == "compare":
                left, op, right = node[1:]
                if left[0] == "field":
                    field = left[1]
                    if field in enums and right not in enums[field]:
                        raise PolicySyntaxError("Unknown enum value")
                    if field in booleans and not isinstance(right, bool):
                        raise PolicySyntaxError("Boolean comparison required")
                    if field == "agent.depth" and (
                        isinstance(right, bool) or not isinstance(right, (int, float))
                    ):
                        raise PolicySyntaxError("Numeric comparison required")
                    if field != "agent.depth" and op not in {"==", "!="}:
                        raise PolicySyntaxError("Ordering only supports agent.depth")
            if (
                kind == "call"
                and node[1] == "intent.allows"
                and node[2] not in enums["action.effect"]
            ):
                raise PolicySyntaxError("Unknown effect")
            if kind in {"truth", "compare"}:
                validate(node[1])

        for rule in self.rules:
            validate(rule.expression)
        self.version = hashlib.sha256(text.encode()).hexdigest()
        self.text = text

    def matches(self, rule: Rule, fields: dict, functions: dict) -> bool:
        def value(node):
            kind = node[0]
            if kind == "field":
                return fields[node[1]]
            if kind == "call":
                if node[1] == "resource.matches":
                    return fnmatch.fnmatchcase(fields["resource.path"], str(node[2]))
                return functions[node[1]](node[2])
            if kind == "truth":
                v = value(node[1])
                if not isinstance(v, bool):
                    raise PolicySyntaxError("Nonboolean predicate")
                return v
            if kind == "not":
                return not value(node[1])
            if kind == "and":
                return value(node[1]) and value(node[2])
            if kind == "or":
                return value(node[1]) or value(node[2])
            if kind == "compare":
                a, op, b = value(node[1]), node[2], node[3]
                if isinstance(a, list):
                    if op == "==":
                        return b in a
                    if op == "!=":
                        return b not in a
                    raise PolicySyntaxError("List ordering is not defined")
                if op == "==":
                    return a == b
                if op == "!=":
                    return a != b
                if op == ">=":
                    return a >= b
                if op == "<=":
                    return a <= b
                if op == ">":
                    return a > b
                if op == "<":
                    return a < b
            raise PolicySyntaxError("Invalid AST")

        return bool(value(rule.expression))
