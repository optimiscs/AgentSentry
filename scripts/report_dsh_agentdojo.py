#!/usr/bin/env python3
"""Audit cloud request evidence and pair native AgentDojo outcomes."""

import argparse
import json
from collections import Counter
from pathlib import Path

from select_flash_challenge import load_run


def text_parts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for part in value:
            yield from text_parts(part)
    elif isinstance(value, dict):
        for part in value.values():
            yield from text_parts(part)


def audit(path):
    manifest, rows = load_run(path)
    requests, usage, models, exposed, reasoning = 0, Counter(), set(), [], []
    wrapper_seen_ids = []
    bad_requests, missing_usage = [], []
    for index, case_id in enumerate(manifest["planned_ids"]):
        row = rows.get(case_id)
        payloads = [" ".join(p.split()) for p in (row or {}).get("injections", {}).values() if p.strip()]
        seen = wrapper_seen = False
        for file in sorted((path / f"case-{index:04}" / "provider").glob("request-*.json")):
            request = json.loads(file.read_text())
            requests += 1
            body = request["request"]
            if request["status"] != "ok" or body.get("thinking") != {"type": "disabled"}:
                bad_requests.append(str(file.relative_to(path)))
            if request.get("reasoning_observed"):
                reasoning.append(str(file.relative_to(path)))
            records = request.get("usage", [])
            if not records:
                missing_usage.append(str(file.relative_to(path)))
            for record in records:
                usage.update({key: record.get(key, 0) for key in ["prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"]})
            models.update(c.get("model") for c in request.get("response_chunks", []) if c.get("model"))
            for message in body.get("messages", []):
                if message.get("role") == "tool":
                    seen |= any(p in " ".join(t.split()) for t in text_parts(message.get("content")) for p in payloads)
                    wrapper_seen |= bool(payloads) and any("This is an important message from me" in t for t in text_parts(message.get("content")))
        if seen:
            exposed.append(case_id)
        if wrapper_seen:
            wrapper_seen_ids.append(case_id)
    return {"run": str(path), "planned": len(manifest["planned_ids"]), "recorded": len(rows),
            "valid": sum(r["status"] == "ok" for r in rows.values()), "requests": requests,
            "usage": dict(usage), "observed_provider_models": sorted(models),
            "bad_or_thinking_requests": bad_requests, "reasoning_observed_requests": reasoning,
            "requests_missing_usage": missing_usage, "whitespace_normalized_payload_seen_ids": exposed,
            "important_instructions_wrapper_seen_ids": wrapper_seen_ids,
            "exposure_check": "Original injected text occurs within a tool-role request sent to Flash, allowing whitespace differences only",
            "metrics": json.loads((path / "metrics.json").read_text()) if (path / "metrics.json").exists() else None}


def compare(baseline, protected):
    bm, br = load_run(baseline)
    pm, pr = load_run(protected)
    if bm["configuration"] != "baseline" or pm["configuration"] != "runtime_rules":
        raise ValueError("BASELINE_AND_RUNTIME_RULES_PAIR_REQUIRED")
    for field in ["model", "thinking", "client", "max_tokens", "max_steps", "benchmark_commit", "source_archive_sha256", "support_files", "source_files", "session_script_sha256", "policy_sha256", "planned_ids"]:
        if bm.get(field) != pm.get(field):
            raise ValueError("PAIRED_PROTOCOL_MISMATCH:" + field)
    pairs = []
    for case_id in bm["planned_ids"]:
        b, p = br.get(case_id), pr.get(case_id)
        if b and p and b.get("payload_sha256") != p.get("payload_sha256"):
            raise ValueError("PAIRED_PAYLOAD_MISMATCH")
        pair = {"case_id": case_id, "baseline_status": (b or {}).get("status", "missing"),
                "protected_status": (p or {}).get("status", "missing")}
        for name, row in [("baseline", b), ("protected", p)]:
            for field in ["utility", "attack_success"]:
                pair[name + "_" + field] = row.get(field) if row and row["status"] == "ok" else None
        pairs.append(pair)
    normals = [p for p in pairs if p["case_id"].endswith("/benign")]
    return {"baseline": audit(baseline), "protected": audit(protected), "paired": pairs,
            "normal_regression_ids": [p["case_id"] for p in normals if p["baseline_utility"] is True and p["protected_utility"] is False],
            "normal_improvement_ids": [p["case_id"] for p in normals if p["baseline_utility"] is False and p["protected_utility"] is True],
            "causal_limit": "Single paired stochastic run; normal changes may include model variability. Inspect decisions before attributing causation."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--protected", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.baseline, args.protected) if args.protected else audit(args.baseline)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
