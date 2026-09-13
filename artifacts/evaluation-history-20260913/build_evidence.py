"""Collect existing experiment evidence; does not call a model or change old scores."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


inventory = []
for p in sorted((ROOT / "artifacts/benchmarks").glob("*/*/metrics.json")):
    rel = p.parent.relative_to(ROOT)
    entry = {"run": str(rel), "metrics": read(rel / "metrics.json"), "metrics_sha256": digest(rel / "metrics.json")}
    for name in ["manifest.json", "per_case.jsonl"]:
        if (ROOT / rel / name).exists():
            entry[name + "_sha256"] = digest(rel / name)
    if (ROOT / rel / "manifest.json").exists():
        manifest = read(rel / "manifest.json")
        entry["configuration"] = {k: v for k, v in manifest.items() if k not in {"planned_ids", "source_files", "support_files", "adaptations"}}
    if (ROOT / rel / "per_case.jsonl").exists():
        rows = [json.loads(s) for s in (ROOT / rel / "per_case.jsonl").read_text().splitlines()]
        entry["strict_valid_records"] = sum(r.get("status") == "ok" and r.get("valid", True) for r in rows)
    inventory.append(entry)

historical = read("docs/evidence/public-benchmark-report.json")
missing_run = "artifacts/benchmarks/injecagent/qwen27b-v4-base-full-s0"
assert not any(e["run"] == missing_run for e in inventory)
historical_full = next(c for c in historical["summary"]["comparisons"] if any(e["path"] == missing_run for e in c["evidence"]))
inventory.append({"run": missing_run, "source": "docs/evidence/public-benchmark-report.json", "source_sha256": digest("docs/evidence/public-benchmark-report.json"), "strict_summary": historical_full["full"], "provenance": historical_full["evidence"][1], "note": "Historical verified paired report; full raw run is not present in this local mirror."})
assert len(inventory) == 44, len(inventory)

control = Path("artifacts/lab3090-context-filter-v4-benign97")
latest = {"status": "NOT_ACCEPTED", "completed_at_utc": "2026-09-13T12:40:14.451740+00:00", "source_commit_before_document_update": "2dbb066769f2776a10f3888939b09a77c0b478f9", "candidate_archive_sha256": "aa8a418d66e17ee56c58029ab4c0f6db643eb49f4330302a40037e457df7c2dd", "reference_only": True, "independent_heldout": False, "native_attack_cases": 0, "paired_report": read(control / "reference-comparison.json"), "arms": {}}
for arm, job in [("baseline", "baseline"), ("promptarmor_adapted", "reference")]:
    path = Path("artifacts/benchmarks/agentdojo") / f"agentdojo-lab3090-qwen35-9b-context-filter-v4-benign97-{arm}-s0"
    rows = [json.loads(s) for s in (ROOT / path / "per_case.jsonl").read_text().splitlines()]
    assert len(rows) == len({r["case_id"] for r in rows}) == 97
    proc = read(control / f"{job}-process.json")
    assert proc["status"] == "FAILED_REVIEW_REQUIRED" and proc["returncode"] == 1
    modifications = [{"case_id": r["case_id"], "utility": r.get("utility"), **t} for r in rows for t in r.get("sanitizer_trace", []) if t.get("spans")]
    latest["arms"][arm] = {"run": str(path), "metrics": read(path / "metrics.json"), "manifest_sha256": digest(path / "manifest.json"), "records_sha256": digest(path / "per_case.jsonl"), "process": proc, "modified_tool_returns": len(modifications), "modifications": modifications, "cases": [{k: r[k] for k in ["case_id", "status", "utility", "error", "seconds", "guard_model_calls", "guard_failures"] if k in r} for r in rows]}
b, f = ({r["case_id"]: r for r in latest["arms"][arm]["cases"]} for arm in ["baseline", "promptarmor_adapted"])
latest["paired_success_differences"] = [{"case_id": k, "baseline": b[k], "reference": f[k]} for k in b if (b[k].get("utility") is True) != (f[k].get("utility") is True)]
assert len(latest["paired_success_differences"]) == 6

output = {"generated_at": datetime.now(timezone.utc).isoformat(), "scope": "22 paired native model benchmark batches (44 arms), plus separately cited input diagnostics, replay and engineering measurements; not a merged acceptance score", "historical_metrics_note": "Early InjecAgent completed_cases includes invalid outputs. Use strict_valid_records or strict_summary.valid_cases, not completed_cases, as valid denominator.", "inventory": inventory, "latest_joint_filter_benign97": latest}
(ROOT / "docs/evidence/evaluation-history-20260913.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
(ROOT / control / "terminal-review.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"native_arms": len(inventory), "native_paired_batches": len(inventory)//2, "latest_reference_modified_returns": latest["arms"]["promptarmor_adapted"]["modified_tool_returns"], "latest_paired_success_differences": len(latest["paired_success_differences"])}))
