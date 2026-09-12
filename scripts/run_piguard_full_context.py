#!/usr/bin/env python3
"""Fixed CPU checkpoint comparison with complete fields and no truncation."""

import argparse
import importlib.util
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from score_mpbench_checkpoint import (
    MODEL_MANIFEST_SHA,
    digest,
    indexed,
    probability,
    read_json,
)

ROOT = Path(__file__).resolve().parents[1]
LOADER_SHA = "4ab6c09955af0fcc10620a1ce9376b4a6532aae592ccb710937ba42cdf4318b2"
PROTOCOL = {
    "window_content_tokens": 2046,
    "stride": 2046,
    "threshold": 0.5,
    "aggregate": "maximum over all external fields and windows",
    "input_fields": ["context", "skill_md"],
    "excluded": ["user_query", "retrieval_query", "expected_memory", "labels"],
    "threshold_selection": "fixed binary argmax; no calibration on these public records",
    "adaptation": "One complete field per encoding, maximum 2048 tokens including specials; no truncation.",
}


def classify(tokenizer, classifier, text):
    content = tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"]
    encoded = tokenizer(text, truncation=False)["input_ids"]
    if len(content) > 2046:
        raise ValueError("COMPLETE_INPUT_EXCEEDS_2048_TOKEN_BUDGET")
    if encoded != [1, *content, 2]:
        raise ValueError("COMPLETE_FIELD_ENCODING_CHANGED")
    # The length check above ensures the native pipeline receives every token.
    result = classifier(text, truncation=False, max_length=2048, top_k=None)
    if (
        not isinstance(result, list)
        or len(result) != 2
        or {x.get("label") for x in result} != {"benign", "injection"}
    ):
        raise ValueError("UNEXPECTED_PIPELINE_LABELS")
    scores = {x["label"]: probability(x.get("score")) for x in result}
    if abs(sum(scores.values()) - 1) > 1e-5:
        raise ValueError("INVALID_PIPELINE_PROBABILITY_SUM")
    value = scores["injection"]
    return {
        "input_tokens": len(content),
        "injection_probability": value,
        "alert": value > 0.5,
        "windows": [
            {
                "offset": 0,
                "content_tokens": len(content),
                "injection_probability": value,
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet", type=Path, default=ROOT / "artifacts/mpbench-protocol-v1"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    os.environ.update(
        CUDA_VISIBLE_DEVICES="",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
    )
    loader = ROOT / "artifacts/run_piguard_cpu.py"
    if digest(loader) != LOADER_SHA:
        raise ValueError("FROZEN_MODEL_LOADER_CHANGED")
    spec = importlib.util.spec_from_file_location(
        "pinned_cpu_checkpoint_loader", loader
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    if helper.sha(helper.MODEL / "agentsentry-model.json") != MODEL_MANIFEST_SHA:
        raise ValueError("FROZEN_MODEL_MANIFEST_CHANGED")
    import torch
    import transformers
    from transformers import pipeline

    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    args.output.mkdir(parents=True, exist_ok=False)
    state = {
        "status": "LOADING_CPU_MODEL",
        "pid": os.getpid(),
        "device": "cpu",
        "torch_threads": 2,
        "script_sha256": digest(Path(__file__)),
        "loader_sha256": LOADER_SHA,
        "records_completed": 0,
        "protocol": PROTOCOL,
        "kind": "PUBLIC_CHECKPOINT_INPUT_DIAGNOSTIC_NOT_MEMORY_ACCEPTANCE",
        "source_files": {
            str(p.relative_to(ROOT)): digest(p)
            for p in [
                Path(__file__),
                loader,
                ROOT / "scripts/score_mpbench_checkpoint.py",
                ROOT / "scripts/prepare_mpbench.py",
            ]
        },
        "environment": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "tokenizer": "pinned tokenizer.json via standard DebertaV2 fast tokenizer",
        },
    }
    started = time.monotonic()

    def save():
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["elapsed_seconds"] = time.monotonic() - started
        helper.dump(args.output / "progress.json", state)

    save()
    try:
        model, tokenizer, manifest = helper.load_model()
        classifier = pipeline(
            "text-classification", model=model, tokenizer=tokenizer, device=-1
        )
        state.update(
            load_seconds=time.monotonic() - started,
            model_revision=manifest["revision"],
            model_manifest_sha256=MODEL_MANIFEST_SHA,
        )
        if args.smoke:
            state["smoke_predictions"] = [
                classify(tokenizer, classifier, text)
                for text in ["The meeting starts at noon.", "A meeting note. " * 170]
            ]
            state["status"] = "CPU_MODEL_SMOKE_COMPLETED_NOT_BENCHMARK_SCORE"
            return
        packet = read_json(args.packet / "manifest.json")
        for name, expected in packet["artifacts"].items():
            if Path(name).name != name or digest(args.packet / name) != expected:
                raise ValueError("MPBENCH_PACKET_CHANGED")
        # Oracle bytes are integrity-checked above; their labels are never parsed.
        inputs = indexed(args.packet / "inputs.jsonl")
        if len(inputs) != packet["input_records"]:
            raise ValueError("MPBENCH_INPUT_COUNT_MISMATCH")
        state.update(
            packet_manifest_sha256=digest(args.packet / "manifest.json"),
            planned_records=len(inputs),
            status="RUNNING_CPU_DIAGNOSTIC",
        )
        save()
        with (args.output / "predictions.jsonl").open("x") as stream:
            for item in inputs.values():
                begin = time.monotonic()
                row = {
                    "case_id": item["case_id"],
                    "status": "evaluated",
                    "fields": [],
                    "alert": False,
                }
                try:
                    for field in item["external_content"]:
                        result = classify(tokenizer, classifier, field["text"])
                        row["fields"].append({"field": field["field"], **result})
                        row["alert"] |= result["alert"]
                except Exception as exc:
                    row.update(
                        status="error", error=type(exc).__name__ + ":" + str(exc)
                    )
                row["seconds"] = time.monotonic() - begin
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                stream.flush()
                state["records_completed"] += 1
                if state["records_completed"] % 25 == 0:
                    save()
        state.update(
            predictions_sha256=digest(args.output / "predictions.jsonl"),
            status="CPU_PREDICTIONS_FINISHED_SCORING_PENDING",
        )
    except Exception as exc:
        state.update(
            status="STOPPED_REVIEW_REQUIRED", error=type(exc).__name__ + ":" + str(exc)
        )
        raise
    finally:
        save()
        print(
            json.dumps(
                {
                    key: state[key]
                    for key in ["status", "records_completed", "elapsed_seconds"]
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
