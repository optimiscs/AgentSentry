"""Six fixed public inputs, CPU/GPU FP32 parity; no labels or tools."""
from pathlib import Path
import sys, importlib.util, json, hashlib
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from run_piguard_full_context import classify, LOADER_SHA
import os
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
loader = ROOT / "artifacts/run_piguard_cpu.py"
assert hashlib.sha256(loader.read_bytes()).hexdigest() == LOADER_SHA
spec = importlib.util.spec_from_file_location("pinned_loader", loader)
helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
helper.MODEL = ROOT / "artifacts/models/piguard-dd78b24e3301"
import torch, transformers
from transformers import pipeline
torch.set_num_threads(2); torch.set_num_interop_threads(1); torch.manual_seed(0)
torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
model, tokenizer, manifest = helper.load_model()
rows = [json.loads(line) for line in (ROOT / "artifacts/mpbench-protocol-v1/inputs.jsonl").read_text().splitlines()]
texts = ["The meeting starts at noon.", "A meeting note. " * 170] + [r["external_content"][0]["text"] for r in rows[:4]]
cpu = pipeline("text-classification", model=model, tokenizer=tokenizer, device=-1)
a = [classify(tokenizer, cpu, text) for text in texts]
gpu = pipeline("text-classification", model=model, tokenizer=tokenizer, device="cuda:0")
b = [classify(tokenizer, gpu, text) for text in texts]
diffs = [abs(x["injection_probability"] - y["injection_probability"]) for x,y in zip(a,b)]
passed = max(diffs) <= 2e-4 and all(x["alert"] == y["alert"] for x,y in zip(a,b))
out = {"status":"PASS" if passed else "FAIL", "kind":"CPU_GPU_PARITY_NOT_BENCHMARK", "dtype":"float32", "tf32":False,
       "model_revision":manifest["revision"], "torch":torch.__version__, "transformers":transformers.__version__,
       "maximum_absolute_difference":max(diffs), "tolerance":2e-4,
       "rows":[{"text_sha256":hashlib.sha256(t.encode()).hexdigest(), "cpu":x, "gpu":y} for t,x,y in zip(texts,a,b)]}
(ROOT / "artifacts/lab3090-migration-v1/piguard-parity.json").write_text(json.dumps(out, indent=2)+"\n")
print(json.dumps({k:v for k,v in out.items() if k!="rows"}), flush=True)
if not passed:raise SystemExit(1)
