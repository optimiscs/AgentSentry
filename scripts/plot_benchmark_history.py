#!/usr/bin/env python3
"""Rebuild audited history and research figures from preserved result artifacts.

Run with Python 3 + matplotlib. Never invokes a model or touches running jobs.
Historical sources are immutable; refreshed evidence is written separately.
"""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {}
OUT = ROOT / "docs/05-validation/figures"


def read(path):
    raw = (ROOT / path).read_bytes()
    SOURCES[path] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def normalize(row, dataset):
    m = row.get("metrics", row.get("strict_summary"))
    def field(*keys):
        return next((m[k] for k in keys if k in m), None)
    n = m["planned_cases"]
    valid = row.get("strict_valid_records", field("valid_cases", "completed_cases"))
    return dict(planned=n, valid=valid, unknown=n-valid,
                attack_n=field("attack_cases") if dataset == "agentdojo" else n,
                asr=field("simulated_execution_asr_all", "native_asr_all", "asr_all"),
                asr_upper=field("strict_execution_asr_upper_bound", "strict_asr_upper_bound", "asr_upper_bound"),
                benign_n=field("benign_cases"), benign_utility=field("benign_utility_all"),
                attack_utility=field("attack_utility_all"),
                complete_tools=field("all_normal_tools_executed_rate_all"))


def evidence():
    old = read("docs/evidence/evaluation-history-20260913.json")
    inventory = {r["run"]: r for r in old["inventory"]}
    assert len(inventory) == 44
    # Verify preserved raw metrics where available; absent raw files retain their
    # explicitly named historical strict-report source, never a fabricated path.
    for run, row in inventory.items():
        p = ROOT / run / "metrics.json"
        if p.exists() and "metrics_sha256" in row:
            assert hashlib.sha256(p.read_bytes()).hexdigest() == row["metrics_sha256"], run
    for stem in ["context-filter-v4-attack16", "context-filter-v5-dev35"]:
        for arm in ["baseline", "promptarmor_adapted"]:
            run = f"artifacts/benchmarks/agentdojo/agentdojo-lab3090-qwen35-9b-{stem}-{arm}-s0"
            m, config = read(run + "/metrics.json"), read(run + "/manifest.json")
            assert m["all_planned_records_present"] and m["recorded_cases"] == m["planned_cases"]
            inventory[run] = dict(run=run, metrics=m, configuration=config,
                                  metrics_sha256=SOURCES[run + "/metrics.json"],
                                  manifest_sha256=SOURCES[run + "/manifest.json"])
    specs = [
        ("agentdojo", ["pilot", "benign", "benign-32k", "benign-v3", "qwen27b-v4-pilot", "qwen27b-v4-benign", "task-plan-v1-pilot"]),
        ("agentdojo", ["agentdojo-lab3090-qwen35-9b-" + s for s in [
            "contract-v3-benign8", "contract-v4-benign8", "contract-v4-attack16", "context-filter-v1-dev24",
            "context-filter-v2-dev24", "context-filter-v2-benign97", "context-filter-v4-benign97",
            "context-filter-v4-attack16", "context-filter-v5-dev35"]]),
        ("injecagent", ["pilot-base", "native-base", "protocol-v2-pilot", "qwen27b-v4-pilot", "qwen27b-v4-base"]),
        ("asb", ["asb-local-v1-pilot", "asb-lab3090-qwen35-9b-protocol-v2", "asb-lab3090-qwen35-9b-contract-v3"]),
    ]
    rounds, counts = {}, dict(agentdojo=0, injecagent=0, asb=0)
    report_path = "docs/05-validation/evaluation-history-and-code-changes.md"
    report = (ROOT / report_path).read_text()
    SOURCES[report_path] = hashlib.sha256((ROOT / report_path).read_bytes()).hexdigest()
    for dataset, names in specs:
        for name in names:
            counts[dataset] += 1
            rid = dict(agentdojo="A", injecagent="I", asb="S")[dataset] + f"{counts[dataset]:02}"
            line = next(s for s in report.splitlines() if s.startswith(f"| {rid} ·"))
            r = dict(dataset=dataset, name=name, code_change=line.split("|")[2].strip(), arms={})
            for alias, arm in [("baseline", "baseline"), ("protected", "promptarmor_adapted" if "context-filter" in name else "full")]:
                run = f"artifacts/benchmarks/{dataset}/{name}-{arm}-s0"
                r["arms"][alias] = dict(run=run, **normalize(inventory[run], dataset))
            rounds[rid] = r
    assert len(rounds) == 24 and len(inventory) == 48
    mp = []
    for filename in ["mpbench-input-screen.json", "piguard-mpbench-input-screen.json", "lab3090-piguard-mpbench.json"]:
        rows = read("docs/evidence/" + filename)["groups"]
        r = next(r for r in rows if r["mode"] == "all_external_fields" and r["group"] == "all")
        assert r["valid"] == r["records"] == 6240 and r["unknown"] == 0
        assert abs(r["tpr"] - r["tp"] / (r["tp"] + r["fn"])) < 1e-12
        mp.append(dict(source=filename, **r))
    v5 = read("docs/evidence/context-filter-v5-evaluation.json")
    mode = read("docs/evidence/context-filter-mode-comparison.json")
    cpu = [read("docs/evidence/" + n)["summary"]["configurations"] for n in ["perf-cpu-before.json", "perf-cpu.json"]]
    live = read("artifacts/evaluation-history-refresh-20260913/live-progress.json")
    result = dict(status="DEVELOPMENT_HISTORY_NOT_PRODUCT_ACCEPTANCE", snapshot=live["observed_at_utc"],
                  completed_pairs=24, completed_arms=48, rounds=rounds,
                  inventory=list(inventory.values()), mpbench=mp,
                  fixed32={k: v["all_attempt_latency_seconds"] for k, v in mode["arms"].items()},
                  fixed43={k: v["latency_all_attempts_seconds"] for k, v in v5["diagnostic"]["arms"].items()},
                  matched19=dict(previous=v5["previous_v4_same_19_normal_tasks"]["utility_true"],
                                 current=round(rounds["A16"]["arms"]["protected"]["benign_utility"] * 19), n=19,
                                 selection="Retrospective development subset; not heldout"),
                  cpu=cpu, live_progress=live,
                  limitations=["Lines within comparable model/cohort families only; not causal ablations.",
                               "Unknown-as-success bounds are not statistical confidence intervals.",
                               "Input filtering is a reference without the full product action gate.",
                               "MPBench is binary input classification, not memory-poisoning ASR.",
                               "No ongoing run, scripted native client test or API preflight becomes a benchmark score."],
                  source_sha256=SOURCES)
    dest = ROOT / "docs/evidence/benchmark-trends-20260913.json"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


