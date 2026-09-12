#!/usr/bin/env python3
"""CPU-only full local gateway microbenchmark; no model/HTTP/approval waiting."""

import argparse
import concurrent.futures
import json
import math
import os
import resource
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from agentsentry.config import Settings
from agentsentry.demo import seed
from agentsentry.gateway.runtime import Runtime
from agentsentry.schemas import SourceType, ToolCall

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=200)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    cpus = sorted(os.sched_getaffinity(0))[:4]
    os.sched_setaffinity(0, cpus)
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    output = []
    for size in (1024, 8192):
        for concurrency in (1, 4):
            with tempfile.TemporaryDirectory(
                prefix="perf-", dir=ROOT / "artifacts"
            ) as temp:
                root = Path(temp)
                cfg = Settings(
                    root, root / "workspace", ROOT / "policies/default.aspolicy"
                )
                seed(cfg)
                rt = Runtime(cfg)
                text = ("This is a public code review document. " * 300)[:size]
                # Pre-authorized tasks; each has room for the input and resulting tool output.
                sessions = [
                    rt.create_session("review code")
                    for _ in range(math.ceil((args.samples + args.warmup) / 32))
                ]

                def operation(index):
                    start = time.perf_counter()
                    s = sessions[index // 32]
                    try:
                        rt.scan(
                            s.session_id, s.owner, SourceType.DOCUMENT, "perf", text
                        )
                        result = rt.call(
                            ToolCall(
                                session_id=s.session_id,
                                tool="fs.read",
                                arguments={"path": "README.md"},
                            )
                        )
                        status = result.status
                    except Exception:
                        status = "error"
                    return {
                        "index": index,
                        "milliseconds": (time.perf_counter() - start) * 1000,
                        "status": status,
                    }

                with concurrent.futures.ThreadPoolExecutor(concurrency) as pool:
                    for _ in pool.map(operation, range(args.warmup)):
                        pass
                    # Bounded batches measure actual contention without an artificial backlog of 1000 jobs.
                    results = []
                    for start in range(
                        args.warmup, args.warmup + args.samples, concurrency
                    ):
                        submitted = time.perf_counter()
                        futures = [
                            pool.submit(operation, i)
                            for i in range(
                                start,
                                min(start + concurrency, args.warmup + args.samples),
                            )
                        ]
                        for f in futures:
                            r = f.result()
                            r["batch_completion_ms"] = (
                                time.perf_counter() - submitted
                            ) * 1000
                            results.append(r)
                values = sorted(r["milliseconds"] for r in results)
                row = {
                    "input_bytes": size,
                    "concurrency": concurrency,
                    "n": len(results),
                    "warmup": args.warmup,
                    "p50_ms": statistics.median(values),
                    "p95_ms": values[math.ceil(0.95 * len(values)) - 1],
                    "p99_ms": values[math.ceil(0.99 * len(values)) - 1],
                    "max_ms": max(values),
                    "errors": sum(r["status"] != "succeeded" for r in results),
                    "queue_included": True,
                }
                row["pass"] = row["p95_ms"] <= 200 and row["errors"] == 0
                output.append(row)
                rt.close()
                (ROOT / f"artifacts/perf-{size}-{concurrency}.json").write_text(
                    json.dumps(results)
                )
                print(json.dumps(row), flush=True)
    report = {
        "name": "CPU 网关性能实测",
        "kind": "local_gateway_benchmark",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "cpu_affinity": cpus,
            "address_space_limit_gib": 8,
            "gpu_used": False,
            "configurations": output,
            "pass": all(r["pass"] for r in output),
        },
        "limits": [
            "包含扫描、归一化、策略、SQLite 审计和本地文件执行；不含网络 HTTP 传输与上游 Agent 生成。",
            "CPU affinity 与虚拟地址空间上限用于本次隔离；共享主机存在其他任务，非独占物理 4 核/8 GiB。",
            "排队为每批并发 1/4 的线程锁等待；不代表无界请求队列或生产容量。",
        ],
    }
    (ROOT / "artifacts/perf-cpu.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
