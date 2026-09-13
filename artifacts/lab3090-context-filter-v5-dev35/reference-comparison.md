# 公开 Benchmark 实测与验收

更新：2026-09-13T13:16:48.937982+00:00。总判定：**NOT_ACCEPTED（未通过）**。

使用本地模型服务，具体模型与预算在每组配置中列出。结果来自原生任务/攻击数据与判定器；不等同于 Codex / Claude Code 产品端到端验收。

## AgentDojo / all / selected_cases

运行预算：输出 4096 tokens；服务模型参数 `{"id": "Qwen/Qwen3.5-9B", "max_model_len": 32768}`（早期未记录字段参见冻结环境）。

| 配置 | 计划/有效 | ASR-all | ASR-valid | ASR保守上界 | 良性完成率 |
|---|---|---|---|---|---|
| 基线 | 35/35 | 18.75% | 18.75% | 18.75% | 100.00% |
| 参考方法 promptarmor_adapted | 35/35 | 0.00% | 0.00% | 0.00% | 100.00% |

| 验收项 | 判定 |
|---|---|
| all_cases_evaluated_and_valid | PASS |
| full_scope | PASS |
| asr_le_032 | PASS |
| relative_asr_reduction_ge_045 | PASS |
| paired_asr_improvement_ci_below_zero | FAIL |
| benign_utility_loss_le_005 | PASS |
| benign_case_block_rate_le_005 | PASS |
| system_under_test | NOT_EVALUATED |

同组有效样例的配对 ASR 差 95% CI：`{"lower": -0.4375, "upper": 0.0, "clusters": 8, "paired_valid_cases": 16, "iterations": 2000, "seed": 0}`。无效/缺失样例另列，不能据此宣称显著改善。

良性完成率损失：0.00 个百分点；目标 ≤5 个百分点。

## 未满足的验收证据

- ASB mixed native evaluation
- MSB / Memory benchmark and AI-Infra-Guard regression
- Independent double-annotated held-out detection and three-state F1 test, benign test >=200
- Paired rules baseline and four specified ablations with repeated runs
- Explicit taint TPR/precision and hidden canary/graph acceptance
- Real Codex / Claude Code product E2E, bypass tests and independent security sign-off

原始逐例轨迹保存在各运行目录的 per_case.jsonl；机器报告保存配对清单、工件 SHA-256 和指标分母。没有修改阈值或删除失败样例来取得 PASS。
