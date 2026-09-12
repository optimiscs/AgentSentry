# vLLM 调优实时记录

状态：`TUNING_FINISHED_REVIEW_REQUIRED`。更新：2026-09-12T17:10:26.125823+00:00

固定 27B NVFP4 权重；依次等待 v4 配对及 task-plan-v1 小样结束。调优结束后恢复原服务配置。
本页仅记录服务性能试验，不代表 AgentSentry 的 benchmark 验收通过。

| 配置 | 状态 | 正确性检查 | 性能工件数 |
|---|---|---:|---:|
| eager-s2 | FAILED_REVIEW_REQUIRED | 5/5 | 0 |
| graph-s2 | FAILED_REVIEW_REQUIRED | 5/5 | 0 |
| graph-apc-s2 | FAILED_REVIEW_REQUIRED | 5/5 | 0 |
| graph-apc-s4 | FAILED_REVIEW_REQUIRED | 5/5 | 0 |

机器状态与原始工件路径见 [JSON](../evidence/vllm-tuning-report.json)。
16 条固定长度随机请求仅用于筛选配置；即使变快，仍需真实 Agent 工作负载和完整质量配对验证。
