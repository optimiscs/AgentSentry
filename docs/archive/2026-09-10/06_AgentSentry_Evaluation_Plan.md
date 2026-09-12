> 项目：AgentSentry（意链盾，暂定名）

# 06 评测与 Benchmark 计划（Evaluation Plan）

定义每项赛题能力如何被公开数据集、自建数据、指标和消融实验验证。

| **Document ID**  | AS-EVAL-006                                |
|------------------|--------------------------------------------|
| **Status**       | Draft for Design Review                    |
| **Version**      | v0.9                                       |
| **Owner**        | 评测负责人（C）                            |
| **Reviewers**    | 算法负责人（B）、系统负责人（A）           |
| **Last Updated** | 2026-09-10                                 |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review |

> **TL;DR** 采用“公开 benchmark 验证可比性 + 自建 AgentSentryBench 补齐赛题特有能力”的矩阵。公开集用于 Direct/Indirect/MCP/Memory/Tool/Multi-Agent；自建集专门评 Intent→Action alignment、ALLOW/ASK/BLOCK 和 provenance DAG。Security 与 Utility 必须同时报告。

## 1. Evaluation Questions

- Q1：Prompt Injection detector 是否能识别多源/混淆攻击，而不过度误报 benign 内容？

- Q2：运行时防护能否降低真实 Agent Attack Success Rate？

- Q3：Intent/Action Alignment 是否能识别越权而非只靠关键词？

- Q4：ALLOW/ASK/BLOCK 是否比纯 allow/deny 更好地平衡安全与任务成功率？

- Q5：Injection 漏检后，Policy/Taint 是否仍可阻断真实危险副作用？

- Q6：DAG 是否准确恢复攻击源、传播节点和 sink？

- Q7：引入防护后的 P95 延迟和吞吐是否可接受？

## 2. Benchmark Matrix

| **能力**                        | **公开 Benchmark**                                   | **主要指标**                     | **备注**                  |
|---------------------------------|------------------------------------------------------|----------------------------------|---------------------------|
| Direct / multilingual injection | CyberSecEval Prompt Injection                        | ASR, Recall, FPR/FRR             | detector-level            |
| Indirect injection E2E          | AgentDojo                                            | Attack ASR, Utility              | 主 E2E benchmark          |
| Indirect/tool abuse             | InjecAgent / AgentDyn                                | ASR, task success                | 补充复杂/OOD              |
| MCP supply-chain/injection      | MCP Security Bench (MSB)                             | MCP attack ASR                   | 赛题高度匹配              |
| Memory poisoning                | MPBench                                              | write/retrieve/consequential ASR | 跨会话                    |
| Tool safety                     | Agent-SafetyBench / ToolEmu                          | unsafe action rate, helpfulness  | 三态标签派生              |
| Multi-Agent cascading           | ACIArena                                             | cascading ASR                    | 用于多 Agent + trace 派生 |
| Obfuscation stress              | TensorTrust / WAInjectBench / AI-Infra-Guard attacks | robust recall/FPR                | 专项 stress               |

## 3. AgentSentryBench（自建）

目标不是重复造 Prompt Injection，而是补齐公开 benchmark 缺少的三类标注：Intent→Action alignment、三态决策、Trace Ground Truth。建议 1,200–2,000 cases。

| **Subset**             | **规模建议** | **构造**                                 | **GT**                                |
|------------------------|--------------|------------------------------------------|---------------------------------------|
| Intent-Action          | 600          | AgentDojo/ToolEmu/真实业务任务派生       | allowed scope/effect + deviation type |
| Three-State            | 450          | 每个 base task 构造 ALLOW/ASK/BLOCK 变体 | decision + reason                     |
| Trace                  | 200          | 受控 multi-agent/MCP 场景                | source/node/edge/sink/span            |
| Robustness Hard Benign | 300          | 包含“讨论攻击文本但不执行”等             | benign / expected allow               |

## 4. Metrics