BLUE, ORANGE, RED, GREEN = "#2364AA", "#B8660D", "#C14343", "#208268"


def style():
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((f for f in ["PingFang SC", "Heiti SC", "Noto Sans CJK SC", "Arial Unicode MS"] if f in available), None)
    if chosen is None:
        raise RuntimeError("Install a Chinese font (Noto Sans CJK SC), then rebuild.")
    plt.rcParams.update({"font.family": chosen, "font.size": 11, "axes.titlesize": 14,
                         "axes.titleweight": "bold", "axes.unicode_minus": False,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white",
                         "pdf.fonttype": 42, "svg.fonttype": "path"})


def setup(ax, title, labels, note, ylim=(-4, 105), ylabel="比例（%）"):
    ax.set_title(title, loc="left", pad=17)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_xlim(-.3, len(labels)-.7)
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#dce2e8", linewidth=.7)
    ax.set_axisbelow(True)
    ax.text(0, -.25, note, transform=ax.transAxes, fontsize=10, color="#49566a", va="top")


def series(ax, xs, ys, label, color, groups=None, dashed=False, marker="o", annotate=False):
    groups = groups or [list(range(len(xs)))]
    for i, group in enumerate(groups):
        ax.plot([xs[j] for j in group], [ys[j] for j in group],
                label=label if i == 0 else None, color=color, marker=marker,
                markersize=7 if not dashed else 4, linewidth=2,
                linestyle="--" if dashed else "-")
    if annotate:
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=10, color=color)


def save(fig, name):
    OUT.mkdir(exist_ok=True, parents=True)
    for ext in ["png", "svg", "pdf"]:
        path = OUT / f"{name}.{ext}"
        fig.savefig(path, dpi=160, bbox_inches="tight")
        if ext == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


