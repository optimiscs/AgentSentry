"""Fixed-length serving comparison after the frozen ASB pilot has terminated.

Reuse the hash-pinned v1 process ownership, restoration and correctness helpers.
All new outputs have a separate directory; no historical result is amended.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "artifacts/vllm-tuning-v2-plan.json"
OUTPUT = ROOT / "artifacts/vllm-tuning-v2"
HELPER = ROOT / "artifacts/run_vllm_tuning_after_benchmarks.py"
HELPER_SHA = "1c2ef72aefd6f24e4cefe510838d80b50362e953f8a90139ad808cf324710183"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_helper():
    if sha(HELPER) != HELPER_SHA:
        raise ValueError("FROZEN_PROCESS_HELPER_CHANGED")
    spec = importlib.util.spec_from_file_location("vllm_tuning_v1_helpers", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workload(plan):
    item = plan["workload"]
    expected = {
        "input_tokens": 1024,
        "output_tokens": 256,
        "num_prompts": 16,
        "range_ratio": 0.0,
        "client_concurrencies": [2, 4],
        "cache_states": ["first_run", "repeat_identical_prompts"],
    }
    if any(item.get(key) != value for key, value in expected.items()):
        raise ValueError("UNREVIEWED_PERFORMANCE_WORKLOAD")
    return item


def command(plan, trial, directory, concurrency, cache_state):
    item = workload(plan)
    argv = trial["argv"]
    options = {
        "backend": "openai",
        "base-url": "http://127.0.0.1:18080",
        "endpoint": "/v1/completions",
        "model": argv[argv.index("--served-model-name") + 1],
        "tokenizer": argv[argv.index("--model") + 1],
        "dataset-name": "random",
        "random-input-len": item["input_tokens"],
        "random-output-len": item["output_tokens"],
        "random-range-ratio": item["range_ratio"],
        "random-prefix-len": 0,
        "num-prompts": item["num_prompts"],
        "max-concurrency": concurrency,
        "seed": {2: 0, 4: 1}[concurrency],
        "num-warmups": 0,
        "ready-check-timeout-sec": 0,
        "result-dir": directory,
        "result-filename": f"c{concurrency}-{cache_state}.json",
        "percentile-metrics": "ttft,tpot,itl,e2el",
        "metric-percentiles": "50,95,99",
    }
    cli = [str(Path(argv[0]).parent / "vllm"), "bench", "serve"]
    for key, value in options.items():
        cli.extend(["--" + key, str(value)])
    return cli + ["--ignore-eos", "--save-result", "--save-detailed", "--disable-tqdm"]


def check_result(result):
    for key in ("completed", "failed", "total_input_tokens", "total_output_tokens"):
        if type(result.get(key)) is not int:
            raise ValueError("INVALID_PERFORMANCE_COUNTER:" + key)
    expected = {
        "completed": 16,
        "failed": 0,
        "total_input_tokens": 16384,
        "total_output_tokens": 4096,
        "input_lens": [1024] * 16,
        "output_lens": [256] * 16,
        "errors": [""] * 16,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("INCOMPLETE_OR_CHANGED_PERFORMANCE_WORKLOAD")
    keys = [
        "duration",
        "output_throughput",
        "mean_ttft_ms",
        "mean_tpot_ms",
        "p95_ttft_ms",
        "p95_tpot_ms",
        "p95_e2el_ms",
    ]
    for key in keys:
        value = result.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError("INVALID_PERFORMANCE_METRIC:" + key)
    return {
        key: result[key]
        for key in [
            *keys,
            "completed",
            "failed",
            "total_input_tokens",
            "total_output_tokens",
        ]
    }


def sampling_preflight(plan):
    """Exercise the installed native sampler and pinned tokenizer without inference."""
    from vllm.benchmarks.datasets.datasets import RandomDataset
    from vllm.tokenizers import get_tokenizer

    item = workload(plan)
    base = json.loads((ROOT / "artifacts/local-model-27b-32k-command.json").read_text())
    tokenizer = get_tokenizer(base["argv"][base["argv"].index("--model") + 1])
    observed = []
    for seed in (0, 1):
        fingerprints = []
        for _ in range(2):
            rows = RandomDataset(random_seed=seed).sample(
                tokenizer,
                num_requests=item["num_prompts"],
                prefix_len=0,
                range_ratio=item["range_ratio"],
                input_len=item["input_tokens"],
                output_len=item["output_tokens"],
            )
            if len(rows) != 16 or any(
                row.prompt_len != 1024
                or row.expected_output_len != 256
                or len(tokenizer.encode(row.prompt, add_special_tokens=False)) != 1024
                for row in rows
            ):
                raise ValueError("NATIVE_RANDOM_SAMPLING_LENGTH_MISMATCH")
            fingerprints.append(
                hashlib.sha256(
                    json.dumps(
                        [row.prompt for row in rows], ensure_ascii=False
                    ).encode()
                ).hexdigest()
            )
        if fingerprints[0] != fingerprints[1]:
            raise ValueError("SAMPLE_REPLAY_NOT_IDENTICAL")
        observed.append(
            {
                "seed": seed,
                "records": 16,
                "input_tokens_each": 1024,
                "output_tokens_each": 256,
                "prompts_sha256": fingerprints[0],
            }
        )
    try:
        RandomDataset(random_seed=0).sample(
            tokenizer,
            num_requests=16,
            prefix_len=0,
            range_ratio=1.0,
            input_len=1024,
            output_len=256,
        )
    except ValueError as exc:
        if "minimum possible total input tokens" not in str(exc):
            raise
        previous_failure = str(exc)
    else:
        raise ValueError("V1_FAILURE_NOT_REPRODUCED_ON_INSTALLED_SAMPLER")
    return {
        "status": "PASS",
        "model_calls": 0,
        "sampler": "installed vllm RandomDataset",
        "executor_sha256": sha(Path(__file__)),
        "workloads": observed,
        "v1_failure_reproduced": previous_failure,
    }


def assert_asb_terminal(helper, plan, record):
    if helper.same_process(plan["dependency"]):
        raise ValueError("ASB_QUEUE_STILL_LIVE")
    if record.get("status") != "ASB_PILOT_FINISHED_REVIEW_REQUIRED":
        raise ValueError("ASB_TERMINAL_EVIDENCE_MISSING")
    jobs = record.get("jobs", [])
    if len(jobs) != 2 or {job.get("configuration") for job in jobs} != {
        "baseline",
        "full",
    }:
        raise ValueError("ASB_PAIRED_JOBS_MISSING")
    if any(
        job.get("status") != "RECORDED_NOT_ACCEPTED"
        or "exit_code" not in job
        or job.get("metrics", {}).get("recorded_cases") != 40
        for job in jobs
    ):
        raise ValueError("ASB_PAIR_NOT_FULLY_RECORDED")


def measure(helper, plan, trial, directory, state):
    env = dict(os.environ)
    env.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OPENAI_API_KEY="EMPTY",
        NO_PROXY="127.0.0.1,localhost",
    )
    env.pop("PYTHONPATH", None)
    for concurrency in workload(plan)["client_concurrencies"]:
        for cache_state in plan["workload"]["cache_states"]:
            name = f"c{concurrency}-{cache_state}"
            argv = command(plan, trial, directory, concurrency, cache_state)
            helper.write_json(directory / (name + "-command.json"), {"argv": argv})
            peak, started = 0, time.monotonic()
            with (directory / (name + ".log")).open("xb") as log:
                child = subprocess.Popen(
                    argv,
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                identity = helper.process(child.pid)
                try:
                    while child.poll() is None:
                        if time.monotonic() - started > 1200:
                            raise TimeoutError("PERFORMANCE_REQUEST_TIMEOUT")
                        usage = subprocess.check_output(
                            [
                                "nvidia-smi",
                                "--query-gpu=memory.used",
                                "--format=csv,noheader,nounits",
                            ],
                            text=True,
                            timeout=10,
                        )
                        peak = max(peak, *[int(line) for line in usage.splitlines()])
                        time.sleep(1)
                finally:
                    if child.poll() is None and identity:
                        helper.stop_owned_group(identity)
                if child.returncode:
                    raise RuntimeError(
                        "PERFORMANCE_CLI_FAILED:" + str(child.returncode)
                    )
            path = directory / (name + ".json")
            result = check_result(json.loads(path.read_text()))
            result.update(
                name=name,
                client_concurrency=concurrency,
                cache_state=cache_state,
                gpu_memory_peak_mib=peak,
                result_sha256=sha(path),
            )
            trial["measurements"].append(result)
            helper.save(state)


def run(helper, plan):
    def save(state):
        state["updated_at"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017 -- Local Python 3.9 support.
        helper.write_json(OUTPUT / "progress.json", state)

    helper.save = save
    OUTPUT.mkdir(exist_ok=False)
    state = {
        "status": "WAITING_FOR_ASB",
        "pid": os.getpid(),
        "trials": [],
        "executor_sha256": sha(Path(__file__)),
        "helper_sha256": HELPER_SHA,
        "plan_sha256": sha(PLAN),
        "owned_server": None,
        "restored": False,
        "quality_acceptance": "NOT_ACCEPTED",
    }
    stopped = False
    save(state)
    base = json.loads((ROOT / "artifacts/local-model-27b-32k-command.json").read_text())
    try:
        deadline = time.monotonic() + 86400
        while helper.same_process(plan["dependency"]):
            if time.monotonic() > deadline:
                raise TimeoutError("ASB_WAIT_EXCEEDED_24H")
            time.sleep(30)
        assert_asb_terminal(
            helper,
            plan,
            json.loads((ROOT / "docs/evidence/asb-pilot-progress.json").read_text()),
        )
        for relative, digest in plan["pins"].items():
            if sha(ROOT / relative) != digest:
                raise ValueError("FROZEN_TUNING_INPUT_CHANGED:" + relative)
        if (
            sha(PLAN) != state["plan_sha256"]
            or sha(Path(__file__)) != plan["executor_sha256"]
        ):
            raise ValueError("TUNING_VERSION_CHANGED")
        current = plan["current_model_process"]
        if (
            not helper.same_process(current)
            or helper.server_command(current["pid"]) != base["argv"]
        ):
            raise ValueError("EXPECTED_BASE_MODEL_IDENTITY_CHANGED")
        helper.assert_idle()
        stopped = True
        helper.stop_owned_group(current)
        for spec in plan["trials"]:
            helper.assert_no_clients()
            directory = OUTPUT / spec["id"]
            directory.mkdir()
            trial = {**spec, "measurements": [], "status": "STARTING"}
            state["trials"].append(trial)
            state["status"] = "RUNNING_TUNING"
            try:
                identity, seconds = helper.start_server(
                    spec["argv"], directory / "server.log", state
                )
                trial.update(
                    server_identity=identity, startup_seconds=seconds, status="CHECKING"
                )
                trial["checks"] = helper.checks(
                    spec["argv"][spec["argv"].index("--served-model-name") + 1]
                )
                if not all(check["passed"] for check in trial["checks"]):
                    raise ValueError("CORRECTNESS_CHECK_FAILED")
                trial["status"] = "MEASURING"
                save(state)
                measure(helper, plan, trial, directory, state)
                trial["status"] = "MEASURED_REVIEW_REQUIRED"
            except Exception as exc:  # noqa: BLE001 -- Preserve failure and always restore the owned service.
                trial.update(
                    status="FAILED_REVIEW_REQUIRED",
                    error=type(exc).__name__ + ":" + str(exc),
                )
            finally:
                if state["owned_server"]:
                    helper.stop_owned_group(state["owned_server"])
                    state["owned_server"] = None
                save(state)
        state["status"] = "TUNING_FINISHED_REVIEW_REQUIRED"
    except Exception as exc:  # noqa: BLE001 -- Queue boundary records failure before restoration.
        state.update(
            status="STOPPED_REVIEW_REQUIRED", error=type(exc).__name__ + ":" + str(exc)
        )
    finally:
        if stopped:
            try:
                if state["owned_server"]:
                    helper.stop_owned_group(state["owned_server"])
                if helper.group_members(plan["current_model_process"]["pid"]):
                    raise ValueError("BASE_MODEL_GROUP_NOT_STOPPED")
                identity, seconds = helper.start_server(
                    base["argv"], OUTPUT / "restored-server.log", state
                )
                state.update(
                    restored=True,
                    restored_server=identity,
                    restoration_startup_seconds=seconds,
                )
                helper.write_json(
                    OUTPUT / "restored-server.json", {"argv": base["argv"], **identity}
                )
            except Exception as exc:  # noqa: BLE001 -- Persist an actionable restoration failure.
                state.update(
                    status="RESTORATION_FAILED_REVIEW_REQUIRED",
                    restoration_error=str(exc),
                )
        save(state)
    return int(
        not state["restored"]
        or any(t["status"] != "MEASURED_REVIEW_REQUIRED" for t in state["trials"])
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sampling-preflight", action="store_true")
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    helper = load_helper()
    workload(plan)
    if args.sampling_preflight:
        result = sampling_preflight(plan)
        helper.write_json(ROOT / "artifacts/vllm-tuning-v2-sampling.json", result)
        print(json.dumps(result))
        return 0
    frozen = json.loads((ROOT / "artifacts/vllm-tuning-plan.json").read_text())
    if plan["trials"] != frozen["trials"]:
        raise ValueError("UNREVIEWED_SERVING_CONFIGURATIONS")
    return run(helper, plan)


if __name__ == "__main__":
    raise SystemExit(main())
