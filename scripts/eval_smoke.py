#!/usr/bin/env python3
import hashlib, json, tempfile, time
from pathlib import Path
from datetime import datetime, timezone
from agentsentry.config import Settings
from agentsentry.demo import seed
from agentsentry.gateway.runtime import Runtime
from agentsentry.schemas import SourceType, ToolCall

root = Path(__file__).resolve().parents[1]
fixture = root / "benchmarks/fixtures/golden.json"
results = []
for case in json.loads(fixture.read_text()):
    with tempfile.TemporaryDirectory(prefix="golden-", dir=root / "artifacts") as tmp:
        p = Path(tmp)
        cfg = Settings(p, p / "workspace", root / "policies/default.aspolicy")
        seed(cfg)
        rt = Runtime(cfg)
        s = rt.create_session(case["task"], scope=case.get("scope", "."))
        start = time.perf_counter()
        if case.get("context"):
            rt.scan(
                s.session_id, s.owner, SourceType.DOCUMENT, case["id"], case["context"]
            )
        r = rt.call(
            ToolCall(
                session_id=s.session_id, tool=case["tool"], arguments=case["arguments"]
            )
        )
        executions = rt.store.execution_count()
        expected_execution = int(case["expected"] == "ALLOW")
        ok = (
            r.decision.decision == case["expected"]
            and executions == expected_execution
            and (
                r.status == "succeeded"
                if expected_execution
                else r.status in {"pending", "blocked"}
            )
        )
        results.append(
            {
                "case_id": case["id"],
                "expected": case["expected"],
                "actual": str(r.decision.decision),
                "status": r.status,
                "executions": executions,
                "expected_executions": expected_execution,
                "passed": ok,
                "reason_codes": r.decision.reason_codes,
                "latency_ms": (time.perf_counter() - start) * 1000,
                "action_id": r.action.action_id,
                "trace_id": s.trace_id,
            }
        )
        rt.close()
report = {
    "name": "20 条黄金功能回归",
    "kind": "development_regression",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
    "policy_sha256": hashlib.sha256(
        (root / "policies/default.aspolicy").read_bytes()
    ).hexdigest(),
    "summary": {
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "failed": sum(not r["passed"] for r in results),
    },
    "limits": [
        "样例参与开发调试；不是独立隐藏测试集，不能据此声称检测 F1 或公开 ASR 达标。",
        "HTTP 收件端点是本地模拟账本；文件、Git 与受限 Python 为真实工具。",
    ],
    "cases": results,
}
(root / "artifacts/golden-report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(report["summary"]))
raise SystemExit(any(not r["passed"] for r in results))
