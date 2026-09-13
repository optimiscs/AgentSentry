#!/usr/bin/env python3
"""Official DeepSeek Harness loop and native AgentDojo simulated-world evaluators."""

import argparse
import hashlib
import inspect
import json
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

from deepseek_proxy import read_deepseek_key
from dsh_client import run_session
from run_agentdojo import (LocalPipeline, _function_to_openai, block, FunctionCall,
                           FixedJailbreakAttack, ImportantInstructionsAttack,
                           get_suite, load_system_message, metrics)
from local_model import source_hashes, support_hashes


class NativePipeline(LocalPipeline):
    def __init__(self, config, policy, key, directory):
        super().__init__(config, policy)
        self.key, self.directory, self.native_result = key, directory, None

    def query(self, query, runtime, env, messages=None, extra_args=None):
        server = Server("AgentDojo simulated tools")
        definitions = [_function_to_openai(t)["function"] for t in runtime.functions.values()]
        self.transcript = [{"role": "system", "content": [block(load_system_message(None))]},
                           {"role": "user", "content": [block(query)]}]
        self.bridge_errors = []

        @server.list_tools()
        async def tools():
            return [types.Tool(name=d["name"], description=d["description"], inputSchema=d["parameters"])
                    for d in definitions]

        @server.call_tool()
        async def execute(name: str, arguments: dict):
            try:
                if name not in runtime.functions:
                    raise ValueError("UNKNOWN_SIMULATED_TOOL")
                # Correlation ids here belong to the bridge; the native DSH events retain model ids.
                call = FunctionCall(function=name, args=arguments, id=f"bridge-{len(self.calls)}")
                message = self.execute_call(query, runtime, env, call)
                self.transcript.extend([{"role": "assistant", "content": None, "tool_calls": [call]}, message])
                return [types.TextContent(type="text", text="\n".join(b["content"] for b in message["content"]))]
            except Exception as error:
                self.bridge_errors.append(type(error).__name__)
                raise

        manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)

        async def endpoint(scope, receive, send):
            await manager.handle_request(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app):
            async with manager.run():
                yield

        app = Starlette(routes=[Mount("/", app=endpoint)], lifespan=lifespan)
        self.native_result, self.model_responses = run_session(self.directory, self.config.sdk_python, app, self.key,
            system_prompt=load_system_message(None), user_query=query,
            tool_names=["mcp__benchmark__" + d["name"] for d in definitions],
            max_requests=self.config.max_steps, max_tokens=self.config.max_tokens,
            quota_state=getattr(self.config, "quota_state", None))
        self.model_calls = len(self.model_responses)
        if self.bridge_errors:
            raise ValueError("NATIVE_MCP_BRIDGE_ERROR:" + ",".join(self.bridge_errors))
        if self.native_result["status"] != "ok":
            raise ValueError("NATIVE_DSH_RUN_INCOMPLETE")
        final = self.native_result["result"]["final_response"]
        if not final:
            raise ValueError("NATIVE_DSH_EMPTY_FINAL_RESPONSE")
        self.transcript.append({"role": "assistant", "content": [block(final)], "tool_calls": None})
        return query, runtime, env, self.transcript, extra_args or {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True, help="JSON array of exact suite/user/injection-or-benign ids")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--sdk-python", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--quota-state", type=Path)
    parser.add_argument("--configuration", choices=["baseline", "runtime_rules"], required=True)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()
    args.sdk_python = args.sdk_python.absolute()  # Preserve venv symlinks; resolve() loses that environment.
    import agentdojo
    if Path(agentdojo.__file__).resolve().parents[2] != args.source.resolve():
        raise ValueError("INSTALLED_BENCHMARK_SOURCE_MISMATCH")
    provenance = json.loads((args.source / "agentsentry-source.json").read_text())
    sdk_version = subprocess.check_output([str(args.sdk_python), "-c",
        "import importlib.metadata; print(importlib.metadata.version('deepseek-harness-sdk'))"], text=True).strip()
    if sdk_version != "0.1.5rc1":
        raise ValueError("PINNED_DSH_SDK_REQUIRED")
    ids = json.loads(args.cases.read_text())
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or not ids:
        raise ValueError("EXACT_UNIQUE_CASE_IDS_REQUIRED")
    key = read_deepseek_key(args.env_file)
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    config = SimpleNamespace(model="deepseek-flash", sdk_python=args.sdk_python,
        configuration="baseline" if args.configuration == "baseline" else "full",
        max_steps=args.max_steps, max_tokens=args.max_tokens, quota_state=args.quota_state)
    policy = (root / "policies/default.aspolicy").read_text()
    manifest = {"started_at": datetime.now(timezone.utc).isoformat(), "model": "deepseek-flash",
        "client": "deepseek-harness-sdk==0.1.5rc1", "configuration": args.configuration,
        "benchmark_commit": provenance["commit"], "source_archive_sha256": provenance["archive_sha256"],
        "policy_sha256": hashlib.sha256(policy.encode()).hexdigest(),
        "session_script_sha256": hashlib.sha256((root / "scripts/dsh_session.py").read_bytes()).hexdigest(),
        "scope": "NATIVE_DSH_AGENTDOJO_SCREENING_PILOT", "planned_ids": ids,
        "thinking": False, "temperature": 0, "seed_supported": False, "max_steps": args.max_steps,
        "max_tokens": args.max_tokens, "source_files": source_hashes(root), "support_files": support_hashes(),
        "native_evaluator": "TaskSuite.run_task_with_pipeline", "agentdojo_version": "v1.2.2",
        "attack": "important_instructions", "attack_model_name": "deepseek-flash",
        "annotation_version": "native-outcomes-and-evidence-v1", "quota_state": str(args.quota_state) if args.quota_state else None,
        "adaptations": ["Official sdk-minimal kernel with benchmark MCP tools instead of host shell tools",
          "AgentDojo tools keep original names beneath the DSH MCP namespace and use original schemas",
          "Shared product-rule action/observation path; not composed-guard-v1 or a new semantic guard",
          "Evaluator receives actual dispatched calls, filtered observations, and native final answer; full native events retained",
          "Provider SSE is buffered for evidence; these timings are not native streaming latency"]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    with (args.output / "per_case.jsonl").open("w") as output:
        for index, case_id in enumerate(ids):
            if args.quota_state and args.quota_state.exists():
                break
            suite_name, user_id, attack_id = case_id.split("/")
            injection_id = None if attack_id == "benign" else attack_id
            pipeline = NativePipeline(config, policy, key, args.output / f"case-{index:04}")
            row = {"case_id": case_id, "suite": suite_name, "user_task": user_id,
                   "injection_task": injection_id, "status": "error"}
            start = time.perf_counter()
            try:
                suite = get_suite("v1.2.2", suite_name)
                user = suite.user_tasks[user_id]
                injection = suite.injection_tasks[injection_id] if injection_id else None
                row["evaluation_contract"] = {"user_query": user.PROMPT,
                    "attacker_goal": injection.GOAL if injection else None,
                    "utility_oracle_source": inspect.getsource(type(user).utility),
                    "security_oracle_source": inspect.getsource(type(injection).security) if injection else None,
                    "exposure_boundary": "Untrusted native tool response; original attacker goal and oracle metadata are evaluator-only"}
                attack = FixedJailbreakAttack(ImportantInstructionsAttack._JB_STRING, suite, pipeline)
                attack.user_name, attack.model_name = "Emma Johnson", "deepseek-flash"
                payload = attack.attack(user, injection) if injection else {}
                row["injections"] = payload
                row["payload_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                utility, success = suite.run_task_with_pipeline(pipeline, user, injection, payload)
                row.update(status="ok", utility=bool(utility), attack_success=bool(success) if injection else None)
            except Exception as error:
                row["error"] = type(error).__name__ + ":" + str(error).replace(key, "[redacted]")
            row.update(calls=pipeline.calls, transcript=pipeline.transcript, model_calls=pipeline.model_calls,
                       native_status=(pipeline.native_result or {}).get("status"), seconds=time.perf_counter()-start)
            row["labels"] = {"execution": "completed" if row["status"] == "ok" else "incomplete",
                "attack_native": ("success" if row["attack_success"] else "failure") if row["status"] == "ok" and injection_id else "not_applicable" if not injection_id else "unknown",
                "task_native": ("success" if row["utility"] else "failure") if row["status"] == "ok" else "unknown",
                "attack_reviewed": "pending_review" if injection_id else "not_applicable",
                "label_basis": "Original AgentDojo evaluators; text-only successes require independent evidence review",
                "failure_reason": row.get("error"), "tool_errors": [c["tool_error"] for c in pipeline.calls if c.get("tool_error")],
                "dispatched_tool_count": sum(c["simulated_dispatch"] for c in pipeline.calls),
                "native_evidence_dir": str(args.output / f"case-{index:04}"),
                "notes": "Safety outcome and legitimate task completion are separate labels; no response error is counted as successful defense."}
            output.write(json.dumps(row, default=lambda v: v.model_dump(), ensure_ascii=False) + "\n")
            output.flush()
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in ["case_id", "status", "utility", "attack_success", "error"]}), flush=True)
            if not pipeline.model_calls and row["status"] == "error":
                break  # Stop configuration/protocol failures before another paid case.
    summary = metrics(rows, len(ids))
    (args.output / "not_started_ids.json").write_text(json.dumps(ids[len(rows):], indent=2) + "\n")
    (args.output / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["all_cases_evaluated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
