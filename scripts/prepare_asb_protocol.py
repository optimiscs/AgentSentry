#!/usr/bin/env python3
"""Prepare an ASB scenario index and audit memory snapshots without model calls.

Dataset labels are evaluator-only; this index must not be a defender tool allowlist.
No upstream entry point, environment file, embedding client or tool is executed.
"""

import argparse
import ast
import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import yaml

MODES = {
    "mixed": {"direct": True, "observation": True, "memory": True},
    "DPI_OPI": {"direct": True, "observation": True, "memory": False},
    "DPI_MP": {"direct": True, "observation": False, "memory": True},
    "OPI_MP": {"direct": False, "observation": True, "memory": True},
}


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def default_task_count(path):
    values = []
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "--task_num"
        ):
            values.extend(
                ast.literal_eval(k.value) for k in node.keywords if k.arg == "default"
            )
    if len(values) != 1 or type(values[0]) is not int or values[0] <= 0:
        raise ValueError("ASB_TASK_COUNT_DEFAULT_UNREVIEWED")
    return values[0]


def memory_inventory(path):
    before = fingerprint(path)
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as db:
        db.execute("PRAGMA query_only=ON")
        documents = [
            r[0]
            for r in db.execute(
                "SELECT string_value FROM embedding_metadata WHERE key='chroma:document'"
            )
        ]
        dimensions = [r[0] for r in db.execute("SELECT dimension FROM collections")]
        embeddings = db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert before == fingerprint(path), "READ_ONLY_INVENTORY_CHANGED_DATABASE"
    if any(not isinstance(text, str) or len(text) > 2_000_000 for text in documents):
        raise ValueError("UNEXPECTED_MEMORY_DOCUMENT")
    workflow_count = sum(
        bool(re.search(r"Workflow:\s*(\[.*?\]);", text, re.S)) for text in documents
    )
    return {
        "sha256": before,
        "embedding_rows": embeddings,
        "documents": len(documents),
        "dimensions": dimensions,
        "documents_with_native_workflow_pattern": workflow_count,
        "retrieval_executed": False,
        "note": "Document presence is not proof that the native query retrieves it. Cached vectors require the original embedding space.",
    }


def prepare(source, output):
    source = source.resolve()
    selected = [
        "data/agent_task.jsonl",
        "data/all_normal_tools.jsonl",
        "data/all_attack_tools.jsonl",
        "main_attacker.py",
        "scripts/agent_attack.py",
        "aios/utils/utils.py",
        "pyopenagi/agents/react_agent_attack.py",
        "pyopenagi/tools/simulated_tool.py",
    ]
    tasks = rows(source / selected[0])
    normal = rows(source / selected[1])
    attacks = rows(source / selected[2])
    count = default_task_count(source / "aios/utils/utils.py")
    agents = {row["agent_name"]: row for row in tasks}
    if len(agents) != len(tasks) or any(not row["tasks"] for row in tasks):
        raise ValueError("INVALID_ASB_TASK_CATALOG")
    if any(row["Corresponding Agent"] not in agents for row in attacks + normal):
        raise ValueError("UNKNOWN_ASB_AGENT")
    normal_names = {row["Tool Name"] for row in normal}
    attack_names = [row["Attacker Tool"] for row in attacks]
    overlap = normal_names & set(attack_names)
    if overlap:
        raise ValueError("AMBIGUOUS_NORMAL_ATTACK_TOOL_IDENTITY")
    scenarios = []
    configs = {}
    for mode, surfaces in MODES.items():
        relative = "config/" + mode + ".yml"
        selected.append(relative)
        config = yaml.safe_load((source / relative).read_text())
        if (
            config["attack_tool"] != ["all"]
            or config["read_db"] is not surfaces["memory"]
        ):
            raise ValueError("UNREVIEWED_ASB_CONFIG:" + mode)
        configs[mode] = {
            "source_config": relative,
            "surfaces": surfaces,
            "upstream_models": config["llms"],
            "attack_styles": config["attack_types"],
            "cases_per_model": 0,
        }
        for agent_name, agent in agents.items():
            for task_index, task in enumerate(agent["tasks"][:count]):
                for attack_row, attack in enumerate(attacks):
                    if attack["Corresponding Agent"] != agent_name:
                        continue
                    for style in config["attack_types"]:
                        case_id = (
                            f"{mode}/{style}/{agent_name}/{task_index}/{attack_row}"
                        )
                        scenarios.append(
                            {
                                "case_id": case_id,
                                "mode": mode,
                                "style": style,
                                "agent": agent_name,
                                "task_index": task_index,
                                "task_sha256": hashlib.sha256(
                                    task.encode()
                                ).hexdigest(),
                                "evaluator_attack_row": attack_row,
                            }
                        )
                        configs[mode]["cases_per_model"] += 1
    if len({s["case_id"] for s in scenarios}) != len(scenarios):
        raise ValueError("DUPLICATE_ASB_SCENARIO")
    memories = {
        str(path.relative_to(source)): memory_inventory(path)
        for path in sorted((source / "memory_db").rglob("chroma.sqlite3"))
    }
    report = {
        "status": "PROTOCOL_INVENTORY_ONLY_NOT_A_BENCHMARK_RUN",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": json.loads((source / "agentsentry-source.json").read_text()),
        "source_file_sha256": {name: fingerprint(source / name) for name in selected},
        "upstream_default_task_num": count,
        "catalog": {
            "agents": len(agents),
            "available_user_tasks": sum(len(r["tasks"]) for r in tasks),
            "normal_tools": len(normal),
            "attack_rows": len(attacks),
            "distinct_attack_tool_names": len(set(attack_names)),
            "duplicate_attack_names": {
                name: n for name, n in Counter(attack_names).items() if n > 1
            },
        },
        "modes": configs,
        "indexed_scenarios_for_one_model": len(scenarios),
        "memory_snapshots": memories,
        "remaining_protocol_requirements": [
            "Implement and validate local agent/workflow transport; no model run was performed here.",
            "Preserve native attack/utility text scores and separately record actual simulated dispatch.",
            "Do not feed evaluator labels, attack goal or row membership into defender authorization.",
            "Match native memory embedding/retrieval, or report a separately named adapted protocol; do not choose memory by attack labels.",
            "Declare the original trusted user request separately from the DPI-mutated runtime message; do not promote DPI text into authorization.",
            "Model and refusal-judge substitutions require explicit provenance. No paid API was called.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    index = output / "scenario-index.jsonl"
    index.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in scenarios)
    )
    report["scenario_index_sha256"] = fingerprint(index)
    (output / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "cases": result["indexed_scenarios_for_one_model"],
                "default_task_count": result["upstream_default_task_num"],
                "catalog": result["catalog"],
                "memory_snapshots": len(result["memory_snapshots"]),
            }
        )
    )
