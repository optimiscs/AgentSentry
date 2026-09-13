"""Paired live-guard diagnostic on hash-verified native tool observations.

This does not run an actor, tool dispatch or benchmark evaluator. Cohort labels
are analyst metadata and never enter the guard payload.
"""
import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from local_model import source_hashes, support_hashes, serving_model
from run_agentdojo import LocalPipeline
from agentsentry.schemas import digest

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--mode", choices=["nonthinking", "thinking"], required=True)
p.add_argument("--url", required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
control = Path(__file__).resolve().parent
candidate = root / "artifacts/development/context-filter-v3"
assert not a.output.exists(), "NEW_DIAGNOSTIC_OUTPUT_REQUIRED"
data_raw = (control / "paired-inputs.json").read_bytes()
items = json.loads(data_raw)["inputs"]
config = argparse.Namespace(
    model="Qwen/Qwen3.5-9B", url=a.url, configuration="promptarmor_adapted",
    intent_mode="task-plan", max_steps=15, max_tokens=4096, guard_max_tokens=4096,
    guard_format="json_schema", seed=0, guard_thinking=a.mode == "thinking", request_timeout=300,
)
manifest = {
    "benchmark": "ContextSanitizerDiagnostic", "scope": "selected_development_inputs",
    "native_evaluator_run": False, "configuration": vars(config),
    "planned_ids": [r["case_id"] for r in items],
    "inputs_sha256": hashlib.sha256(data_raw).hexdigest(),
    "source_files": source_hashes(candidate), "support_files": support_hashes(),
    "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "model": serving_model(config.url, config.model),
    "started_at": datetime.now(timezone.utc).isoformat(),
}
a.output.mkdir(parents=True)
(a.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
policy = (candidate / "policies/default.aspolicy").read_text()


def one(item):
    payload = item["input"]
    assert digest(payload) == item["input_hash"]
    pipeline = LocalPipeline(config, policy)
    row = {"case_id": item["case_id"], "cohort": item["cohort"], "input_hash": item["input_hash"],
           "status": "error", "started_at": datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    try:
        output = pipeline.sanitizer.sanitize(payload["original_user_request"],
            payload["tool_call"]["name"], payload["tool_call"]["arguments"], payload["tool_response"])
        row.update(status="ok", changed=output != payload["tool_response"], output_hash=digest(output))
    except Exception as exc:
        row.update(error=type(exc).__name__ + ":" + str(exc))
    row.update(seconds=time.monotonic() - started, sanitizer_trace=pipeline.sanitizer.trace,
               guard_failures=pipeline.sanitizer.failures, guard_model_responses=pipeline.guard_responses)
    return row


rows = []
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [pool.submit(one, item) for item in items]
    for future in as_completed(futures):
        row = future.result(); rows.append(row)
        with (a.output / "per_case.jsonl").open("a") as out:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({k: row.get(k) for k in ["case_id", "cohort", "status", "changed", "seconds"]}), flush=True)
metrics = {
    "planned": len(items), "recorded": len(rows), "errors": sum(r["status"] != "ok" for r in rows),
    "native_evaluator_run": False, "acceptance": "NOT_EVALUATED",
    "cohorts": {cohort: {"cases": sum(r["cohort"] == cohort for r in rows),
        "valid": sum(r["cohort"] == cohort and r["status"] == "ok" for r in rows),
        "changed": sum(r["cohort"] == cohort and r.get("changed", False) for r in rows)}
        for cohort in sorted({r["cohort"] for r in rows})},
}
(a.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
raise SystemExit(bool(metrics["errors"]))
