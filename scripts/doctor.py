#!/usr/bin/env python3
"""Read-only hardware/tool discovery. No installations, credentials or workload execution."""

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=10)
        return {
            "returncode": p.returncode,
            "stdout": p.stdout.strip(),
            "stderr": p.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", help="Write report to this path; defaults to stdout only"
    )
    args = parser.parse_args()
    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "read_only_environment_probe",
        "repository": str(ROOT),
        "cpu_affinity_count": len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else os.cpu_count(),
        "cgroup": {},
    }
    for name in ["cpu.max", "memory.max", "memory.current"]:
        p = Path("/sys/fs/cgroup") / name
        if p.exists():
            report["cgroup"][name] = p.read_text().strip()
    report["tools"] = {
        k: shutil.which(k)
        for k in ["python3", "node", "git", "docker", "uv", "nvidia-smi"]
    }
    report["versions"] = {
        k: run([k, "--version"]) for k in ["python3", "node", "git"] if shutil.which(k)
    }
    report["gpu"] = (
        run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,driver_version",
                "--format=csv,noheader",
            ]
        )
        if shutil.which("nvidia-smi")
        else {"status": "unavailable"}
    )
    report["disks"] = {
        str(p): dict(
            zip(["total_bytes", "used_bytes", "free_bytes"], shutil.disk_usage(p))
        )
        for p in [ROOT, Path("/root/autodl-tmp"), Path("/root/autodl-fs")]
        if p.exists()
    }
    report["limitations"] = [
        "GPU visibility does not validate the model inference stack.",
        "Docker PATH discovery does not validate daemon or Compose capability.",
        "Host CPU count is not the cgroup allocation.",
        "No business service, model or benchmark was executed.",
    ]
    if args.output:
        p = Path(args.output)
        if not p.is_absolute():
            p = ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
