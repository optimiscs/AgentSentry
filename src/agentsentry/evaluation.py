"""Metrics distinguish errors, abstentions, and negative security outcomes."""

import json
from collections import Counter
from pathlib import Path


def summarize(records: list[dict]):
    if not records:
        raise ValueError("EMPTY_EVALUATION")
    ids = [r["case_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("DUPLICATE_CASE_ID")
    valid = []
    for r in records:
        if r.get("status") not in {"ok", "error", "timeout", "incomplete"}:
            raise ValueError("INVALID_CASE_STATUS")
        if r["status"] == "ok":
            if not isinstance(r.get("attack_success"), bool) or not isinstance(
                r.get("task_success"), bool
            ):
                raise ValueError("MISSING_NATIVE_OUTCOME")
            valid.append(r)
    attacks = sum(r["attack_success"] for r in valid)
    n = len(records)
    v = len(valid)
    return {
        "planned_cases": n,
        "completed_cases": v,
        "errors": n - v,
        "completion_rate": v / n,
        "attack_successes": attacks,
        "asr_completed": attacks / v if v else None,
        "asr_all_lower_bound": attacks / n,
        "asr_all_upper_bound": (attacks + n - v) / n,
        "task_success_rate_completed": sum(r["task_success"] for r in valid) / v
        if v
        else None,
        "decisions": dict(Counter(r.get("decision", "UNAVAILABLE") for r in valid)),
        "full_run_valid": v == n,
    }


def classification_metrics(expected: list[str], actual: list[str], labels: list[str]):
    if len(expected) != len(actual) or not expected:
        raise ValueError("INVALID_CLASSIFICATION_INPUT")
    if not set(expected + actual) <= set(labels):
        raise ValueError("UNKNOWN_CLASSIFICATION_LABEL")
    matrix = {a: {b: 0 for b in labels} for a in labels}
    for a, b in zip(expected, actual):
        matrix[a][b] += 1
    per = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[a][label] for a in labels if a != label)
        fn = sum(matrix[label][b] for b in labels if b != label)
        per[label] = {
            "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            "support": sum(matrix[label].values()),
        }
    return {
        "n": len(expected),
        "macro_f1": sum(v["f1"] for v in per.values()) / len(labels),
        "classes": per,
        "confusion_matrix": matrix,
    }


def import_native(path: Path, manifest: dict):
    """Explicit field mapping for native evaluator exports, not a replacement evaluator."""
    import hashlib

    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["source_sha256"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    required = {
        "benchmark",
        "benchmark_commit",
        "model",
        "configuration",
        "field_map",
        "source_sha256",
    }
    if not required <= set(manifest) or any(not manifest[k] for k in required):
        raise ValueError("INCOMPLETE_MANIFEST")
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    mapping = manifest["field_map"]
    records = []
    for row in rows:
        item = {key: row.get(field) for key, field in mapping.items()}
        if item.get("status") != "ok":
            item["status"] = (
                item.get("status")
                if item.get("status") in {"error", "timeout", "incomplete"}
                else "incomplete"
            )
        records.append(item)
    return records, summarize(records)
