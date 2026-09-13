#!/usr/bin/env python3
"""CPU tokenizer audit of a proposed LOO proxy on completed AgentDojo traces.

No weights, HTTP calls, action execution, attribution scores or defense claims.
Keeps message envelopes while blanking one source's content. Uses the same
observed assistant turn as the target in every variant, never a new model answer.
"""

import argparse
import copy
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def token_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def split_target(prefix, completed):
    if not prefix or completed[:len(prefix)] != prefix or len(completed) <= len(prefix):
        raise ValueError("SCORING_TARGET_PREFIX_MISMATCH")
    return completed[len(prefix):]


def variants(messages):
    users = [i for i, m in enumerate(messages) if m["role"] == "user"]
    if len(users) != 1:
        raise ValueError("EXPECTED_ONE_ORIGINAL_USER_REQUEST")
    yield "full", copy.deepcopy(messages)
    indices = [("without_user", users[0])] + [
        ("without_tool_" + str(i), i) for i, m in enumerate(messages) if m["role"] == "tool"
    ]
    for name, index in indices:
        changed = copy.deepcopy(messages)
        changed[index]["content"] = ""
        yield name, changed


def wire_messages(transcript, model):
    from agentdojo.agent_pipeline.llms.openai_llm import _message_to_openai
    from agentdojo.functions_runtime import FunctionCall
    restored = copy.deepcopy(transcript)
    for message in restored:
        if message.get("tool_calls"):
            message["tool_calls"] = [FunctionCall(**c) for c in message["tool_calls"]]
        if message.get("tool_call"):
            message["tool_call"] = FunctionCall(**message["tool_call"])
    wire = [_message_to_openai(m, model) for m in restored]
    wire[0]["role"] = "system"
    # vLLM 0.17.1 chat_utils normalizes serialized arguments before templating.
    for message in wire:
        for call in message.get("tool_calls", []):
            call["function"]["arguments"] = json.loads(call["function"]["arguments"])
    return wire


