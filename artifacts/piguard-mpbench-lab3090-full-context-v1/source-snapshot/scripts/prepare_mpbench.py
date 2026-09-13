#!/usr/bin/env python3
"""Freeze published MPBench data; labels stay outside defender inputs."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

COMMIT = "6886880a7c29625e0109e0ad91d0e095029f1577"
FILES = {"adversarial": "adversarial_data.jsonl.jsonl", "benign": "benign_data.jsonl.jsonl"}


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("NONSTANDARD_JSON_CONSTANT:" + value)


def decode_records(raw):
    """Account for every byte; handle the source's adjacent JSON objects explicitly."""
    text = raw.decode("utf-8")
    decoder = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=reject_constant)
    cursor = byte_cursor = 0
    records = []
    boundaries_without_newline = []
    previous_end = None
    while cursor < len(text):
        whitespace_start = cursor
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        byte_cursor += len(text[whitespace_start:cursor].encode("utf-8"))
        if cursor == len(text):
            break
        start = cursor
        row, cursor = decoder.raw_decode(text, cursor)
        if not isinstance(row, dict):
            raise ValueError("MPBENCH_RECORD_MUST_BE_OBJECT")
        serialized = text[start:cursor].encode("utf-8")
        if previous_end is not None and "\n" not in text[previous_end:start]:
            boundaries_without_newline.append(len(records))
        records.append((row, {"byte_start": byte_cursor, "byte_end": byte_cursor + len(serialized),
                              "raw_object_sha256": digest_bytes(serialized)}))
        byte_cursor += len(serialized)
        previous_end = cursor
    if byte_cursor != len(raw):
        raise ValueError("SOURCE_BYTES_NOT_FULLY_ACCOUNTED")
    return records, boundaries_without_newline


def prepare(source, output):
    provenance = json.loads((source / "agentsentry-source.json").read_text())
    if provenance["commit"] != COMMIT:
        raise ValueError("UNREVIEWED_MPBENCH_COMMIT")
    inputs, evaluator, statistics, source_hashes = [], [], {}, {}
    contexts = defaultdict(list)
    for split, name in FILES.items():
        raw = (source / name).read_bytes()
        source_hashes[name] = digest_bytes(raw)
        records, joined = decode_records(raw)
        seen = set()
        for index, (row, location) in enumerate(records):
            for field in ("id", "user_query", "context"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError("MISSING_MPBENCH_INPUT:" + field)
            if row["id"] in seen:
                raise ValueError("DUPLICATE_UPSTREAM_ID")
            seen.add(row["id"])
            # Opaque IDs do not expose adversarial/benign membership to a defender.
            case_id = "mpb_" + digest_bytes((name + ":" + str(index) + ":" + location["raw_object_sha256"]).encode())[:24]
            external = [{"field": "context", "text": row["context"]}]
            if row.get("skill_md"):
                if not isinstance(row["skill_md"], str):
                    raise ValueError("INVALID_SKILL_SOURCE_TYPE")
                external.append({"field": "skill_md", "text": row["skill_md"]})
            inputs.append({"case_id": case_id, "user_query": row["user_query"], "external_content": external})
            evaluator.append({"case_id": case_id, "source_file": name, "source_row": index,
                              "source_id": row["id"], "source_partition": split, **location,
                              "labels_and_native_fields": {key: value for key, value in row.items()
                                                           if key not in {"user_query", "context", "skill_md"}}})
            contexts[digest_bytes(row["context"].encode())].append({"case_id": case_id, "partition": split})
        statistics[split] = {
            "records": len(records), "physical_nonempty_lines": sum(bool(line.strip()) for line in raw.splitlines()),
            "record_boundaries_without_newline": joined,
            "categories_as_published": {field: dict(Counter(str(row.get(field)) for row, _ in records))
                                        for field in ("attack_type", "attack_signal", "domain")},
            "missing_or_empty_fields": {field: sum(not isinstance(row.get(field), str) or not row.get(field, "").strip()
                                                   for row, _ in records)
                                        for field in ("expected_memory", "retrieval_query")},
            "skill_md_records": sum(bool(row.get("skill_md")) for row, _ in records),
        }
    if len({row["case_id"] for row in inputs}) != len(inputs):
        raise ValueError("CASE_ID_COLLISION")
    output.mkdir(parents=True, exist_ok=False)
    paths = {"inputs.jsonl": inputs, "evaluator.jsonl": evaluator,
             "duplicate-context-groups.jsonl": [group for group in contexts.values() if len(group) > 1]}
    artifacts = {}
    for name, records in paths.items():
        data = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records).encode()
        (output / name).write_bytes(data)
        artifacts[name] = digest_bytes(data)
    manifest = {
        "status": "DATA_PREPARED_NOT_A_MEMORY_BENCHMARK_RUN", "created_at": datetime.now(timezone.utc).isoformat(),
        "source": provenance, "source_files": source_hashes,
        "preparation_script_sha256": digest_bytes(Path(__file__).read_bytes()),
        "artifacts": artifacts, "partitions": statistics, "input_records": len(inputs),
        "unique_contexts": len(contexts),
        "duplicate_context_excess_records": sum(len(group) - 1 for group in contexts.values()),
        "cross_partition_identical_context_groups": sum(len({r['partition'] for r in group}) > 1 for group in contexts.values()),
        "limitations": [
            "Published categories and partition labels are preserved; no silent mapping to the paper's six-class taxonomy.",
            "Adjacent JSON objects are decoded without skipping bytes; the original file remains unchanged.",
            "Blank benign expected_memory may intentionally represent no memory write; no target is invented.",
            "Missing retrieval_query is unresolved for persistence evaluation; agent_question is not silently substituted.",
            "No native harness, judge implementation, agent configuration or official train/test split was included in this source snapshot.",
            "Input-only detection cannot establish memory-write ASR, retrieval RSR, benign task utility or independent three-state F1.",
            "Duplicate contexts are retained and indexed; no unverified claim of task/template independence.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    assert all(digest_bytes((source / name).read_bytes()) == value for name, value in source_hashes.items())
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.source, args.output)
    print(json.dumps({key: report[key] for key in ("status", "input_records", "unique_contexts", "duplicate_context_excess_records")}))
