#!/usr/bin/env python3
"""Publish actual test artifacts into engineering docs; never mark research gates passed."""

import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs"


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    results = json.loads((ROOT / "artifacts/test-results.json").read_text())
    manifest = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder, pattern in [
            ("src", "*.py"),
            ("policies", "*.aspolicy"),
            ("tests", "*.py"),
            ("dashboard/src", "*"),
        ]
        for p in sorted((ROOT / folder).rglob(pattern))
        if p.is_file()
    }
    if results.get("source_files") and results["source_files"] != manifest:
        raise ValueError("SOURCE_CHANGED_SINCE_TEST_RUN: rerun tests before publishing")
    coverage = json.loads((ROOT / "artifacts/coverage.json").read_text())["totals"]
    generated = datetime.now(timezone.utc).isoformat()
    outcome = Counter(t["outcome"] for t in results["tests"])
    evidence = DOC / "evidence"
    evidence.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "artifacts/test-results.json", evidence / "runtime-tests.json")
    dump(evidence / "coverage-summary.json", coverage)
    for name in ("golden-report.json", "perf-cpu.json"):
        if (ROOT / "artifacts" / name).exists():
            shutil.copy2(ROOT / "artifacts" / name, evidence / name)
    tests = json.loads((DOC / "05-validation/test-cases.json").read_text())
    for case in tests:
        associated = [t for t in results["tests"] if case["id"] in t["cases"]]
        case["automated_tests"] = [t["test"] for t in associated]
        case["evidence"] = ["docs/evidence/runtime-tests.json"] if associated else []
        case["status"] = (
            "regression_covered"
            if associated and all(t["outcome"] == "passed" for t in associated)
            else "regression_failed"
            if associated
            else "not_run"
        )
        case["verification_note"] = (
            "该主题已有下列自动化回归证据；不表示原 TC 全部攻击变体或发布条件已签收。"
            if associated
            else "尚无实际运行证据。"
        )
        if case["id"] == "TC-35" and (evidence / "perf-cpu.json").exists():
            case["status"] = "measured_limited"
            case["evidence"].append("docs/evidence/perf-cpu.json")
            case["verification_note"] = (
                "4 CPU affinity/8 GiB 地址空间上限；ASCII 1/8 KiB、并发 1/4 的本地网关路径。不是独占资源或 HTTP/模型性能验收。"
            )
        if case["id"] in {"TC-22", "TC-37", "TC-41"} and associated:
            case["status"] = "partial"
            case["verification_note"] = {
                "TC-22": "原生导入、配对/缺失/无效结果验收合同已测试；AgentDojo/InjecAgent 实际运行另见公开评测报告，不表示效果达标。",
                "TC-37": "仅指标计算器算术测试；没有独立标注三态/良性 test。",
                "TC-41": "仅本机加密备份/恢复通过；无 Docker 干净部署证据。",
            }[case["id"]]
    dump(DOC / "05-validation/test-cases.json", tests)
    by_test = {t["id"]: t for t in tests}
    requirements = json.loads((DOC / "01-requirements/requirements.json").read_text())
    for r in requirements:
        linked = [by_test[t] for t in r["tests"]]
        r["evidence"] = sorted({e for t in linked for e in t["evidence"]})
        r["implementation_status"] = (
            "implemented_development_scope"
            if r["id"].startswith(("FR-", "SR-"))
            else "partial"
        )
        r["verification_status"] = "regression_covered" if r["evidence"] else "not_run"
        r["acceptance_signed_off"] = False
        if r["id"] == "FR-5.2":
            r["implementation_status"] = "partial"
            r["verification_status"] = "adapter_contract_only"
        if r["id"] in {"NFR-01", "G6"}:
            r["verification_status"] = "measured_limited"
        if r["id"] in {"NFR-02", "NFR-06"} or r["id"].startswith("GATE-"):
            r["implementation_status"] = "pending_acceptance"
            r["verification_status"] = "not_run"
        if r["id"] == "GATE-08":
            r["verification_status"] = "synthetic_regression_only"
        if r["id"] in {"FR-4.1", "FR-4.2", "FR-4.3", "SR-01", "SR-08", "G4", "G5"}:
            r["verification_status"] = "partial_scope_verified"
    dump(DOC / "01-requirements/requirements.json", requirements)
    backlog_path = DOC / "04-development/development_backlog.json"
    backlog = json.loads(backlog_path.read_text())
    backlog["status"] = "development_in_progress"
    for t in backlog["tasks"]:
        t["status"] = (
            "implemented_pending_acceptance"
            if t["id"]
            in {
                "A03",
                "A05",
                "B01",
                "B03",
                "B04",
                "B05",
                "B06",
                "B08",
                "C01",
                "C02",
                "C05",
            }
            else "in_progress"
        )
        if t["id"] in {"B07", "C04", "C07", "C08"}:
            t["status"] = "pending_external_evaluation"
    dump(backlog_path, backlog)
    cat = json.loads((DOC / "catalog.json").read_text())
    cat["runtime_implemented"] = True
    cat["runtime_stage"] = "development_preview_not_release_accepted"
    for d in cat["documents"]:
        if d["number"] == 18:
            d["status"] = "active_record"
            d["version"] = "1.1-dev"
    dump(DOC / "catalog.json", cat)
    dump(
        evidence / "source-manifest.json",
        {
            "generated_at": generated,
            "git_state": "uncommitted_development_tree",
            "files": manifest,
        },
    )
    report = {
        "name": "开发版工程验证",
        "kind": "development_verification",
        "generated_at": generated,
        "summary": {
            "pytest": dict(outcome),
            "pytest_exitstatus": results["exitstatus"],
            "statement_coverage_percent": coverage["percent_statements_covered"],
            "branch_coverage_percent": coverage["percent_branches_covered"],
            "test_topics_with_evidence": sum(bool(t["evidence"]) for t in tests),
            "release_accepted": False,
        },
        "limits": [
            "没有将自动化工程回归等同于 50 条需求正式签收。",
            "AgentDojo/InjecAgent 已接入原生评测，单列实际结果；ASB/MSB/Memory、独立 F1 和完整消融未验收。",
            "可选本地神经模型、Docker 干净部署、七天稳定性和独立安全评审未验收。",
            "外部 Agent 需要独立隔离；当前强制执行声明仅覆盖网关内工具及受限 Python。",
        ],
    }
    dump(evidence / "runtime-report.json", report)
    header = (
        "# 06 需求追踪矩阵 / RTM\n\n文档 ID：AS-DOC-06 ｜ 状态：`draft` ｜ 更新："
        + generated[:10]
        + "\n\n[返回导航](../README.md)\n\n13 条 FR、7 条 NFR、10 条 Gate、14 条 SR、6 项目标，共 50 项。状态由实际测试工件同步；regression_covered 表示有回归覆盖，不等于全部需求验收通过。所有人工签收仍为 false。设计与验收细节保存在 [机器可读矩阵](requirements.json)。\n\n| 需求 | 内容 | 任务 | 测试主题 | 实现 / 验证 |\n|---|---|---|---|---|\n"
    )
    rows = [
        "| "
        + r["id"]
        + " | "
        + r["title"]
        + " | "
        + ", ".join(r["tasks"])
        + " | "
        + ", ".join(r["tests"])
        + " | "
        + r["implementation_status"]
        + " / "
        + r["verification_status"]
        + " |"
        for r in requirements
    ]
    (DOC / "01-requirements/06-requirement-traceability-matrix.md").write_text(
        header
        + "\n".join(rows)
        + "\n\n[原始测试记录](../evidence/runtime-tests.json) · [报告与限制](../05-validation/18-test-benchmark-report.md)\n"
    )
    plan = DOC / "05-validation/16-test-plan.md"
    text = plan.read_text()
    text = text.replace(
        "当前只有文档与环境脚手架校验，没有业务测试实现；下面是42个有输入与判定依据的测试设计。",
        "已按以下主题实现自动化回归；实际覆盖、缺口及证据以 test-cases.json 和测试报告为准。设计主题的覆盖不等于全部验收通过。",
    )
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| TC-"):
            id = line.split("|")[1].strip()
            if id in by_test:
                parts = line.rsplit("|", 2)
                lines[i] = parts[0] + "| " + by_test[id]["status"] + " |"
    plan.write_text("\n".join(lines) + "\n")
    golden = (
        json.loads((evidence / "golden-report.json").read_text())
        if (evidence / "golden-report.json").exists()
        else None
    )
    perf = (
        json.loads((evidence / "perf-cpu.json").read_text())
        if (evidence / "perf-cpu.json").exists()
        else None
    )
    text = f"""# 18 测试与 Benchmark 报告

文档 ID：AS-DOC-18 ｜ 版本：1.1-dev ｜ 更新：{generated[:10]}  
Owner：C ｜ 状态：`active_record` ｜ 独立复核：尚未完成

[返回文档导航](../README.md)

## 已运行结果

Python 自动化测试：{outcome.get("passed", 0)} 通过、{outcome.get("failed", 0)} 失败、{outcome.get("skipped", 0)} 跳过；pytest 退出码 {results["exitstatus"]}。语句覆盖率 {coverage["percent_statements_covered"]:.2f}%，分支覆盖率 {coverage["percent_branches_covered"]:.2f}%。覆盖率只描述该测试运行，不替代安全正确性或发布签收。

[逐测试证据](../evidence/runtime-tests.json) · [覆盖率汇总](../evidence/coverage-summary.json) · [源码文件指纹](../evidence/source-manifest.json) · [运行摘要](../evidence/runtime-report.json)

包含三态实际副作用、审批并发/过期/取消/资源替换/版本漂移、未知结果不重试、SECRET 可信域外发、Memory 隔离、父子权限交集、MCP 真实 stdio 与 HTTP JSON-RPC、元数据漂移、沙箱宿主读/联网/fork 阻断、Git 对象变化、API 身份/Origin/验证错误脱敏、冷备份与恢复；原生 Hook 的只决策/审批/单次 claim/客户端回报、真实 HTTP 与进程桥接。

两个提醒来自 FastAPI/Starlette 测试客户端的上游弃用接口，未被隐藏为测试失败。默认神经模型关闭；没有推断或填充模型效果指标。

## 黄金功能回归

"""
    if golden:
        text += f"[20 条逐案例记录](../evidence/golden-report.json)：{golden['summary']['passed']}/{golden['summary']['cases']} 通过。样例参与开发，AL​LOW/ASK/BLOCK 与独立执行账本核对；不将该结果报告为独立 test 的 F1/ASR。\n\n"
    text += "## CPU 本地网关性能\n\n"
    if perf:
        text += "[性能原始报告](../evidence/perf-cpu.json)；4 CPU affinity、8 GiB 虚拟地址空间上限、禁用 GPU，ASCII 1/8 KiB，含扫描/归一化/决策/审计/文件工具及有界并发锁等待，不含 HTTP、模型、上游 Agent 或人工等待。共享主机资源不是独占容器验收。\n\n| 输入 | 并发 | 正式样本 | P95 ms | 错误 | 本配置阈值 |\n|---|---|---|---|---|---|\n"
        for c in perf["summary"]["configurations"]:
            text += f"| {c['input_bytes']} B | {c['concurrency']} | {c['n']} | {c['p95_ms']:.2f} | {c['errors']} | {'PASS' if c['pass'] else 'FAIL'} |\n"
        text += "\n每档另有 200 次预热。[首轮未达标记录](../evidence/perf-cpu-before.json)保留，优化使用事件序号索引、上下文头部查询和等价 ASCII 规范化快速路径。\n\n"
    text += """## 尚未完成的验收

- AgentDojo / InjecAgent 的全配置达标验收；ASB / MSB / Memory、AI-Infra-Guard 全量回归和四项消融。
- 独立分组标注 test 的检测 Macro-F1、三态 Macro-F1、良性效用与 ASR；当前只有指标计算器合同测试。
- 可选本地神经模型权重的正确性/性能、复杂语义路径 P95。
- 外部宿主 Agent 的独立强制隔离、干净 Docker/离线安装验证、七天稳定性及独立安全评审。

总判定：开发版可运行；正式发布验收未通过。未运行项目记 NOT_RUN，不记 0 或 PASS。完整设计主题覆盖及当前缺口见 [test-cases.json](test-cases.json)；生产可用性/效果目标仍按原 PRD 保留。
"""
    if (evidence / "live-mcp.json").exists() and (
        evidence / "ui-verification.json"
    ).exists():
        text += "\n## 运行服务与界面验收补充\n\n[真实 MCP 双传输证据](../evidence/live-mcp.json)与 [浏览器验收记录](../evidence/ui-verification.json)单列于 pytest 之外，以各自记录时间为准。服务在 5090 的 127.0.0.1:8080 运行，通过 SSH 隧道访问；界面已检查审批前完整参数、批准/拒绝、来源图与实测报告。\n"
    if (DOC / "05-validation/public-benchmark-report.md").exists():
        text += "\n## 公开基准实际运行\n\n[公开 Benchmark 实测与验收](public-benchmark-report.md)单独记录真实模型结果与未通过项；不得把本页工程回归通过率当作研究效果验收。\n"
    (DOC / "05-validation/18-test-benchmark-report.md").write_text(text)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
