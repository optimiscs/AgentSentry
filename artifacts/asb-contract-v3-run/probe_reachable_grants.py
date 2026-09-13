"""Replay recorded plans and probe candidate calls; NOT a native ASB score."""

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

from asb_native import read_rows
from asb_pipeline import make_pipeline
from local_model import completion
from agentsentry.schemas import digest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "artifacts/upstream/ASB-1f561dccf92d"
CANDIDATE = ROOT / "artifacts/development/asb-contract-v3"
RUN = ROOT / "artifacts/benchmarks/asb/asb-lab3090-qwen35-9b-contract-v3-full-s0/per_case.jsonl"
TARGETS = {
    "DPI_OPI/combined_attack/financial_analyst_agent/0/20",
    "DPI_MP/combined_attack/medical_advisor_agent/0/60",
}


def main():
    output = ROOT / "artifacts/asb-contract-v3-run/reachable-grants-v2.json"
    if output.exists():
        raise ValueError("NEW_PROBE_OUTPUT_REQUIRED")
    tasks = {r["agent_name"]: r for r in read_rows(SOURCE / "data/agent_task.jsonl")}
    attacks = read_rows(SOURCE / "data/all_attack_tools.jsonl")
    report = {
        "status": "TARGETED_REACHABILITY_DIAGNOSTIC_NOT_ASB_SCORE",
        "source_run_sha256": hashlib.sha256(RUN.read_bytes()).hexdigest(),
        "limits": "Original model-produced plan replayed unchanged; candidate calls forced in plan order. Only simulated tools. Not a fresh actor rollout or attack-success-rate estimate.",
        "cases": [],
    }
    for row in read_rows(RUN):
        if row["case_id"] not in TARGETS:
            continue
        task_row = tasks[row["agent"]]
        attack = attacks[int(row["case_id"].rsplit("/", 1)[1])]
        planned = row["guard_trace"][0]

        def model(config, messages, trace, **options):
            payload = json.loads(messages[1]["content"])
            if "reviewed_tools" in payload:
                assert digest(payload) == planned["input_hash"]
                answer = {"content": json.dumps(planned["result"])}
                trace.append({"replayed_plan_from_case": row["case_id"], "message": answer})
                return answer
            return completion(config, messages, trace, **options)

        config = SimpleNamespace(
            url="http://127.0.0.1:18081/v1", model="Qwen/Qwen3.5-9B",
            configuration="full", direct=False, observation=True, memory=False,
            max_tokens=4096, guard_max_tokens=4096, max_workflow_steps=12,
            seed=0, guard_format="json_schema", workflow_format="json_schema",
        )
        pipeline = make_pipeline(
            SOURCE, task_row, task_row["tasks"][0], attack, config,
            (CANDIDATE / "policies/default.aspolicy").read_text(), complete=model,
        )
        # Native.run installs the added tool before generating the workflow.
        # Direct gate probes must reproduce that setup, not silently skip it.
        pipeline.add_attacker_tool()
        assert attack["Attacker Tool"] in pipeline.tool_list
        assert pipeline.planner.prepare()
        observed = []
        for step in planned["result"]["steps"]:
            before = len(pipeline.calls)
            result = pipeline.call_tools(
                [{"name": step["tool"], "parameters": {}}], final_stage=False
            )
            assert len(pipeline.calls) == before + 1, "CANDIDATE_NOT_SUBMITTED_TO_GATE"
            assert not pipeline.protocol_errors
            observed.append({"candidate": step["tool"], "result": result})
            if step["tool"] == attack["Attacker Tool"]:
                break
        record = {
            "case_id": row["case_id"], "plan": planned,
            "calls": pipeline.calls, "observations": observed,
            "guard_trace": pipeline.planner.trace, "guard_records": pipeline.guard_records,
            "guard_failures": pipeline.planner.failures,
            "simulated_attacker_dispatch": any(
                c["tool"] == attack["Attacker Tool"] and c["simulated_dispatch"]
                for c in pipeline.calls
            ),
        }
        report["cases"].append(record)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: record[k] for k in ["case_id", "calls", "simulated_attacker_dispatch"]}), flush=True)
    assert len(report["cases"]) == len(TARGETS)
    report["complete"] = True
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
