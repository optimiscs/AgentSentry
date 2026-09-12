#!/usr/bin/env python3
"""Inspect two pinned ASB scoring functions without importing its cloud entry point."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/evidence/asb-evaluator-audit.json")
    )
    args = parser.parse_args()
    raw = (args.source / "main_attacker.py").read_text()
    tree = ast.parse(raw)
    names = {"check_attack_success", "check_original_success"}
    functions = [
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names
    ]
    if len(functions) != len(names):
        raise ValueError("NATIVE_FUNCTIONS_NOT_FOUND")
    # Only the already-reviewed pure scoring functions are evaluated, with a
    # restricted syntax/call surface and synthetic plain-data inputs. No imports,
    # decorators, annotations, defaults, dynamic calls, filesystem or network.
    allowed = {
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.Assign,
        ast.Name,
        ast.Store,
        ast.Load,
        ast.Constant,
        ast.For,
        ast.Expr,
        ast.Call,
        ast.Attribute,
        ast.If,
        ast.BoolOp,
        ast.And,
        ast.Compare,
        ast.IsNot,
        ast.In,
        ast.Break,
        ast.Return,
        ast.Tuple,
        ast.GeneratorExp,
        ast.comprehension,
    }
    for function in functions:
        if function.decorator_list or function.returns or function.args.defaults:
            raise ValueError("UNREVIEWED_FUNCTION_SIGNATURE")
        for node in ast.walk(function):
            if type(node) not in allowed:
                raise ValueError("UNREVIEWED_NATIVE_SYNTAX:" + type(node).__name__)
            if isinstance(node, ast.Attribute) and node.attr not in {
                "get",
                "items",
                "add",
                "expected_achivement",
            }:
                raise ValueError("UNREVIEWED_NATIVE_ATTRIBUTE")
            if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name)
                and node.func.id in {"set", "all"}
                or isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get", "items", "add"}
            ):
                raise ValueError("UNREVIEWED_NATIVE_CALL")
    namespace = {"__builtins__": {"set": set, "all": all}}
    exec(
        compile(
            ast.Module(body=functions, type_ignores=[]), "reviewed_asb_scores", "exec"
        ),
        namespace,
    )
    goal = "SYNTHETIC_ATTACK_GOAL_WITH_NO_DISPATCH"
    achievement = "SYNTHETIC_NORMAL_ACHIEVEMENT_WITH_NO_DISPATCH"
    attack = namespace["check_attack_success"](
        [{"role": "user", "content": goal}], None, goal
    )
    utility = namespace["check_original_success"](
        [{"role": "user", "content": achievement}],
        None,
        {"synthetic_tool": SimpleNamespace(expected_achivement=achievement)},
    )
    assert attack is True and utility is True
    report = {
        "status": "NATIVE_TEXT_PROXY_LIMITATION_CONFIRMED_NOT_A_BENCHMARK_RUN",
        "source": json.loads((args.source / "agentsentry-source.json").read_text()),
        "function_sha256": {
            f.name: hashlib.sha256(ast.get_source_segment(raw, f).encode()).hexdigest()
            for f in functions
        },
        "synthetic_checks": {
            "goal_in_user_message_scores_attack_success": attack,
            "achievement_in_user_message_scores_utility_success": utility,
            "executed_tool_count": 0,
        },
        "required_reporting": [
            "Preserve native text scores",
            "Report simulated dispatch outcomes separately",
            "Never treat echo/removal/refusal as demonstrated execution safety or task completion",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps({"status": report["status"], "checks": report["synthetic_checks"]})
    )


if __name__ == "__main__":
    main()
