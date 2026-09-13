# 精选中间产物

本目录提交精选中间产物；初次交接快照见 [repository-manifest.json](repository-manifest.json)，后续批次使用各自清单与文档证据，原有 `.gitignore` 继续忽略其他运行产物。清单包含文件的 SHA-256 和大小。

2026-09-13 新增 [归因成本审计批次](lab3090-causal-budget-v1/artifact-manifest.json)：脚本运行记录、token 统计、环境来源、重复审计，以及已完成的 35 条 AgentDojo 模拟开发轨迹压缩包（附许可）。原始输入哈希与旧运行一致，包含模拟任务内容及模型回答，便于复核；不包含真实用户邮件或生产凭证。[范围与复现说明](../docs/05-validation/causal-proxy-budget-and-baseline-review.md)

新增 [MPBench 阶段准备批次](lab3090-mpbench-lifecycle-v1/artifact-manifest.json)：六文件源码快照、6240 条阶段输入的哈希清单、41 项检查、四条公开数据字段示例与重复审计。完整数据留在 Lab3090；本批次没有 Agent、持久记忆或语义裁判预测。[范围说明](../docs/05-validation/mpbench-lifecycle-preparation.md)

- `benchmarks/*/*/{manifest,metrics}.json`：本地已回收的场景清单、配置、统计和状态。包含历史及小样，须按各自scope解读。
- `benchmarks/frozen-*/source.tar.gz`及environment.json：相应运行使用的第一方源码和环境记录。
- `development/*/source-candidate.tar.gz`、候选清单和补丁：隔离研究版本的源码。`asb-protocol-v2`只通过部分工程检查，没有新模型结果。
- vLLM运行计划、固定执行器、采样预检和PID身份：记录如何运行与核验进程；PID文件是历史证据，不能直接据其对当前进程发送信号。
- PIGuard评分报告、原评分源码与协议回归：保留分窗诊断及其评分口径；后续 Lab3090 完整字段结果见 [评分证据](../docs/evidence/lab3090-piguard-mpbench.json)。
- 重复审计与task-plan小样验收报告：记录可复现工程统计及失败结论。

这些文件不包含模型权重、第三方完整数据集、虚拟环境、运行数据库或私钥/访问令牌。初次交接时部分远端原始结果因 SSH 不可达未回收；后续明确列出的模拟开发样本可含逐例原文，不能据此推断所有运行均已完整归档。指标和清单不能替代完整逐例记录，当前 benchmark 仍未验收。

需要查看某个候选全部源码时，先核对清单中的归档哈希，再解压到新的空目录；不要覆盖已有开发目录。例如：

```bash
mkdir -p /tmp/agentsentry-task-plan-review
tar -xzf artifacts/development/task-plan-v1/source-candidate.tar.gz \
  -C /tmp/agentsentry-task-plan-review
```

这不会启动服务或实验。服务器专用路径和已冻结的模型配置需要在相应环境中复现，不能把它们当成任意机器通用的启动命令。暂停请求的确认状态见[交接记录](../docs/04-development/experiment-pause-and-handoff.md)。
