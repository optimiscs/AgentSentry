"""Local inference readiness checks; declared fixtures, not benchmark scores."""
import argparse, json, time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument("--replica",action="store_true");args=parser.parse_args()
url="http://127.0.0.1:"+("18081" if args.replica else "18080")+"/v1"
tool={"type":"function","function":{"name":"read_record","description":"Read one simulated record.","parameters":{"type":"object","properties":{"record_id":{"type":"string"}},"required":["record_id"],"additionalProperties":False}}}
cases=[
 ("plain",{"messages":[{"role":"user","content":"Compute 2+2. Reply with just the integer."}],"max_tokens":16}),
 ("json",{"messages":[{"role":"user","content":"Return exactly this JSON object: {\"ready\": true}"}],"max_tokens":64,"response_format":{"type":"json_object"}}),
 ("forced_tool",{"messages":[{"role":"user","content":"Use read_record to read record_id sample-1."}],"max_tokens":128,"tools":[tool],"tool_choice":{"type":"function","function":{"name":"read_record"}}}),
 ("auto_tool",{"messages":[{"role":"user","content":"Use read_record to read record_id sample-1."}],"max_tokens":128,"tools":[tool],"tool_choice":"auto"}),
]
results=[]
with httpx.Client(timeout=180,trust_env=False) as client:
 for name,case in cases:
  payload={"model":"Qwen/Qwen3.5-9B","temperature":0,"seed":0,**case};started=time.monotonic()
  response=client.post(url+"/chat/completions",json=payload);response.raise_for_status();raw=response.json()
  message=raw["choices"][0]["message"];passed=raw["choices"][0]["finish_reason"]!="length"
  if name=="plain":passed &= message["content"].strip()=="4"
  elif name=="json":passed &= json.loads(message["content"])=={"ready":True}
  else:
   calls=message.get("tool_calls",[])
   passed &= len(calls)==1 and calls[0]["function"]["name"]=="read_record" and json.loads(calls[0]["function"]["arguments"])=={"record_id":"sample-1"}
  results.append({"name":name,"passed":bool(passed),"seconds":time.monotonic()-started,"request":payload,"response":raw})
  print(json.dumps({k:v for k,v in results[-1].items() if k not in {"request","response"}}),flush=True)
report={"status":"PASS" if all(r["passed"] for r in results) else "FAIL","kind":"LOCAL_MODEL_READINESS_NOT_BENCHMARK","tool_executions":0,"checks":results}
(ROOT/"artifacts/lab3090-migration-v1"/("model-readiness-replica.json" if args.replica else "model-readiness.json")).write_text(json.dumps(report,indent=2)+"\n")
if report["status"]!="PASS":raise SystemExit(1)
