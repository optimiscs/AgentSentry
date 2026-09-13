"""Run one predeclared local experiment and preserve its actual exit status."""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("job", choices=["baseline", "full"])
args = parser.parse_args()
job = json.loads((CONTROL / "jobs.json").read_text())[args.job]
candidate = ROOT / job["candidate"]
for name, expected in json.loads((candidate / "candidate-manifest.json").read_text())["files"].items():
    assert hashlib.sha256((candidate / name).read_bytes()).hexdigest() == expected, name
assert not (ROOT / job["output"]).exists(), "NEW_OUTPUT_REQUIRED"
state_path = CONTROL / (args.job + "-process.json")
assert not state_path.exists(), "NEW_JOB_REQUIRED"

def start_ticks(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]

state = {"status": "STARTING", "pid": os.getpid(), "start_ticks": start_ticks(os.getpid()), "job": job}

def save():
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(state_path)

save()
try:
    with (CONTROL / (args.job + ".log")).open("x") as log:
        child = subprocess.Popen(
            job["command"], cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(candidate / "src") + os.pathsep + str(candidate / "benchmarks"), "HF_HUB_OFFLINE": "1"},
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        )
        state.update(status="RUNNING", child_pid=child.pid, child_start_ticks=start_ticks(child.pid))
        save()
        code = child.wait()
        state.update(returncode=code, status="COMPLETED_REVIEW_REQUIRED" if code == 0 else "FAILED_REVIEW_REQUIRED")
except BaseException as exc:
    state.update(status="FAILED_REVIEW_REQUIRED", error=type(exc).__name__ + ":" + str(exc))
    raise
finally:
    save()
raise SystemExit(state.get("returncode", 1))
