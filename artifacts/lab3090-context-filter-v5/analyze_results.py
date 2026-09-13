"""Summarize frozen guard diagnostics and native development runs, without model calls."""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


report = {"status": "DEVELOPMENT_IMPROVEMENT_NOT_ACCEPTANCE", "generated_at": datetime.now(timezone.utc).isoformat(), "actor_thinking_default": False, "guard_thinking_default": False, "promoted_to_product": False, "diagnostic": {"native_evaluator_run": False, "independent_heldout": False, "inputs_sha256": sha(CONTROL / "expanded-inputs.json"), "arms": {}}, "native": {}}
inputs = {r["case_id"]: r for r in read(CONTROL / "expanded-inputs.json")["inputs"]}
assert len(inputs) == 43
for version in ["v4", "v5"]:
    path = CONTROL / ("diagnostic-" + version)
    data = rows(path / "per_case.jsonl")
    assert len(data) == len({r["case_id"] for r in data}) == 43
    assert {r["case_id"] for r in data} == set(inputs)
    for row in data:
        assert row["input_hash"] == inputs[row["case_id"]]["input_hash"]
    seconds = sorted(r["seconds"] for r in data)
    report["diagnostic"]["arms"][version] = {"metrics": read(path / "metrics.json"), "records_sha256": sha(path / "per_case.jsonl"), "manifest_sha256": sha(path / "manifest.json"), "latency_all_attempts_seconds": {"n": len(seconds), "mean": statistics.mean(seconds), "median": statistics.median(seconds), "p95_nearest_rank": seconds[math.ceil(.95 * len(seconds)) - 1]}, "cases": [{"case_id": r["case_id"], "cohort": r["cohort"], "input_hash": r["input_hash"], "status": r["status"], "changed": r.get("changed"), "error": r.get("error"), "seconds": r["seconds"], "spans": [t.get("spans", []) for t in r["sanitizer_trace"]]} for r in data]}

for name in ["v4-attack16", "v5-dev35"]:
    control = ROOT / ("artifacts/lab3090-context-filter-" + name)
    report["native"][name] = {"strict_report": read(control / "reference-comparison.json"), "strict_report_sha256": sha(control / "reference-comparison.json"), "arms": {}}
    for arm in ["baseline", "reference"]:
        process = read(control / (arm + "-process.json"))
        assert process["returncode"] == 0
        path = ROOT / process["job"]["output"]
        data = rows(path / "per_case.jsonl")
        assert all(r["status"] == "ok" for r in data)
        report["native"][name]["arms"][arm] = {"run": process["job"]["output"], "process": process, "metrics": read(path / "metrics.json"), "records_sha256": sha(path / "per_case.jsonl"), "manifest_sha256": sha(path / "manifest.json"), "cases": [{k: r.get(k) for k in ["case_id", "status", "utility", "attack_success", "seconds"]} for r in data]}

new = report["native"]["v5-dev35"]["arms"]["reference"]["cases"]
normal_ids = {r["case_id"] for r in new if r["case_id"].endswith("/benign")}
previous = ROOT / "artifacts/benchmarks/agentdojo/agentdojo-lab3090-qwen35-9b-context-filter-v4-benign97-promptarmor_adapted-s0/per_case.jsonl"
old = [r for r in rows(previous) if r["case_id"] in normal_ids]
assert len(old) == len(normal_ids) == 19
report["previous_v4_same_19_normal_tasks"] = {"records_sha256": sha(previous), "utility_true": sum(r.get("utility") is True for r in old), "cases": [{k: r.get(k) for k in ["case_id", "status", "utility"]} for r in old], "note": "Selected retrospectively from v4 benign97, not a new run or independent heldout; v5 re-executed these development tasks."}
report["freeze"] = read(CONTROL / "freeze.json")
report["checks"] = {"unit_tests": 117, "subtests": 2, "native_pipeline_checks": 12, "asb_pipeline_checks": 14, "patch_rebuild": read(CONTROL / "patch-rebuild-check.json")}
report["limitations"] = ["Normal native email environments may contain phishing/spam. Modified return count is not a separately annotated false-positive rate.", "Deletion on a fixed input is not a native security outcome; only native runs report ASR.", "The 35-case selection includes observed failure cases; it is development evidence.", "The separately launched full1046 run is not summarized before completion."]
(ROOT / "docs/evidence/context-filter-v5-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": report["status"], "v4_same19_utility": report["previous_v4_same_19_normal_tasks"]["utility_true"], "v5_same19_utility": sum(r.get("utility") is True for r in new if r["case_id"] in normal_ids)}))
