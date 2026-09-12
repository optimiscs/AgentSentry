#!/usr/bin/env python3
"""Inspect published PIGuard splits and exact overlap; never train or run attacks."""

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from prepare_mpbench import reject_constant, unique_object

COMMIT = "1b5751e88bf7475acbedfc8eda795ce060307c84"
NATIVE_EVALUATOR_SHA = "7c676fc726fc7b73b190f6bd31c54357751987218a7b865adbc7bbf63defda18"


def fingerprint(text, normalized=False):
    if normalized:
        text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()
    return hashlib.sha256(text.encode()).hexdigest()


def load(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_object, parse_constant=reject_constant)


def index_rows(rows, normalized):
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[fingerprint(row["prompt"], normalized)].append({"row": index, "label": row["label"]})
    return groups


def split_audit(records, normalized):
    indices = {name: index_rows(rows, normalized) for name, rows in records.items()}
    summaries = {}
    for name, groups in indices.items():
        summaries[name] = {
            "records": len(records[name]), "unique_texts": len(groups),
            "duplicate_excess_records": sum(len(rows) - 1 for rows in groups.values()),
            "conflicting_label_groups": sum(len({row["label"] for row in rows}) > 1 for rows in groups.values()),
            "empty_prompt_rows": [index for index, row in enumerate(records[name]) if not row["prompt"].strip()],
            "label_conflicts": [{"text_sha256": key, "rows": rows} for key, rows in sorted(groups.items())
                                if len({row["label"] for row in rows}) > 1],
        }
    overlaps = []
    for left in ("train", "valid"):
        for right in records:
            if right == left or (left == "valid" and right == "train"):
                continue
            shared = indices[left].keys() & indices[right].keys()
            overlaps.append({"left": left, "right": right, "shared_texts": len(shared),
                             "left_records": sum(len(indices[left][key]) for key in shared),
                             "right_records": sum(len(indices[right][key]) for key in shared),
                             "conflicting_label_groups": sum(len({row["label"] for row in indices[left][key] + indices[right][key]}) > 1 for key in shared),
                             "matches": [{"text_sha256": key, "left": indices[left][key], "right": indices[right][key]} for key in sorted(shared)]})
    return {"mode": "NFKC_casefold_whitespace" if normalized else "exact", "splits": summaries, "overlaps": overlaps}


def audit(source, injecagent, mpbench, output):
    provenance = load(source / "agentsentry-source.json")
    if provenance["commit"] != COMMIT:
        raise ValueError("UNREVIEWED_PIGUARD_DATA_SOURCE")
    if hashlib.sha256((source / "eval_hf.py").read_bytes()).hexdigest() != NATIVE_EVALUATOR_SHA:
        raise ValueError("UNREVIEWED_NATIVE_SPLIT_LABELS")
    records = {}
    files = sorted((source / "datasets").glob("*.json"))
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    for path in files:
        name, data = path.stem, load(path)
        if name.startswith("BIPIA_"):
            if not isinstance(data, dict) or any(not isinstance(values, list) for values in data.values()):
                raise ValueError("UNEXPECTED_BIPIA_FORMAT")
            rows = [{"prompt": text, "label": 1} for values in data.values() for text in values]
        elif name.startswith("NotInject_"):
            rows = [{"prompt": row["prompt"], "label": 0} for row in data]
        elif name in {"train", "valid", "wildguard"}:
            rows = data
        else:
            raise ValueError("UNREVIEWED_PIGUARD_DATA_FILE:" + name)
        if any(not isinstance(row.get("prompt"), str) or
               type(row.get("label")) is not int or row["label"] not in {0, 1} for row in rows):
            raise ValueError("INVALID_PIGUARD_DATA_ROW:" + name)
        records[name] = rows
    if not {"train", "valid"} <= records.keys():
        raise ValueError("MISSING_PIGUARD_SPLIT")
    split_reports = [split_audit(records, normalized) for normalized in (False, True)]
    external = {}
    injec_provenance = load(injecagent / "agentsentry-source.json")
    if injec_provenance["commit"] != "f19c9f2c79a41046eb13c03c51a24c567a8ffa07":
        raise ValueError("UNREVIEWED_INJECAGENT_SOURCE")
    injec_hashes = {}
    for category in ("dh", "ds"):
        name = "test_cases_" + category + "_base.json"
        path = injecagent / "data" / name
        injec_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for index, row in enumerate(load(path)):
            for field in ("Attacker Instruction", "Tool Response"):
                if not isinstance(row[field], str):
                    raise ValueError("UNEXPECTED_INJECAGENT_INPUT")
                external[(name, index, field)] = row[field]
    manifest = load(mpbench / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name or hashlib.sha256((mpbench / name).read_bytes()).hexdigest() != expected:
            raise ValueError("MPBENCH_PACKET_CHANGED")
    for line in (mpbench / "inputs.jsonl").read_text().splitlines():
        row = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_constant)
        for field in row["external_content"]:
            external[("MPBench", row["case_id"], field["field"])] = field["text"]
    matches = []
    for normalized in (False, True):
        training = index_rows(records["train"], normalized)
        match_rows = []
        for (dataset, row, field), value in external.items():
            key = fingerprint(value, normalized)
            if key in training:
                match_rows.append({"dataset": dataset, "row": row, "field": field, "text_sha256": key,
                                   "training_rows": training[key]})
        matches.append({"mode": "NFKC_casefold_whitespace" if normalized else "exact",
                        "matching_external_fields": len(match_rows),
                        "matching_cases_by_dataset": {dataset: len({row["row"] for row in match_rows if row["dataset"] == dataset})
                                                      for dataset in sorted({key[0] for key in external})},
                        "matches": match_rows})
    report = {
        "status": "PUBLISHED_TRAINING_DATA_AUDIT_NOT_CHECKPOINT_MEMBERSHIP_PROOF",
        "generated_at": datetime.now(timezone.utc).isoformat(), "source": provenance,
        "data_file_sha256": hashes, "native_evaluator_sha256": NATIVE_EVALUATOR_SHA,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parser_helper_sha256": hashlib.sha256(Path(__file__).with_name("prepare_mpbench.py").read_bytes()).hexdigest(),
        "partition_labels": {name: dict(Counter(str(row["label"]) for row in rows)) for name, rows in records.items()},
        "training_sources": dict(Counter(row.get("source") for row in records["train"])),
        "validation_sources": dict(Counter(row.get("source") for row in records["valid"])),
        "splits": split_reports, "external_overlap": matches,
        "injecagent_source": injec_provenance, "injecagent_data_sha256": injec_hashes,
        "mpbench_manifest_sha256": hashlib.sha256((mpbench / "manifest.json").read_bytes()).hexdigest(),
        "limitations": [
            "Published training data is not a verified per-checkpoint training manifest or model membership test.",
            "Zero whole-string overlap does not rule out embedded spans, paraphrases, templates or upstream pretraining exposure.",
            "Labels for NotInject and BIPIA follow the reviewed author evaluator; no author training or evaluation script was executed.",
            "PINT.json is not present in this snapshot; existing PINT validation rows do not represent the complete PINT benchmark.",
            "Repository MIT licensing does not replace review of upstream dataset-specific licenses before training or redistribution.",
            "Existing model results are not removed or altered based on overlap; any filtered diagnostic must be separately declared.",
            "Empty string training prompts are retained and indexed as a data-quality defect; this audit does not make them valid training samples.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "injecagent", "mpbench", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source, args.injecagent, args.mpbench, args.output)
    print(json.dumps({"status": result["status"], "training_rows": sum(result["partition_labels"]["train"].values())}))
