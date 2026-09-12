#!/usr/bin/env python3
"""Capture an immutable local benchmark source/model/environment bundle, no secrets."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-python", type=Path, required=True)
    parser.add_argument("--benchmark-python", type=Path, required=True)
    parser.add_argument("--max-model-len", type=int, default=8192)
    parser.add_argument(
        "--serving-command",
        type=Path,
        help="Recorded local launch JSON; required for a non-default serving configuration",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    files = sorted(
        f
        for folder in ["src", "policies", "benchmarks", "scripts", "tests"]
        for f in (root / folder).rglob("*")
        if f.is_file()
        and f.suffix in {".py", ".aspolicy", ".toml"}
        and "__pycache__" not in f.parts
    )
    archive = args.output / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for f in files:
            tar.add(f, arcname=str(f.relative_to(root)), recursive=False)
    model = args.model_path.resolve()
    weights = sorted(model.glob("*.safetensors"))
    if not weights:
        raise ValueError("NO_MODEL_WEIGHTS")
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_state": "uncommitted_source_archive",
        "source_archive_sha256": sha(archive),
        "source_files": {str(f.relative_to(root)): sha(f) for f in files},
        "model_path": str(model),
        "model_files": {
            f.name: {"bytes": f.stat().st_size, "sha256": sha(f)}
            for f in sorted(model.iterdir())
            if f.is_file()
            and (
                f.suffix in {".json", ".safetensors", ".jinja"}
                or f.name in {"LICENSE", "README.md"}
            )
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_affinity_count": len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "gpu": subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip(),
        "serving": {
            "model": "agentsentry-local-qwen",
            "vllm": "0.27.1",
            "max_model_len": args.max_model_len,
            "max_num_seqs": 8,
            "gpu_memory_utilization": 0.75,
            "tool_call_parser": "hermes",
            "enforce_eager": True,
            "flashinfer_sampler": False,
            "network": "loopback_only",
            "external_api_calls": False,
        },
    }
    if args.serving_command:
        launch = json.loads(args.serving_command.read_text())
        argv = launch["argv"]
        if not isinstance(argv, list) or not all(isinstance(v, str) for v in argv):
            raise ValueError("INVALID_SERVING_COMMAND")

        def value(flag):
            return argv[argv.index(flag) + 1]

        if Path(value("--model")).resolve() != model:
            raise ValueError("SERVING_MODEL_PATH_MISMATCH")
        if int(value("--max-model-len")) != args.max_model_len:
            raise ValueError("SERVING_CONTEXT_LENGTH_MISMATCH")
        record["serving"] = {
            "source": "recorded_launch_command; readiness/inference evidence separate",
            "command_sha256": sha(args.serving_command),
            "argv": argv,
            "model": value("--served-model-name"),
            "max_model_len": args.max_model_len,
            "max_num_seqs": int(value("--max-num-seqs")),
            "gpu_memory_utilization": float(value("--gpu-memory-utilization")),
            "tool_call_parser": value("--tool-call-parser"),
            "enforce_eager": "--enforce-eager" in argv,
            "network": "loopback_only"
            if value("--host") == "127.0.0.1"
            else "UNVERIFIED",
        }
    for name, interpreter in [
        ("model", args.model_python),
        ("benchmark", args.benchmark_python),
    ]:
        packages = json.loads(
            subprocess.check_output(
                [str(interpreter), "-m", "pip", "list", "--format=json"], text=True
            )
        )
        (args.output / (name + "-packages.json")).write_text(
            json.dumps(packages, indent=2) + "\n"
        )
        record[name + "_packages_sha256"] = sha(args.output / (name + "-packages.json"))
    (args.output / "environment.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "model_weight_files": len(weights),
                "source_files": len(files),
            }
        )
    )


if __name__ == "__main__":
    main()
