"""Reconstruct selected sanitizer inputs via recorded native simulated calls; no model or score."""
import argparse,json
from pathlib import Path
from agentdojo.task_suite import get_suite
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentsentry.schemas import canonical,digest
p=argparse.ArgumentParser();p.add_argument('--records',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument("--case-id", action="append", required=True);a=p.parse_args()
assert not a.output.exists()
results=[]
for line in a.records.read_text().splitlines():
 row=json.loads(line)
 if row['case_id'] not in a.case_id:continue
 suite=get_suite('v1.2.2',row['suite']);user=suite.user_tasks[row['user_task']]
 env=user.init_environment(suite.load_and_inject_default_environment(row.get('injections',{})))
 runtime=FunctionsRuntime(suite.tools);index=0
 for call in row['calls']:
  if not call['simulated_dispatch']:continue
  result,error=runtime.run_function(env,call['tool'],call['arguments'])
  raw=error or tool_result_to_str(result)
  payload={'original_user_request':user.PROMPT,'tool_call':{'name':call['tool'],'arguments':call['arguments']},'tool_response':raw}
  original=row['sanitizer_trace'][index];index+=1
  assert digest(payload)==original['input_hash'],(row['case_id'],index,'SOURCE_REPLAY_MISMATCH')
  results.append({'case_id':row['case_id'],'input':payload,'trace':original})
a.output.write_text(json.dumps({'kind':'native source replay only; no new benchmark scores','input_records_hash':digest(a.records.read_text()),'cases':results},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'reconstructed_inputs':len(results),'all_inputs_hash_matched':True}))
