#!/usr/bin/env python3
"""Run a declared experiment once, verifying frozen source and Linux process identity."""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def start_ticks(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    control = args.jobs.resolve().parent
    job = json.loads(args.jobs.read_text())[args.name]
    candidate = root / job["candidate"]
    for name, expected in json.loads((candidate / "candidate-manifest.json").read_text())["files"].items():
        if hashlib.sha256((candidate / name).read_bytes()).hexdigest() != expected:
            raise ValueError("FROZEN_SOURCE_CHANGED:" + name)
    state_path = control / (args.name + "-process.json")
    if state_path.exists() or (root / job["output"]).exists():
        raise ValueError("NEW_JOB_AND_OUTPUT_REQUIRED")
    state = {"status": "STARTING", "pid": os.getpid(), "start_ticks": start_ticks(os.getpid()), "job": job}

    def save():
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(state_path)

    save()
    try:
        with (control / (args.name + ".log")).open("x") as log:
            child = subprocess.Popen(job["command"], cwd=root,
                env={**os.environ, "PYTHONPATH": str(candidate / "src") + os.pathsep + str(candidate / "benchmarks")},
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            state.update(status="RUNNING", child_pid=child.pid, child_start_ticks=start_ticks(child.pid))
            save()
            code = child.wait()
            state.update(returncode=code, status="COMPLETED_REVIEW_REQUIRED" if code == 0 else "FAILED_REVIEW_REQUIRED")
    except BaseException as error:
        state.update(status="FAILED_REVIEW_REQUIRED", error=type(error).__name__)
        raise
    finally:
        save()
    return state.get("returncode", 1)


if __name__ == "__main__":
    raise SystemExit(main())