| **层**       | **指标**                                             | **解释**                        |
|--------------|------------------------------------------------------|---------------------------------|
| Detector     | Precision / Recall / Macro-F1 / FPR                  | 文本/上下文识别                 |
| Attack       | Attack Success Rate (ASR)                            | 真正危险目标是否实现            |
| Utility      | Benign Task Success                                  | 安全防护是否破坏正常任务        |
| Over-defense | Benign Block Rate / Unnecessary Ask Rate             | 过度阻断和过度询问              |
| Three-state  | Macro-F1 / per-class recall                          | ALLOW/ASK/BLOCK                 |
| Alignment    | Deviation Recall / FPR / Type-F1                     | scope/effect/sensitive mismatch |
| Dataflow     | Exfiltration Prevention Rate                         | secret→sink 阻断                |
| Memory       | Write / Retrieval / Consequential ASR                | 跨阶段                          |
| Trace        | Source Acc / Node-F1 / Edge-F1 / Sink Acc / Span IoU | 溯源正确性                      |
| System       | P50/P95 latency / throughput / CPU/RAM               | 工程性能                        |

## 5. Baselines

| **Baseline**                                       | **目的**                                 |
|----------------------------------------------------|------------------------------------------|
| No Defense                                         | 攻击成功率与任务成功率上界/下界          |
| Injection-only                                     | 证明单分类器不足                         |
| Hard Rules-only                                    | 证明语义 Intent/ASK 的价值               |
| Intent+Policy without Taint                        | 测 Dataflow 增益                         |
| Full AgentSentry                                   | 最终系统                                 |
| Optional: AI-Infra-Guard red-team discovered cases | 验证外部扫描发现的漏洞能否在运行时被阻断 |

## 6. Core Ablations

| **Ablation**                           | **想回答的问题**                               |
|----------------------------------------|------------------------------------------------|
| \- Normalization                       | Unicode/zero-width/encoding 对 detector 的影响 |
| \- Intent Alignment                    | 是否退化成黑名单防御                           |
| \- ASK (force binary)                  | 三态是否降低 benign block                      |
| \- Taint                               | Injection 漏检后 secret egress 是否增加        |
| \- Provenance                          | 对阻断本身影响小，但溯源指标是否显著下降       |
| LLM semantic judge → small model/rules | 成本/延迟/效果权衡                             |

## 7. Statistical Protocol

- 固定模型、temperature、tool environment 和 policy version；记录 random seed。

- Agent benchmark 每个 case 至少 1 次 deterministic run；若模型存在采样，再做 3-run robustness。

- 报告样本数、95% bootstrap CI（ASR/utility 等比例指标）。

- 所有 threshold 只在 dev set 调整，test set 一次性报告。

- Security 与 Utility 指标必须并列，禁止只报“拦截率”。

## 8. Acceptance Gates

| **Gate** | **要求**                                                      |
|----------|---------------------------------------------------------------|
| G-E1     | 至少 1 个公开 E2E benchmark 显著降低 ASR                      |
| G-E2     | Benign Task Success 相比 no-defense 降幅 ≤ 5pp                |
| G-E3     | Three-State Macro-F1 ≥ 0.85，自建 hard benign block rate ≤ 5% |
| G-E4     | Canary secret exfiltration P0 cases 阻断率 100%               |
| G-E5     | Trace 黄金集 source/sink accuracy 100%，Node/Edge-F1 ≥ 0.9    |
| G-E6     | Fast-path P95 ≤ 200 ms（指定硬件）                            |

## 9. Reporting Template

```text
Table A: Security vs Utility
System | ASR↓ | Benign Success↑ | Block Rate↓ | Ask Rate
Table B: Capability Breakdown
Direct | Indirect | MCP | Memory | Tool Abuse | Multi-Agent
Table C: Trace
Source Acc | Node-F1 | Edge-F1 | Sink Acc | Span IoU
Table D: Performance
P50 | P95 | throughput | CPU | RAM
```

## 10. Reproducibility

- 保存 benchmark commit/hash、container image digest、model ID/version、policy hash。

- 所有报告数字对应机器可读 JSON result。

- 提供 one-command regression：make eval-smoke / make eval-full。

- CVE/攻击演示只使用隔离环境与 canary secret，不访问真实敏感目标。

## Review Checklist

☐ 每项赛题能力是否至少有一个量化指标？

☐ 是否同时测 Security 和 Utility？

☐ 自建数据是否只补公开 benchmark 的空缺，而非自说自话？

☐ test threshold 是否避免在 test set 上调参？

☐ 所有结果是否可由 commit+policy+model 版本重放？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/

说明：本文档采用可公开验证的大厂工程文档习惯，不声称复刻 OpenAI 或字节跳动未公开的内部模板、审批流或专有规范。