def draw(d):
    style()
    rounds = d["rounds"]
    def values(ids, arm, metric):
        return [100 * rounds[k]["arms"][arm][metric] for k in ids]
    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.subplots_adjust(top=.89, bottom=.13, hspace=.65, wspace=.23)
    fig.suptitle("AgentSentry · 已完成评估的指标变化", x=.075, ha="left", fontsize=23, fontweight="bold", y=.982)
    fig.text(.075, .947, "24 组模型配对 + 输入检测诊断  |  不同模型断开连线；同轮基线与防护分别保留  |  2026-09-13", fontsize=12, color="#49566a")
    ax=axes[0,0]; ids=["A02","A03","A04","A06","A13","A14"]; groups=[[0,1,2],[3],[4,5]]
    setup(ax,"A  正常任务完成率 ↑ · AgentDojo / 97 条",["7B\n初版","7B\n32K","7B\n授权修复","27B\n模板","9B\n清洗 v2","9B\n清洗 v4"],"断线处换模型/方案。另在同一组 19 条开发正常任务上，\nv4 → v5 完成 17 → 19 条；不能接到 97 条曲线上。")
    series(ax,range(6),values(ids,"baseline","benign_utility"),"无防护",ORANGE,groups,marker="s")
    series(ax,range(6),values(ids,"protected","benign_utility"),"对应防护/清洗参考",BLUE,groups,annotate=True)
    ax.legend(loc="lower right",fontsize=10)
    labels=["契约 v4","清洗 v1","清洗 v2","清洗 v4","清洗 v5"]
    ids=["A10","A11","A12","A15","A16"]; groups=[[0],[1,2,3,4]]
    ax=axes[0,1]
    setup(ax,"B  攻击成功率 ASR ↓ · 同 16 个攻击",labels,"红虚线：把未知也算攻击成功的保守上界，非置信区间。\n契约门控与清洗参考分开；小样尚不足以验收。",(-2,30))
    series(ax,range(5),values(ids,"baseline","asr"),"无防护：已知成功",ORANGE,groups,marker="s")
    series(ax,range(5),values(ids,"protected","asr"),"对应防护：已知成功",BLUE,groups)
    series(ax,range(5),values(ids,"protected","asr_upper"),"防护保守上界",RED,groups,dashed=True,annotate=True)
    ax.legend(loc="upper right",fontsize=10)
    ax=axes[1,0]
    setup(ax,"C  攻击下的正常任务完成率 ↑ · 同 16 个攻击",labels,"清洗 v1 → v2：修复转义定位，12/16 → 14/16。\nv4、v5 维持 14/16；清洗参考未启用产品动作门控。")
    series(ax,range(5),values(ids,"baseline","attack_utility"),"无防护",ORANGE,groups,marker="s")
    series(ax,range(5),values(ids,"protected","attack_utility"),"对应防护/清洗参考",BLUE,groups,annotate=True)
    ax.legend(loc="lower right",fontsize=10)
    ax=axes[1,1]; ids=["I02","I05"]
    setup(ax,"D  攻击结果 ↓ · InjecAgent / 1054 条",["7B · I02","27B · I05"],"换了模型和代码，因此两点不连线。防护已知执行均为 0，\n但未知从 465 → 52 条；该数据没有正常任务完成指标。",(-4,80))
    for arm,col,label in [("baseline",ORANGE,"无防护"),("protected",BLUE,"防护")]:
        xs=[i + (-.035 if arm == "baseline" else .035) for i in range(2)]
        series(ax,xs,values(ids,arm,"asr"),label+"：已知成功",col,[[0],[1]],marker="s")
        series(ax,xs,values(ids,arm,"asr_upper"),label+"：保守上界",col,[[0],[1]],dashed=True,marker="^")
    ax.text(.36,.38,"7B → 27B\n基线已知 ASR：17.55% → 0.76%\n防护保守上界：44.12% → 4.93%",transform=ax.transAxes,fontsize=10,color="#49566a",linespacing=1.7)
    ax.legend(loc="upper right",fontsize=9)
    ax=axes[2,0]; ids=["S01","S02","S03"]; groups=[[0],[1,2]]
    setup(ax,"E  ASB / 40 条 · 拦住攻击仍不等于任务可用",["27B · 初版","9B · 协议 v2","9B · 契约 v3"],"防护完整正常工具执行率始终为 0%。v2 → v3 有效结果\n38 → 40，仍未完成正常任务；40 条不代表全量 mixed。",(-4,65))
    series(ax,range(3),values(ids,"baseline","asr"),"无防护：已知 ASR",ORANGE,groups,marker="s")
    series(ax,range(3),values(ids,"protected","asr_upper"),"防护 ASR 保守上界",RED,groups,dashed=True,annotate=True)
    series(ax,range(3),values(ids,"protected","complete_tools"),"防护：完整任务效用",BLUE,groups)
    ax.legend(loc="upper right",fontsize=10)
    ax=axes[2,1]
    setup(ax,"F  MPBench / 6240 条 · 仅输入二分类",["规则","PIGuard\n分窗 / CPU","PIGuard\n完整输入 / GPU"],"PIGuard 是第三方模型；分窗 → 完整输入少误报 203 条、\n少检出 14 条。不是记忆投毒 ASR，也不是三态 Macro-F1。",(-4,70))
    for key,col,label in [("tpr",BLUE,"攻击检出率 ↑"),("fpr",RED,"正常误报率 ↓"),("binary_macro_f1",GREEN,"二分类 Macro-F1 × 100 ↑")]:
        ys=[100*r[key] for r in d["mpbench"]]
        series(ax,range(3),ys,label,col)
        for i,y in enumerate(ys):
            offset=(12,-11) if i==0 and key=="fpr" else (0,9)
            ax.annotate(f"{y:.1f}",(i,y),xytext=offset,textcoords="offset points",ha="center",fontsize=10,color=col)
    ax.legend(loc="upper left",fontsize=9)
    fig.text(.075,.015,"所有分母包含错误/未知；正在运行的全量对照、脚本模型的客户端检查、DeepSeek 接口连通性均不作为最终分数入图。",fontsize=11,color="#49566a")
    save(fig,"benchmark-quality-history")
    fig, axes = plt.subplots(1,3,figsize=(16,5.3))
    fig.subplots_adjust(top=.74,bottom=.28,wspace=.29)
    fig.suptitle("速度变化 · 相同输入和统计口径下比较",x=.075,ha="left",y=.97,fontsize=22,fontweight="bold")
    fig.text(.075,.89,"包含所有尝试的耗时；默认关闭思考。局部清洗延迟不是完整 Agent 任务耗时。",fontsize=12,color="#49566a")
    ax=axes[0]
    setup(ax,"G  本地网关 · 8 KiB / 并发 4",["最初","最近测量"],"审计索引/查询/ASCII 路径优化；每档 1000 次。\n包含排队，不含 HTTP/模型；共享主机。",(0,370),"P95（毫秒）")
    ys=[next(r["p95_ms"] for r in c if r["input_bytes"]==8192 and r["concurrency"]==4) for c in d["cpu"]]
    series(ax,range(2),ys,"P95",BLUE,annotate=True)
    ax.axhline(200,color=RED,linestyle="--",linewidth=1.3,label="200 ms 目标")
    ax.legend(loc="upper right",fontsize=10)
    for ax,key,n,labels,title in [(axes[1],"fixed32",32,["v3 两阶段","v4 合并调用"],"H  清洗耗时 · 固定 32 条"),(axes[2],"fixed43",43,["v4","v5 验证码修复"],"I  清洗耗时 · 固定 43 条")]:
        rows=[d[key][k] for k in (["two_stage_nonthinking","joint_nonthinking"] if n==32 else ["v4","v5"])]
        note="同输入/同模型；调用 56 → 32 次。\n平均降低 39.7%，P95 降低 56.6%。" if n==32 else "同输入/同模型；两组均 43 条有效。\n平均降低 4.9%，但 P95 增加 5.3%。"
        setup(ax,title,labels,note,(0,18 if n==32 else 8),"每条输入耗时（秒）")
        for metric,col,label in [("mean",BLUE,"平均"),("p95_nearest_rank",RED,"P95")]:
            series(ax,range(2),[r[metric] for r in rows],label,col,annotate=True)
        ax.legend(loc="lower center" if n==43 else "upper right",fontsize=10)
    save(fig,"benchmark-latency-history")


if __name__ == "__main__":
    data = evidence()
    draw(data)
    print("Verified 24 pairs / 48 arms; wrote evidence and 6 PNG/SVG/PDF figure files.")
