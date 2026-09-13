#!/usr/bin/env python3
"""A count-based, plain-language view of the already audited history."""
import json

from plot_benchmark_history import BLUE, ROOT, plt, save, style


def main():
    data = json.loads((ROOT / "docs/evidence/benchmark-trends-20260913.json").read_text())
    rounds = data["rounds"]
    panels = [
        ("早期：修复对正常指令的误解", ["最初", "增加输入输出长度", "修复授权识别"], 97,
         [round(rounds[k]["arms"]["protected"]["benign_utility"] * 97) for k in ["A02", "A03", "A04"]],
         "同一个 7B 模型、同 97 个正常任务。\n加防护后，能做完的任务逐步增加。"),
        ("后来：修复清洗代码的错误", ["清洗 v1", "清洗 v2", "清洗 v4", "清洗 v5"], 16,
         [round(rounds[k]["arms"]["protected"]["attack_utility"] * 16) for k in ["A11", "A12", "A15", "A16"]],
         "同一个 9B 模型、同 16 个带攻击的任务。\nv1 有两次清洗错误，后面几版没有。"),
        ("最近：不再误删用户需要的验证码", ["修复前 · v4", "修复后 · v5"], 19,
         [data["matched19"][k] for k in ["previous", "current"]],
         "同一个 9B 模型、同 19 个正常任务。\n含已知失败案例，不能代表所有新任务。"),
    ]
    style()
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8))
    fig.subplots_adjust(left=.07, right=.98, top=.73, bottom=.27, wspace=.26)
    fig.suptitle("修改后，正常工作做完了几件？", x=.07, ha="left", y=.97, fontsize=23, fontweight="bold")
    fig.text(.07, .88, "每张图都在比较同一批任务；三张图的任务不同，不要跨图比较高低。", fontsize=13, color="#49566a")
    for ax, (title, labels, n, counts, note) in zip(axes, panels):
        assert all(0 <= count <= n for count in counts)
        ax.set_title(title, loc="left", fontsize=14, pad=16)
        ax.plot(range(len(labels)), counts, "o-", color=BLUE, linewidth=2.5, markersize=8)
        ax.set_xticks(range(len(labels)), labels, fontsize=10)
        ax.set_ylim(0, n * 1.20)
        ax.set_yticks([0, round(n/2), n])
        ax.set_ylabel("完成任务数（个）")
        ax.set_xlim(-.3, len(labels)-.7)
        ax.grid(axis="y", color="#dce2e8")
        ax.set_axisbelow(True)
        for x, count in enumerate(counts):
            ax.annotate(f"{count} / {n}", (x, count), xytext=(0, 11),
                        textcoords="offset points", ha="center", fontsize=13, color=BLUE)
        ax.text(0, -.26, note, transform=ax.transAxes, va="top", fontsize=11, color="#49566a")
    save(fig, "benchmark-plain-language")
    print("Rendered three within-cohort comparisons from audited data; no model calls.")


if __name__ == "__main__":
    main()
