#!/usr/bin/env python3
"""Inventory MSB's native scenario loop without starting tools or reading .env."""

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PINS = {
    "main.py": "f87bc067284d373828995d8b7d90a42e3347e8ece8d32da01e0dd9d7ed196821",
    "metrics.py": "8ddd708548a2e11e7e54e256ac30f8a0cedf1b14cc667d75f704eb78d59b7682",
    "setup.py": "a44218278f881e4d583fd6e0dc0e2b2a14be9d44fff7d073f03842e0bb944c68",
}
RESTRICTED = ("tool_transfer", "name_overlap", "out_of_scope_parameter", "preference_manipulation")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def native_names(attack, agent, task, tool, goal):
    safe_task = task[:20].replace(" ", "_").replace(":", "").replace("/", "").replace(".", "")
    log = "#".join([attack, "local-model", agent, safe_task, tool, goal])
    operation = "#".join("_".join(piece[:1] for piece in component.split("_"))
                         for component in log.replace("-", "_").split("#"))
    return log, operation


def prepare(source, output):
    provenance = json.loads((source / "agentsentry-source.json").read_text())
    if provenance["commit"] != "c1d6a70171e4d2c44c87a2ae909d13df00c6aa8d":
        raise ValueError("UNREVIEWED_MSB_COMMIT")
    for name, expected in PINS.items():
        if sha(source / name) != expected:
            raise ValueError("PINNED_MSB_CODE_CHANGED:" + name)
    agents = jsonl(source / "data/agent_task.jsonl")
    goals = jsonl(source / "data/attack_task.jsonl")
    attack_types = jsonl(source / "data/attack_type.jsonl")[0]["attack_type"]
    normal = source / "data/tools/normal_tools"
    attacks = source / "data/tools/attack_tools"
    scenarios, skipped, unavailable = [], [], []
    logs, operations = defaultdict(list), defaultdict(list)
    for attack in attack_types:
        for agent in agents:
            name = agent["agent_name"]
            if (name == "information_retrieval") != (attack == "search_term_deception"):
                continue
            for task_index, item in enumerate(agent["task_tool"]):
                tool = item["tool"]
                directory = attacks / name / tool
                # Mirrors reviewed main.py tool_exist; its attack_type parameter is unused.
                if any(part in attack for part in RESTRICTED) and (name == "image_generation" or not directory.is_dir()):
                    skipped.append({"attack_type": attack, "agent": name, "task_index": task_index,
                                    "tool": tool, "reason": "NATIVE_TOOL_EXIST_FILTER"})
                    continue
                for goal in goals:
                    identifier = "/".join([attack, name, str(task_index), goal["attack_task"]])
                    log, operation = native_names(attack, name, item["task"], tool, goal["attack_task"])
                    required = []
                    if attack not in {"out_of_scope_parameter", "search_term_deception", "tool_transfer"}:
                        required.append(str((normal / (tool + ".json")).relative_to(source)))
                    if attack not in {"out_of_scope_parameter", "tool_transfer", "preference_manipulation-out_of_scope_parameter"}:
                        support = "Desktop_Commander" if goal["attack_task"] == "kill_process" else "Filesystem_MCP_Server"
                        required.append("data/tools/support_tools/" + support + ".json")
                    if any(part in attack for part in RESTRICTED):
                        config_path = directory / "mcp_config.json"
                        required.append(str(config_path.relative_to(source)))
                        if config_path.exists():
                            config = json.loads(config_path.read_text())
                            base = next(iter(config["mcpServers"].values()))["args"][3]
                            suffix = "preference_manipulation" if attack == "preference_manipulation-simulated_user" else attack
                            required.append(str((directory / base.replace(".py", "-" + suffix + ".py")).relative_to(source)))
                            if attack == "tool_transfer":
                                required.append(str((directory / base.replace(".py", "-out_of_scope_parameter.py")).relative_to(source)))
                    missing = [path for path in required if not (source / path).is_file()]
                    if missing:
                        unavailable.append({"case_id": identifier, "missing_files": missing})
                    record = {"case_id": identifier, "attack_type": attack, "agent": name, "task_index": task_index,
                              "task_sha256": hashlib.sha256(item["task"].encode()).hexdigest(), "tool_config": tool,
                              "evaluator_attack_goal": goal["attack_task"], "required_source_files": required,
                              "native_log_name": log, "native_output_basename": operation,
                              "status": "SOURCE_FILES_MISSING" if missing else "SOURCE_PRESENT_EXECUTION_NOT_RUN"}
                    scenarios.append(record)
                    logs[log].append(identifier)
                    operations[operation].append(identifier)
    if len({r["case_id"] for r in scenarios}) != len(scenarios):
        raise ValueError("DUPLICATE_MSB_SCENARIO")
    configurations = []
    for path in sorted((source / "data/tools").rglob("*.json")):
        config = json.loads(path.read_text())
        for name, server in config.get("mcpServers", {}).items():
            arguments = server.get("args", [])
            configurations.append({"file": str(path.relative_to(source)), "server_name": name,
                                   "command": server.get("command"), "environment_keys": sorted(server.get("env", {})),
                                   "has_version_latest": any("@latest" in arg for arg in arguments),
                                   "has_absolute_placeholder": any("/ABSOLUTE/" in arg for arg in arguments),
                                   "has_embedded_authorization_argument": any("authorization:" in arg.casefold() for arg in arguments),
                                   "sha256": sha(path)})
    source_paths = list(PINS) + ["data/agent_task.jsonl", "data/attack_task.jsonl", "data/attack_type.jsonl",
                                 "data/prompt_template.py", "scripts/utility.py", "config/all.yml", "requirements.txt", "LICENSE.txt"]
    source_paths += [str(p.relative_to(source)) for p in (source / "data/tools").rglob("*")
                     if p.is_file() and p.suffix in {".py", ".json"}]
    definitions = 0
    for path in attacks.rglob("*.py"):
        tree = ast.parse(path.read_text())
        definitions += sum(any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
                               for d in n.decorator_list) for n in ast.walk(tree)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    output.mkdir(parents=True, exist_ok=False)
    index = output / "scenario-index.jsonl"
    index.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in scenarios))
    report = {"status": "PROTOCOL_INVENTORY_ONLY_NO_MCP_TOOLS_EXECUTED", "generated_at": datetime.now(timezone.utc).isoformat(),
              "source": provenance, "source_files": {name: sha(source / name) for name in sorted(set(source_paths))},
              "preparation_script_sha256": sha(Path(__file__)), "scenario_index_sha256": sha(index),
              "agents": len(agents), "user_tasks": sum(len(a["task_tool"]) for a in agents),
              "native_all_config_scenarios_per_model": len(scenarios),
              "scenarios_per_attack": dict(Counter(row["attack_type"] for row in scenarios)),
              "native_filtered_agent_tasks": len(skipped), "scenarios_with_missing_files": unavailable,
              "native_log_collisions": [v for v in logs.values() if len(v) > 1],
              "native_output_collisions": [v for v in operations.values() if len(v) > 1],
              "server_configurations": configurations,
              "static_decorated_function_definitions_across_attack_variants": definitions,
              "limitations": [
                  "Native scenarios use real MCP tools, environment mutations and logs. A static detector scan cannot reproduce this benchmark.",
                  "Configured external services and latest package versions are not pinned or proven available by this inventory.",
                  "Embedded authorization arguments and .env values were not loaded into any runtime or copied into the report.",
                  "Upstream setup.py rewrites configurations and moves a patched agent file into LangChain; it was not executed.",
                  "Native check_result skips incomplete logs. Our future report must retain missing/incomplete outcomes and conservative bounds separately.",
                  "Several operation attacks score file existence; parameter attacks and user utility use log proxies. Separate actual dispatch/state checks are required.",
                  "Static decorated function counts include variants and do not verify the paper's remotely supplied tool count.",
                  "No benchmark model, MCP server, attack tool or target process was executed by this inventory.",
              ]}
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.source, args.output)
    print(json.dumps({key: report[key] for key in ("status", "agents", "user_tasks", "native_all_config_scenarios_per_model", "scenarios_per_attack")}))
