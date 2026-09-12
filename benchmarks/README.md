# 评测入口

`make eval-smoke` 运行 20 条开发黄金回归，逐例核对三态与真实执行账本；不代表独立 test 的 F1/ASR。`make perf-cpu` 运行 4 CPU / 8 GiB 约束下固定 ASCII 1/8 KiB、并发 1/4，每档预热 200 + 正式 1000；不含 HTTP/模型推理。

## 原生公开基准

源码先用 `python3 scripts/fetch_benchmark_sources.py` 固定官方 GitHub commit 和下载归档 SHA-256，保存在 artifacts/upstream。5090 的 artifacts/benchmark-venv 与核心 .venv 分离；AgentDojo 源码以 editable 安装，启动器检查安装路径，不静默使用其他版本。

```bash
cd /root/autodl-tmp/AgentSentry
artifacts/benchmark-venv/bin/python benchmarks/run_agentdojo.py \
  --source artifacts/upstream/agentdojo-089ed468cf3e \
  --output artifacts/benchmarks/agentdojo/new-pilot-baseline \
  --configuration baseline --limit-per-suite 1
artifacts/benchmark-venv/bin/python benchmarks/run_injecagent.py \
  --source artifacts/upstream/InjecAgent-f19c9f2c79a4 \
  --output artifacts/benchmarks/injecagent/new-pilot-baseline \
  --configuration baseline --limit 12
```

同一清单另跑 `--configuration full`；完整运行去掉 limit。AgentDojo 的 `--mode benign` 只运行 97 个良性任务，不表示攻击集完成；默认 all 包含四场景 97 良性 + 949 important_instructions 攻击配对。InjecAgent base 为 1054 条，enhanced 是另一配置。目录中的 manifest 固定模型/seed/源码/策略/数据/计划 ID，配置变化禁止原地续跑；失败案例不自动删除重试。

默认只访问 localhost:18080，使用已部署本地模型；工具为上游模拟环境，不执行真实邮件、支付或设备控制。默认 1024 输出 token、temperature=0、15 步（AgentDojo）、无 HTTP 自动重试。截断、上下文超限和原生格式错误不算防御成功。InjecAgent 同时报模型提议与门控模拟执行 ASR；其原生判定器没有良性任务完成 oracle。

研究适配按工具语义表/名称归一化，未知副作用拒绝。它复用实际策略和 Intent 解析，但不是 Codex/Claude Code 终端适配；当前窄 Intent 模板和未知外发审批会明显损失跨领域良性效用。rules 是仅上下文规则隔离；no_context 关闭隔离仍保留标签，no_intent 去任务副作用约束但保留静态规则，no_taint 去标签。这些选项是候选实验，尚不能替代计划所需的完整四项消融和 ASK 人工审批实验。

## 配对验收

```bash
.venv/bin/python benchmarks/acceptance.py \
  --pair <baseline运行目录> <full运行目录> \
  --output docs/evidence/public-benchmark-report.json \
  --markdown docs/05-validation/public-benchmark-report.md
```

可重复 `--pair` 合并多个配对。检查模型、commit、源码/策略/runner、seed、计划 ID 一致性，报告 ASR 上下界、有效样例数、任务聚类配对 bootstrap CI 与效用损失。当前实现会保持 `NOT_ACCEPTED` 和退出码 1，因为完整公开基准、独立隐藏集、消融及产品验收证据尚未齐备；不能用 `|| true` 将该退出码宣称 PASS。研究结果与缺失项逐条报告。

`scripts/freeze_benchmark_environment.py` 保存源码归档、模型权重哈希、GPU 信息与依赖清单；不复制凭据或模型权重。初次封存目录是服务器 artifacts/benchmarks/frozen-qwen7b-v1。源码后续变化时旧结果仍引用此归档，不自动成为新版本验收。

`scripts/import_benchmark.py` 仍用于导入外部原生 JSONL 导出，不能代替原生模型运行。

[评测计划](../docs/05-validation/17-evaluation-benchmark-plan.md) · [公开实测](../docs/05-validation/public-benchmark-report.md) · [工程回归](../docs/05-validation/18-test-benchmark-report.md)
