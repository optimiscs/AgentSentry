#!/usr/bin/env python3
"""Diagnostic input screening only; never a memory-write/persistence acceptance."""

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from input_screen_metrics import rates

from agentsentry.context.scanner import Scanner
from agentsentry.schemas import SourceType


def evaluate(packet, output):
    manifest = json.loads((packet / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        if hashlib.sha256((packet / name).read_bytes()).hexdigest() != expected:
            raise ValueError("MPBENCH_PACKET_CHANGED:" + name)
    inputs = [json.loads(s) for s in (packet / "inputs.jsonl").read_text().splitlines()]
    oracle = {r["case_id"]: r for r in map(json.loads, (packet / "evaluator.jsonl").read_text().splitlines())}
    if len(inputs) != manifest["input_records"] or len(oracle) != len(inputs) or set(oracle) != {r["case_id"] for r in inputs}:
        raise ValueError("INCOMPLETE_MPBENCH_PACKET")
    scanner = Scanner()
    predictions = []
    # Only input fields are visible to this loop. Membership/targets are joined later.
    for item in inputs:
        for mode in ("context_only", "all_external_fields"):
            result = {"case_id": item["case_id"], "mode": mode, "status": "evaluated", "alert": False, "signals": []}
            try:
                for external in item["external_content"]:
                    if mode == "context_only" and external["field"] != "context":
                        continue
                    _, signal = scanner.scan(item["case_id"], external["text"], SourceType.DOCUMENT)
                    result["signals"].append({"field": external["field"], "labels": signal.labels,
                                               "attack_types": signal.attack_types, "latency_ms": signal.latency_ms})
                    result["alert"] |= "INJECTION_RISK" in signal.labels
            except Exception as exc:
                result.update(status="error", error=type(exc).__name__ + ":" + str(exc))
            predictions.append(result)
    for row in predictions:
        label = oracle[row["case_id"]]
        row.update(adversarial=label["source_partition"] == "adversarial",
                   attack_type=label["labels_and_native_fields"].get("attack_type"),
                   attack_signal=label["labels_and_native_fields"].get("attack_signal"))
    output.mkdir(parents=True, exist_ok=False)
    raw = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in predictions).encode()
    (output / "results.jsonl").write_bytes(raw)
    groups = defaultdict(list)
    for row in predictions:
        groups[(row["mode"], "all")].append(row)
        if row["adversarial"]:
            groups[(row["mode"], "signal:" + str(row["attack_signal"]))].append(row)
            groups[(row["mode"], "type:" + str(row["attack_type"]))].append(row)
    source_root = Path(__file__).resolve().parents[1]
    report = {
        "status": "INPUT_SCREEN_DIAGNOSTIC_NOT_MEMORY_BENCHMARK_ACCEPTANCE", "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_manifest_sha256": hashlib.sha256((packet / "manifest.json").read_bytes()).hexdigest(),
        "source_files": {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted((source_root / "src/agentsentry").rglob("*.py"))},
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "metrics_helper_sha256": hashlib.sha256(Path(__file__).with_name("input_screen_metrics.py").read_bytes()).hexdigest(),
        "model": scanner.model_version, "input_records": len(inputs), "prediction_records": len(predictions),
        "prediction_sha256": hashlib.sha256(raw).hexdigest(),
        "groups": [{"mode": key[0], "group": key[1], **rates(rows)} for key, rows in sorted(groups.items())],
        "score_denominator": "All published rows, including duplicate contexts. Errors retained; valid-only rates are descriptive.",
        "limitations": manifest["limitations"] + [
            "No model inference, persistent memory write/read or tool execution occurred.",
            "Binary attack-partition labels are evaluator-only and are not independent action-level ALLOW/ASK/BLOCK labels.",
            "Context-only and context-plus-skill payload screening differ; neither is a native agent execution protocol.",
            "This is a pre-change diagnostic, not a hidden test or a comparison with differently configured paper results.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.packet, args.output)
    print(json.dumps({"status": report["status"], "overall": [r for r in report["groups"] if r["group"] == "all"]}))
