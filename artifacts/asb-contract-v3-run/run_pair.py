"""One frozen recovery pilot, preserving configuration and terminal state."""
from pathlib import Path
import argparse, json, os, subprocess, sys, hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument("--configuration",choices=["baseline","full"],required=True);a=p.parse_args()
control=ROOT/"artifacts/asb-contract-v3-run"
preflight=ROOT/"artifacts/lab3090-migration-v1"
assert json.loads((preflight/"asb-data-preflight.json").read_text())["status"]=="PASS"
readiness=preflight/("model-readiness.json" if a.configuration=="baseline" else "model-readiness-replica.json")
assert json.loads(readiness.read_text())["status"]=="PASS"
config_path=ROOT/"deploy/lab3090"/("serving.json" if a.configuration=="baseline" else "serving-replica.json")
serving=json.loads(config_path.read_text());port=serving["arguments"][serving["arguments"].index("--port")+1]
candidate=ROOT/"artifacts/development/asb-contract-v3"
assert hashlib.sha256((candidate/"source-candidate.tar.gz").read_bytes()).hexdigest()=="386892c47a342ec3df4129ea578b300bf6909b5b1c634d5633e75ea9d61cbba8"
frozen=json.loads((candidate/"candidate-manifest.json").read_text())
for relative,expected in frozen["files"].items():
 assert hashlib.sha256((candidate/relative).read_bytes()).hexdigest()==expected,relative
output=ROOT/("artifacts/benchmarks/asb/asb-lab3090-qwen35-9b-contract-v3-"+a.configuration+"-s0")
if output.exists():raise ValueError("NEW_RECOVERY_OUTPUT_REQUIRED")
command=[sys.executable,str(candidate/"benchmarks/run_asb.py"),"--source",str(ROOT/"artifacts/upstream/ASB-1f561dccf92d"),"--index",str(ROOT/"artifacts/asb-protocol-v1/scenario-index.jsonl"),"--memory",str(ROOT/"artifacts/asb-memory-e5-v1"),"--output",str(output),"--url",f"http://127.0.0.1:{port}/v1","--model","Qwen/Qwen3.5-9B","--configuration",a.configuration,"--modes","mixed","DPI_OPI","DPI_MP","OPI_MP","--limit-per-agent","1","--workers","2","--max-tokens","4096","--guard-max-tokens","4096","--max-workflow-steps","12","--seed","0","--workflow-format","json_schema","--guard-format","json_schema"]
state={"status":"RUNNING","pid":os.getpid(),"start_ticks":Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19],"configuration":a.configuration,"model_revision":serving["model_revision"],"serving_config_sha256":hashlib.sha256(config_path.read_bytes()).hexdigest(),"command":command,"hardware":"Lab3090; one RTX3090 per replica; CPU/shared host not a controlled latency benchmark"}
path=control/("asb-"+a.configuration+"-process.json")
def save():
 state["updated_at"]=datetime.now(timezone.utc).isoformat();tmp=path.with_suffix(".tmp");tmp.write_text(json.dumps(state,indent=2)+"\n");tmp.replace(path)
save()
try:
 with (control/("asb-"+a.configuration+".log")).open("x") as log:
  child=subprocess.Popen(command,cwd=ROOT,env={**os.environ,"PYTHONPATH":str(candidate/"src")+os.pathsep+str(candidate/"benchmarks"),"HF_HUB_OFFLINE":"1"},stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  state.update(child_pid=child.pid,child_start_ticks=Path(f"/proc/{child.pid}/stat").read_text().rsplit(")",1)[1].split()[19]);save()
  code=child.wait();state.update(returncode=code,status="COMPLETED_REVIEW_REQUIRED" if code==0 else "FAILED_REVIEW_REQUIRED")
except BaseException as exc:
 state.update(status="FAILED_REVIEW_REQUIRED",error=type(exc).__name__+":"+str(exc));raise
finally:save()
if state.get("returncode",1)!=0:raise SystemExit(1)