def case_budget(row, tools, tokenizer, model, read_tools, limit):
    wire = wire_messages(row["transcript"], model)
    turns, checks, response_index = [], [], 0

    def render(messages, generation):
        return tokenizer.apply_chat_template(messages, tools=tools, tokenize=True,
                                              add_generation_prompt=generation, enable_thinking=False)

    for index, assistant in enumerate(wire):
        if assistant["role"] != "assistant":
            continue
        prefix = render(wire[:index], True)
        observed = row["model_responses"][response_index]["usage"]["prompt_tokens"]
        checks.append({"response_index": response_index, "rendered": len(prefix), "observed": observed})
        response_index += 1
        if len(prefix) != observed:
            raise ValueError("ACTOR_PROMPT_TOKEN_COUNT_MISMATCH:" + str(checks[-1]))
        calls = assistant.get("tool_calls", [])
        if not calls or all(call["function"]["name"] in read_tools for call in calls):
            continue
        tool_count = sum(m["role"] == "tool" for m in wire[:index])
        if not tool_count:
            continue
        target, batch = None, []
        for name, messages in variants(wire[:index]):
            pre = render(messages, True)
            full = render([*messages, assistant], False)
            suffix = split_target(pre, full)
            if target is not None and suffix != target:
                raise ValueError("ABLATION_CHANGED_SCORING_TARGET")
            target = suffix
            batch.append({"variant": name, "prefix_tokens": len(pre), "target_tokens": len(suffix),
                          "total_tokens": len(full), "prefix_token_sha256": token_hash(pre),
                          "target_token_sha256": token_hash(suffix), "within_context_limit": len(full) <= limit})
        turns.append({"assistant_index": index, "tool_names": [c["function"]["name"] for c in calls],
                      "untrusted_observations": tool_count, "contexts": len(batch),
                      "scoring_tokens": sum(b["total_tokens"] for b in batch), "batch": batch})
    if response_index != row["model_calls"] or response_index != len(row["model_responses"]):
        raise ValueError("ACTOR_TRACE_RESPONSE_COUNT_MISMATCH")
    return {"case_id": row["case_id"], "status": "ok", "actor_prompt_checks": checks, "privileged_turns": turns}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-limit", type=int, default=32768)
    args = parser.parse_args()
    assert not args.output.exists(), "NEW_OUTPUT_REQUIRED"
    import agentdojo
    from agentdojo.agent_pipeline.llms.openai_llm import _function_to_openai
    from agentdojo.functions_runtime import FunctionsRuntime
    from agentdojo.task_suite import get_suite
    from agentdojo_catalog import READ
    import local_model
    from transformers import AutoTokenizer, __version__ as transformers_version
    assert Path(agentdojo.__file__).resolve().parents[2] == args.source.resolve()
    assert args.context_limit > 0
    candidate_manifest = json.loads((args.candidate / "candidate-manifest.json").read_text())
    for name, expected in candidate_manifest["files"].items():
        assert sha(args.candidate / name) == expected, name
    run_manifest = json.loads((args.run / "manifest.json").read_text())
    assert Path(local_model.__file__).resolve().parents[1] == args.candidate.resolve()
    assert local_model.source_hashes(args.candidate) == run_manifest["source_files"]
    assert local_model.support_hashes() == run_manifest["support_files"]
    assert json.loads((args.source / "agentsentry-source.json").read_text())["commit"] == run_manifest["benchmark_commit"]
    metrics = json.loads((args.run / "metrics.json").read_text())
    assert metrics["all_cases_evaluated"] and run_manifest["actor_thinking"] is False
    rows = [json.loads(line) for line in (args.run / "per_case.jsonl").read_text().splitlines()]
    assert len(rows) == len({r["case_id"] for r in rows}) == len(run_manifest["planned_ids"])
    assert {r["case_id"] for r in rows} == set(run_manifest["planned_ids"])
    assert all(r["status"] == "ok" for r in rows)
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True, trust_remote_code=False)
    tools = {suite: [_function_to_openai(t) for t in FunctionsRuntime(get_suite(run_manifest["version"], suite).tools).functions.values()]
             for suite in {r["suite"] for r in rows}}
    started, records = time.perf_counter(), []
    for row in rows:
        try:
            result = case_budget(row, tools[row["suite"]], tokenizer, run_manifest["model"], READ, args.context_limit)
        except Exception as exc:
            result = {"case_id": row["case_id"], "status": "error", "error": type(exc).__name__ + ":" + str(exc)}
        records.append(result)
    turns = [t for r in records for t in r.get("privileged_turns", [])]
    contexts = [c for t in turns for c in t["batch"]]
    full_tokens = sum(t["batch"][0]["total_tokens"] for t in turns)
    summary = {"cases": len(records), "valid": sum(r["status"] == "ok" for r in records),
               "actor_prompt_counts_verified": sum(len(r.get("actor_prompt_checks", [])) for r in records),
               "privileged_turns_with_observations": len(turns), "scoring_contexts": len(contexts),
               "scoring_tokens": sum(c["total_tokens"] for c in contexts),
               "unablated_scoring_tokens": full_tokens,
               "token_multiplier_over_single_scoring": sum(c["total_tokens"] for c in contexts) / full_tokens if full_tokens else None,
               "max_context_tokens": max((c["total_tokens"] for c in contexts), default=0),
               "over_context_limit": sum(not c["within_context_limit"] for c in contexts),
               "max_contexts_per_turn": max((t["contexts"] for t in turns), default=0),
               "two_context_chunks_if_statically_batched": sum(math.ceil(t["contexts"] / 2) for t in turns),
               "cpu_tokenizer_seconds": time.perf_counter() - started}
    report = {"status": "TOKENIZER_AUDIT_NOT_MODEL_EVALUATION", "created_at": datetime.now(timezone.utc).isoformat(),
              "run": str(args.run), "model": run_manifest["model"], "thinking": False,
              "model_calls": 0, "weights_loaded": False, "transformers_version": transformers_version,
              "runner_sha256": sha(Path(__file__)), "candidate_manifest_sha256": sha(args.candidate / "candidate-manifest.json"),
              "run_files": {n: sha(args.run / n) for n in ["manifest.json", "metrics.json", "per_case.jsonl"]},
              "tokenizer_files": {p.name: sha(p) for p in args.model_path.iterdir() if p.is_file() and p.name in {"tokenizer.json", "tokenizer_config.json", "chat_template.jinja"}},
              "active_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
              "scope": "Completed development cases, no hidden evaluation metadata enters rendering. Every retained actor prompt count checked against saved vLLM usage. Action target identical across variants.",
              "adaptations": ["Qwen3.5-9B proxy candidate, not the paper's Gemma proxy", "Blank source content while retaining chat envelopes", "Target is observed assistant text plus tool calls and closing template marker; no generated thoughts", "No observed latency/ASR/attribution scores; token count is not FLOPs or wall time"],
              "summary": summary, "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["valid"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
