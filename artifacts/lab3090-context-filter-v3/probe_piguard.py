"""Pinned PIGuard reference on the same selected native observations, CPU only.

Imports the previously reviewed full-field classifier; no model code is copied.
No task, cohort label, or attack goal enters the classifier. This is neither
an AgentDojo actor run nor an independent held-out detector acceptance set.
"""
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
control = Path(__file__).resolve().parent
source = root / "artifacts/piguard-mpbench-lab3090-full-context-v1/source-snapshot/scripts"
sys.path.insert(0, str(source))
sys.path.append(str(root / "scripts"))
from run_piguard_full_context import classify, LOADER_SHA, MODEL_MANIFEST_SHA

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  TOKENIZERS_PARALLELISM="false", CUDA_VISIBLE_DEVICES="")
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
packet = control / "paired-inputs.json"
assert sha(packet) == "a3e2f74bf9bd777c7ded4c071bacde73322e22ab70b4935afdc9219b749d7182"
loader = root / "artifacts/run_piguard_cpu.py"
assert sha(loader) == LOADER_SHA
spec = importlib.util.spec_from_file_location("pinned_piguard_loader", loader)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.MODEL = root / "artifacts/models/piguard-dd78b24e3301"
assert sha(helper.MODEL / "agentsentry-model.json") == MODEL_MANIFEST_SHA
output = control / "diagnostic-piguard"
output.mkdir(exist_ok=False)
started = time.monotonic()
state = {"status": "LOADING", "pid": os.getpid(),
         "start_ticks": Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19],
         "started_at": datetime.now(timezone.utc).isoformat(), "planned": 32,
         "input_field": "tool_response only", "input_sha256": sha(packet),
         "native_evaluator_run": False, "acceptance": "NOT_EVALUATED",
         "source_files": {str(p.relative_to(root)): sha(p) for p in
                          [Path(__file__), loader, source / "run_piguard_full_context.py",
                           source / "score_mpbench_checkpoint.py", source / "prepare_mpbench.py",
                           root / "scripts/input_screen_metrics.py"]}}

def save():
    state["observed_at"] = datetime.now(timezone.utc).isoformat()
    state["elapsed_seconds"] = time.monotonic() - started
    (output / "progress.json").write_text(json.dumps(state, indent=2) + "\n")

save()
try:
    import torch
    import transformers
    from transformers import pipeline
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    model, tokenizer, manifest = helper.load_model()
    assert all(p.dtype == torch.float32 for p in model.parameters())
    classifier = pipeline("text-classification", model=model, tokenizer=tokenizer, device=-1)
    state.update(status="RUNNING", load_seconds=time.monotonic() - started,
                 model_revision=manifest["revision"], dtype="float32", device="cpu",
                 torch_threads=2, torch=torch.__version__, transformers=transformers.__version__,
                 threshold=0.5, maximum_content_tokens=2046, truncation=False)
    save()
    rows = []
    for item in json.loads(packet.read_text())["inputs"]:
        begin = time.monotonic()
        row = {"case_id": item["case_id"], "input_hash": item["input_hash"],
               "cohort": item["cohort"], "status": "error"}
        try:
            row.update(classify(tokenizer, classifier, item["input"]["tool_response"]), status="ok")
        except Exception as exc:
            row["error"] = type(exc).__name__ + ":" + str(exc)
        row["seconds"] = time.monotonic() - begin
        rows.append(row)
        with (output / "per_case.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        state.update(recorded=len(rows), errors=sum(r["status"] != "ok" for r in rows))
        save()
    state["status"] = "COMPLETED_REVIEW_REQUIRED"
    (output / "metrics.json").write_text(json.dumps(state, indent=2) + "\n")
except Exception as exc:
    state.update(status="FAILED_REVIEW_REQUIRED", error=type(exc).__name__ + ":" + str(exc))
    raise
finally:
    save()
    print(json.dumps(state), flush=True)
raise SystemExit(bool(state["errors"]))
