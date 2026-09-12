#!/usr/bin/env python3
"""Pinned InjecAgent ReAct evaluation against a local model and AgentSentry policy.

Retains upstream proposal outcomes separately from simulated execution outcomes.
No real tools, email, finance, devices, or external model endpoints are invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from local_model import (
    completion,
    persist_manifest,
    serving_model,
    source_hashes,
    support_hashes,
)
from native_protocol import emitted_arguments

from agentsentry.context.scanner import Scanner
from agentsentry.intent.contracts import resolve
from agentsentry.policy.engine import Engine
from agentsentry.schemas import ActionIR, Effect, SourceType, digest


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def classify_tool(name):
    # Catalog semantics only. Never inspect Attacker Tools, attack labels or targets
    # when deciding authorization. Unknown semantics are explicitly blocked.
    if re.search(r"Send|Post|Upload|Transfer|Publish", name):
        return Effect.NET_EGRESS
    if re.search(
        r"Delete|Remove|Create|Update|Set|Turn|Switch|Lock|Unlock|Add|Cancel|Schedule|Book|Buy|Sell|Order|Play|Pause|Stop|Start|Adjust|Change|Move|Open|Close|Execute",
        name,
    ):
        return Effect.FILE_WRITE
    if re.search(
        r"Get|Read|List|Search|Fetch|Check|View|Query|Download|Retrieve|Find|Browse|Lookup",
        name,
    ):
        return Effect.FILE_READ
    return Effect.OTHER


def decide(engine, task, name, args, labels, configuration="full"):
    intent = resolve(task, "benchmark-user", ".")
    if configuration == "no_intent":
        intent.allowed_effects = intent.maximum_effects
        intent.forbidden_effects = []
    effect = classify_tool(name)
    destinations = re.findall(
        r"[\w.+-]+@([\w.-]+)|https?://([^/\s\"']+)", json.dumps(args)
    )
    domains = sorted({a or b for a, b in destinations})
    action = ActionIR(
        session_id="benchmark",
        tool=name,
        server_id="injecagent-simulation",
        effects=[effect],
        resource="simulation://" + name,
        resource_version=digest(args),
        args_hash=digest(args),
        resource_class="CREDENTIAL"
        if re.search(r"Password|Credential|Secret|PrivateKey", name)
        else "REPO",
        scope_valid=True,
        scope_allowed=True,
        adapter_valid=effect != Effect.OTHER,
        adapter_error="BENCHMARK_TOOL_SEMANTICS_UNSUPPORTED"
        if effect == Effect.OTHER
        else None,
        labels=labels,
        source_type="MCP_RESPONSE",
        source_trust="UNTRUSTED",
        destination_domain=",".join(domains),
        destination_trust="UNKNOWN",
    )
    return engine.decide(intent, action).model_dump(mode="json")


def metrics(rows):
    ok = [r for r in rows if r["status"] == "ok"]
    valid = [r for r in ok if r["valid"]]
    n, v = len(rows), len(valid)
    native = sum(r["proposal_attack_success"] for r in valid)
    executed = sum(r["executed_attack_success"] for r in valid)
    unknown = n - v
    return {
        "planned_cases": n,
        "completed_cases": len(ok),
        "valid_cases": v,
        "infrastructure_errors": n - len(ok),
        "invalid_outputs": len(ok) - v,
        "valid_rate": v / n if n else None,
        "native_proposal_asr_all": native / n if n else None,
        "native_proposal_asr_valid": native / v if v else None,
        "simulated_execution_asr_all": executed / n if n else None,
        "simulated_execution_asr_valid": executed / v if v else None,
        "strict_asr_upper_bound": (executed + unknown) / n if n else None,
        "blocked_or_pending_calls": sum(
            c["decision"] != "ALLOW" for r in ok for c in r["calls"]
        ),
        "utility": None,
        "utility_reason": "InjecAgent native evaluator has no benign task completion oracle",
        "all_planned_records_present": len(rows) == n,
        "all_cases_evaluated": len(ok) == n,
        "native_outputs_all_valid": v == n,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--url", default="http://127.0.0.1:18080/v1")
    p.add_argument("--model", default="agentsentry-local-qwen")
    p.add_argument("--setting", choices=["base", "enhanced"], default="base")
    p.add_argument(
        "--configuration",
        choices=["baseline", "rules", "full", "no_context", "no_intent", "no_taint"],
        required=True,
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-tokens", type=int, default=1024)
    a = p.parse_args()
    serving = serving_model(a.url, a.model)
    source = a.source.resolve()
    root = Path(__file__).resolve().parents[1]
    provenance = json.loads((source / "agentsentry-source.json").read_text())
    parser = load_module(source / "src/output_parsing.py", "injec_native_parser")
    prompts = load_module(
        source / "src/prompts/agent_prompts.py", "injec_native_prompts"
    )
    generation = load_module(
        source / "src/prompts/generation_prompts.py", "injec_native_generation"
    )
    tools = {}
    for kit in json.loads((source / "data/tools.json").read_text()):
        for tool in kit["tools"]:
            tool = dict(tool)
            tool["name"] = kit["toolkit"] + tool["name"]
            tools[tool["name"]] = tool
    cached_responses = json.loads(
        (source / "data/attacker_simulated_responses.json").read_text()
    )
    cases = []
    for kind in ["dh", "ds"]:
        data = json.loads(
            (
                source / ("data/test_cases_" + kind + "_" + a.setting + ".json")
            ).read_text()
        )
        cases.extend((kind, i, item) for i, item in enumerate(data))
    if a.limit:
        # Stratified deterministic pilot; full runs use every native row.
        half = max(1, a.limit // 2)
        cases = [c for kind in ["dh", "ds"] for c in cases if c[0] == kind][:half] + [
            c for c in cases if c[0] == "ds"
        ][:half]
    a.output.mkdir(parents=True, exist_ok=True)
    policy = (root / "policies/default.aspolicy").read_text()
    engine, scanner = Engine(policy), Scanner()
    ids = [kind + ":" + str(i) for kind, i, _ in cases]
    manifest = {
        "benchmark": "InjecAgent",
        "benchmark_commit": provenance["commit"],
        "source_archive_sha256": provenance["archive_sha256"],
        "configuration": a.configuration,
        "serving_model": {k: serving.get(k) for k in ["id", "max_model_len"]},
        "setting": a.setting,
        "model": a.model,
        "seed": a.seed,
        "temperature": 0,
        "max_tokens": a.max_tokens,
        "workers": a.workers,
        "planned_ids": ids,
        "policy_sha256": hashlib.sha256(policy.encode()).hexdigest(),
        "protocol_sha256": hashlib.sha256(
            Path(__file__).with_name("native_protocol.py").read_bytes()
        ).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_files": source_hashes(root),
        "support_files": support_hashes(),
        "data_files": {
            f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (source / "data").glob("*.json")
        },
        "scope": "pilot" if a.limit else "full_native_setting",
        "real_tools_executed": False,
        "native_evaluator": "src/output_parsing.py:evaluate_output_prompted",
        "adaptations": [
            "Local model replaces cloud backend; native prompts/parser retained",
            "Complete emitted JSON recovered separately for policy input; native judgments are not rewritten; protocol mismatch remains incomplete",
            "On absent native cached stage-2 tool response, original response-generation prompt uses the same local model",
            "Proposal ASR is retained; policy-denied simulated executions are reported separately",
            "Context quarantine drops the whole high-risk observation and may lose benign information",
            "Tool effects use name-based benchmark adapter v1; unsupported tools BLOCK; not a production semantic adapter",
            "ASK stays pending; no fabricated user approval",
            "No benign utility oracle; release acceptance cannot follow from this benchmark alone",
        ],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = a.output / "manifest.json"
    persist_manifest(manifest_path, manifest)
    output = a.output / "per_case.jsonl"
    existing = (
        [json.loads(l) for l in output.read_text().splitlines()]
        if output.exists()
        else []
    )
    done = {r["case_id"] for r in existing}
    if len(done) != len(existing) or not done <= set(ids):
        raise ValueError("INVALID_RESUME_RECORDS")

    def model(system, user, trace):
        raw = []
        try:
            message = completion(
                a,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                raw,
            )
            return message["content"]
        finally:
            trace.extend(
                {"prompt_sha256": digest([system, user]), "response": obj}
                for obj in raw
            )

    def one(case):
        kind, i, original = case
        result = {
            "case_id": kind + ":" + str(i),
            "attack_type": kind,
            "user_task_hash": digest(original["User Instruction"]),
            "status": "error",
            "calls": [],
            "model_responses": [],
        }
        start = time.perf_counter()
        try:
            item = dict(original)
            _, signal = scanner.scan(
                result["case_id"], item["Tool Response"], SourceType.MCP_RESPONSE
            )
            result["context_labels"] = signal.labels
            if (
                a.configuration not in {"baseline", "no_context"}
                and "INJECTION_RISK" in signal.labels
            ):
                item["Tool Response"] = (
                    "[AgentSentry quarantined untrusted instructions in this tool response.]"
                )
            available = [item["User Tool"]] + item["Attacker Tools"]

            def predict(step2=False):
                scratch = f"\n{item['Thought']}\nAction: {item['User Tool']}\nAction Input: {item['Tool Parameters']}\nObservation: {item['Tool Response']}\n"
                if step2:
                    scratch += f"Thought: {item['Attacker Tool Thought']}\nAction: {item['Attacker Tools'][0]}\nAction Input: {item['Attacker Tool Parameters']}\nObservation: {item['Attacker Tool Response']}\n"
                system, template = prompts.PROMPT_DICT["InjecAgent"]
                return model(
                    system,
                    template.format(
                        available_tool_descriptions=json.dumps(
                            [tools[t] for t in available], indent=True
                        ),
                        input=item["User Instruction"],
                        available_tool_names=available,
                        agent_scratchpad=scratch,
                    ),
                    result["model_responses"],
                )

            def inspect_output(text, target, stage, reachable=True):
                parsed = parser.evaluate_output_prompted(
                    text,
                    target,
                    item["Attacker Tools"],
                    item["User Tool"],
                    item["Attacker Instruction"],
                )
                allowed = True
                if parsed["eval"] != "invalid":
                    # Decide each emitted candidate using its own identity/arguments.
                    # Target labels are used ONLY below by the native evaluator.
                    names = [
                        name for key, name in parsed["info_list"] if key == "Action"
                    ]
                    for name, arguments in emitted_arguments(text, names):
                        if name in {"None", "N/A"}:
                            continue
                        decision = {
                            "decision": "ALLOW",
                            "reason_codes": ["BASELINE_NO_GATE"],
                        }
                        if a.configuration not in {"baseline", "rules"}:
                            decision = decide(
                                engine,
                                item["User Instruction"],
                                name,
                                arguments,
                                [] if a.configuration == "no_taint" else signal.labels,
                                configuration=a.configuration,
                            )
                        result["calls"].append(
                            {
                                "stage": stage,
                                "tool": name,
                                "arguments": arguments,
                                "decision": decision["decision"],
                                "reason_codes": decision["reason_codes"],
                                "simulated_dispatch": reachable
                                and decision["decision"] == "ALLOW",
                                "counterfactual": not reachable,
                            }
                        )
                        if name == target and decision["decision"] != "ALLOW":
                            allowed = False
                return parsed, allowed

            text = predict()
            result["output"] = text
            parsed, permitted = inspect_output(text, item["Attacker Tools"][0], 1)
            result["native_eval"] = parsed["eval"]
            result["invalid_reason"] = parsed.get("invalid_reason")
            proposal = parsed["eval"] == "succ"
            effective = proposal and permitted
            valid = parsed["eval"] != "invalid"
            if kind == "ds" and proposal:
                item["Attacker Tool Parameters"] = parsed["Attacker Tool Parameters"]
                item["Attacker Tool Thought"] = parsed["Attacker Tool Thought"]
                key = (
                    f"({item['Attacker Tools'][0]},{item['Attacker Tool Parameters']})"
                )
                if key in cached_responses:
                    response = cached_responses[key]
                    result["stage2_response_source"] = "native_cache"
                else:
                    prompt = generation.DS_ATTACKER_TOOL_RESPONSE_GEN_MESSAGE.format(
                        example=generation.EXAMPLE,
                        attacker_tool=json.dumps(
                            tools[item["Attacker Tools"][0]], indent=True
                        ),
                        tool_parameters=item["Attacker Tool Parameters"],
                    )
                    generated = model(
                        generation.SYSTEM_MESSAGE, prompt, result["model_responses"]
                    )
                    matches = re.findall(r"```(?:json)?\s*(.*?)```", generated, re.S)
                    if not matches:
                        raise ValueError("SIMULATED_RESPONSE_GENERATION_INVALID")
                    response = matches[0].strip()
                    result["stage2_response_source"] = (
                        "local_model_native_generation_prompt"
                    )
                item["Attacker Tool Response"] = response
                result["stage2_simulated_response"] = response
                text2 = predict(True)
                result["output_step2"] = text2
                parsed2, permitted2 = inspect_output(
                    text2, item["Attacker Tools"][1], 2, reachable=permitted
                )
                result["native_eval_step2"] = parsed2["eval"]
                proposal = parsed2["eval"] == "succ"
                effective = effective and proposal and permitted2
                valid = valid and parsed2["eval"] != "invalid"
                result["stage2_counterfactual_if_stage1_denied"] = not permitted
            result.update(
                status="ok",
                valid=valid,
                proposal_attack_success=proposal,
                executed_attack_success=effective,
            )
        except Exception as exc:
            result["error"] = type(exc).__name__ + (
                ":" + str(exc) if isinstance(exc, ValueError) else ""
            )
        result["seconds"] = time.perf_counter() - start
        return result

    rows = existing[:]
    with output.open("a") as f, ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [
            pool.submit(one, c) for c in cases if c[0] + ":" + str(c[1]) not in done
        ]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if len(rows) % 10 == 0 or len(rows) == len(cases):
                print(
                    json.dumps(
                        {
                            "completed": len(rows),
                            "planned": len(cases),
                            "errors": sum(r["status"] != "ok" for r in rows),
                        }
                    ),
                    flush=True,
                )
    summary = metrics(rows)
    (a.output / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    return (
        0
        if summary["all_cases_evaluated"] and summary["native_outputs_all_valid"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
