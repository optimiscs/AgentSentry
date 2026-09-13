"""Replay recorded actor proposals and a frozen plan, using a live guard model.

Stops after the first effectful candidate. Only native in-memory tools execute;
no native utility/attack score is produced. This is a protocol diagnostic.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite import get_suite
import run_agentdojo
from agentsentry.schemas import canonical, digest
from local_model import source_hashes, support_hashes, serving_model

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--candidate", type=Path, required=True)
parser.add_argument("--records", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--url", default="http://127.0.0.1:18080/v1")
args = parser.parse_args()
assert Path(run_agentdojo.__file__).resolve().parents[1] == args.candidate.resolve()
assert not args.output.exists(), "NEW_DIAGNOSTIC_OUTPUT_REQUIRED"
args.output.mkdir(parents=True)
config = argparse.Namespace(
    model="Qwen/Qwen3.5-9B", url=args.url, configuration="full",
    intent_mode="task-plan", max_steps=15, max_tokens=4096,
    guard_max_tokens=4096, guard_format="json_schema", seed=0,
)
rows = [json.loads(line) for line in args.records.read_text().splitlines()]
policy = (args.candidate / "policies/default.aspolicy").read_text()
selected = []
for row in rows:
    if row["injection_task"] is not None:
        continue
    effectful = [c for c in row["calls"] if c["tool"] not in run_agentdojo.READ]
    if effectful:
        selected.append((row, effectful[0]))
manifest = {
    "kind": "recorded-actor-and-plan/live-guard diagnostic; not benchmark scores",
    "input_sha256": hashlib.sha256(args.records.read_bytes()).hexdigest(),
    "candidate": str(args.candidate), "source_files": source_hashes(args.candidate),
    "support_files": support_hashes(), "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "model": serving_model(config.url, config.model), "configuration": vars(config),
    "case_ids": [r["case_id"] for r, _ in selected],
}
(args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
errors = 0
for row, target in selected:
    prefix = []
    for response in row["model_responses"]:
        message = response["choices"][0]["message"]
        prefix.append(message)
        calls = message.get("tool_calls") or []
        if any(c["function"]["name"] not in run_agentdojo.READ for c in calls):
            assert len(calls) == 1, "DIAGNOSTIC_REQUIRES_SINGLE_FIRST_EFFECTFUL_CALL"
            break
    assert prefix and prefix[-1].get("tool_calls")
    original_plan = next(t for t in row["guard_trace"] if t["phase"] == "plan")
    replay = iter(prefix)
    complete = run_agentdojo.completion

    def model_call(config, messages, trace, *, tools=None, response_format=None):
        if response_format is not None:
            return complete(config, messages, trace, response_format=response_format)
        response = copy.deepcopy(next(replay, {"content": "Diagnostic prefix finished.", "tool_calls": None}))
        trace.append({"recorded_actor_replay": True, "choices": [{"message": response}]})
        return response

    pipeline = run_agentdojo.LocalPipeline(config, policy)
    live_guard = pipeline.guard_model
    guard_inputs = []

    def guard(phase, messages, schema):
        guard_inputs.append({"phase": phase, "messages": copy.deepcopy(messages), "schema": copy.deepcopy(schema)})
        if phase == "plan":
            assert digest(json.loads(messages[1]["content"])) == original_plan["input_hash"]
            return copy.deepcopy(original_plan["result"])
        return live_guard(phase, messages, schema)

    suite = get_suite("v1.2.2", row["suite"])
    user = suite.user_tasks[row["user_task"]]
    env = user.init_environment(suite.load_and_inject_default_environment({}))
    with patch.object(run_agentdojo, "completion", model_call), patch.object(pipeline, "guard_model", guard):
        pipeline.query(user.PROMPT, FunctionsRuntime(suite.tools), env)
    actual = [c for c in pipeline.calls if c["tool"] not in run_agentdojo.READ]
    assert len(actual) == 1 and actual[0]["tool"] == target["tool"]
    assert canonical(actual[0]["arguments"]) == canonical(target["arguments"])
    reads = len(pipeline.calls) - 1
    for original, replayed in zip(row["calls"][:reads], pipeline.calls[:reads]):
        for key in ["tool", "arguments", "tool_error", "context_labels"]:
            assert original[key] == replayed[key], (row["case_id"], key)
    original_data = [m["content"] for m in row["transcript"] if m["role"] == "tool"][:reads]
    replayed_data = [m["content"] for m in pipeline.transcript if m["role"] == "tool"][:reads]
    assert canonical(original_data) == canonical(replayed_data), "OBSERVATION_REPLAY_MISMATCH"
    errors += bool(pipeline.planner.failures)
    result = {
        "case_id": row["case_id"], "original_decision": target["decision"],
        "original_reason_codes": target["reason_codes"], "first_effectful_call": actual[0],
        "calls": pipeline.calls, "guard_trace": pipeline.planner.trace,
        "guard_model_responses": pipeline.guard_responses,
        "guard_inputs": guard_inputs, "guard_failures": pipeline.planner.failures,
        "native_evaluator_run": False,
    }
    with (args.output / "per_case.jsonl").open("a") as out:
        out.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps({"case_id": row["case_id"], "decision": actual[0]["decision"], "reason_codes": actual[0]["reason_codes"]}), flush=True)
(args.output / "complete.json").write_text(json.dumps({"status": "DIAGNOSTIC_ERRORS" if errors else "RECORDED_DIAGNOSTIC", "cases": len(selected), "errors": errors}) + "\n")
raise SystemExit(bool(errors))
