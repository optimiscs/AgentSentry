#!/usr/bin/env python3
"""Freeze native Flash attack successes without consulting defense outcomes."""

import argparse
import hashlib
import json
from pathlib import Path


def load_run(path):
    invalid = path.parent / "invalid-runs.json"
    if invalid.exists() and path.name in json.loads(invalid.read_text()).get("excluded_runs", {}):
        raise ValueError("INVALID_PROTOCOL_RUN")
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest["model"] != "deepseek-flash" or manifest["thinking"] is not False:
        raise ValueError("NONTHINKING_FLASH_RUN_REQUIRED")
    rows = [json.loads(line) for line in (path / "per_case.jsonl").read_text().splitlines()]
    by_id = {row["case_id"]: row for row in rows}
    if len(by_id) != len(rows) or not set(by_id) <= set(manifest["planned_ids"]):
        raise ValueError("RUN_CASE_ID_MISMATCH")
    return manifest, by_id


def succeeded(row):
    return bool(row and row.get("status") == "ok" and row.get("native_status") == "ok"
                and row.get("attack_success") is True)


def select(discovery, confirmation=None, review=None):
    manifest, rows = load_run(discovery)
    if manifest["configuration"] != "baseline":
        raise ValueError("SELECTION_MUST_USE_UNDEFENDED_BASELINE")
    planned = manifest["planned_ids"]
    attacks = [i for i in planned if not i.endswith("/benign")]
    normals = [i for i in planned if i.endswith("/benign")]
    success_ids = [i for i in attacks if succeeded(rows.get(i))]
    reviews = (review or {}).get("reviews", {})
    verdicts = {i: reviews.get(discovery.name + "/" + i, {}) for i in success_ids}
    excluded = [i for i in success_ids if verdicts[i].get("verdict") == "oracle_false_positive"]
    eligible = [i for i in success_ids if i not in excluded]
    reviewed = [i for i in eligible if verdicts[i].get("verdict") == "actual_success" and verdicts[i].get("evidence")]
    invalid = [i for i in attacks if rows.get(i, {}).get("status") != "ok"]
    result = {"selection_policy": "Native oracle success in undefended discovery; independent repeat before confirmed challenge",
              "split": "development_only_not_heldout", "model": manifest["model"], "thinking": False,
              "discovery_run": str(discovery), "discovery_manifest_sha256": hashlib.sha256((discovery / "manifest.json").read_bytes()).hexdigest(),
              "original_attack_count": len(attacks), "original_normal_count": len(normals),
              "discovery_success_ids": success_ids, "discovery_unknown_ids": invalid,
              "oracle_false_positive_ids": excluded, "eligible_discovery_ids": eligible,
              "reviewed_success_ids": reviewed, "native_reproduced_ids": [], "unreviewed_reproduced_ids": [],
              "discovery_asr_lower_bound": len(success_ids) / len(attacks) if attacks else None,
              "discovery_asr_upper_bound": (len(success_ids) + len(invalid)) / len(attacks) if attacks else None,
              "confirmed_ids": [], "unconfirmed_ids": [], "confirmation_unknown_ids": [],
              "normal_control_ids": normals,
              "discovery_normal_utility": sum(rows.get(i, {}).get("status") == "ok" and rows[i].get("utility") is True for i in normals) / len(normals) if normals else None,
              "payload_sha256": {i: rows[i]["payload_sha256"] for i in success_ids}}
    if confirmation is not None:
        repeated_manifest, repeated = load_run(confirmation)
        for field in ["configuration", "model", "thinking", "client", "max_tokens", "max_steps", "benchmark_commit", "source_archive_sha256", "support_files", "source_files", "session_script_sha256"]:
            if manifest.get(field) != repeated_manifest.get(field):
                raise ValueError("CONFIRMATION_PROTOCOL_MISMATCH:" + field)
        if set(repeated_manifest["planned_ids"]) != set(eligible):
            raise ValueError("CONFIRMATION_MUST_COVER_ALL_DISCOVERY_SUCCESSES")
        for i in eligible:
            row = repeated.get(i)
            if row and row.get("payload_sha256") != rows[i]["payload_sha256"]:
                raise ValueError("CONFIRMATION_PAYLOAD_MISMATCH")
            if succeeded(row):
                result["native_reproduced_ids"].append(i)
            category = ("confirmed_ids" if i in reviewed else "unreviewed_reproduced_ids") if succeeded(row) else "unconfirmed_ids" if row and row.get("status") == "ok" else "confirmation_unknown_ids"
            result[category].append(i)
        result["confirmation_run"] = str(confirmation)
        result["confirmation_manifest_sha256"] = hashlib.sha256((confirmation / "manifest.json").read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path)
    parser.add_argument("--review", type=Path, help="Evidence-backed review of native positives; required for confirmed challenge entries")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = select(args.discovery, args.confirmation, json.loads(args.review.read_text()) if args.review else None)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in [("selection.json", result), ("repeat-ids.json", result["eligible_discovery_ids"]),
                        ("confirmed-ids.json", result["confirmed_ids"]),
                        ("paired-ids.json", result["confirmed_ids"] + result["normal_control_ids"])]:
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["original_attack_count", "discovery_success_ids", "confirmed_ids", "discovery_unknown_ids"]}))


if __name__ == "__main__":
    main()
