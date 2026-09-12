> 项目：AgentSentry（意链盾，暂定名）

# 01 产品需求文档（PRD）

定义为什么做、做什么、不做什么，以及 MVP 的可验收结果。

| **Document ID**  | AS-PRD-001                                        |
|------------------|---------------------------------------------------|
| **Status**       | Draft for Design Review                           |
| **Version**      | v0.9                                              |
| **Owner**        | 产品/安全负责人（A）                              |
| **Reviewers**    | 系统负责人（A）、算法负责人（B）、评测负责人（C） |
| **Last Updated** | 2026-09-10                                        |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review        |

> **TL;DR** 构建一个部署在 LLM Agent 与 MCP/工具之间的运行时安全网关，对多源提示注入、意图偏离、工具滥用和敏感数据外流进行实时研判，并给出 ALLOW / ASK / BLOCK 三态决策和可重放的攻击溯源证据。

## 1. 背景与问题

LLM Agent 已具备文件、网络、代码执行、Git、MCP 和子 Agent 能力，安全边界从“模型输出内容”扩展到“真实副作用”。传统 WAF/EDR/DLP 对上下文中的间接提示注入、工具描述投毒、跨会话 Memory Poisoning 及跨 Agent 传播缺少语义理解。赛题要求形成检测—研判—阻断—溯源闭环。

| **产品定位** AgentSentry 不是单纯的 Prompt Injection 分类器，也不是离线漏洞扫描器；它是运行时 Agent Firewall / Agent EDR。AI-Infra-Guard 作为红队与回归测试组件接入，而非运行时强制执行点。 |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|

## 2. 目标用户与关键场景

| **Persona**      | **核心诉求**                         | **代表场景**                                |
|------------------|--------------------------------------|---------------------------------------------|
| Agent 平台研发   | 低侵入接入、安全默认值、可观察性     | Claude/Cursor 类 Agent 接 MCP/文件/网络工具 |
| 安全工程师 / SOC | 阻断高风险动作、解释原因、追溯攻击源 | 恶意 Issue 诱导读取密钥并外发               |
| 业务管理员       | 配置最小权限、审批高风险副作用       | 代码 Review 不允许自动 git.push             |
| 红队 / 测试      | 可复现攻击、回归验证防护效果         | AgentDojo / MSB / MPBench / 自建用例        |

## 3. Goals

- G1：覆盖 Direct / Indirect / Memory / MCP Description & Response 四类主要注入入口。

- G2：把用户自然语言任务解析成 Task Contract（Intent IR），把候选工具调用规范化成 Action IR，检测权限范围与副作用偏离。

- G3：对每个候选工具调用执行细粒度 Policy DSL，并输出 ALLOW / ASK / BLOCK。

- G4：实现 provenance + taint 传播，能够从攻击源重建到敏感 sink 的 DAG 和时间线。

- G5：在 Prompt Injection 漏检时，仍可由 Intent/Policy/Data-flow 后续防线阻断真实危险副作用。

- G6：支持 Docker Compose 一键部署，P0 场景可在单机 CPU + 可选本地小模型下运行。

## 4. Non-goals（MVP 不做）

- 不自研通用大模型或从零训练大型 Prompt Injection 模型。

- 不做完整企业 SIEM、SOAR、Kubernetes 多租户和复杂 RBAC 平台。

- 不承诺对所有闭源 Agent 获取完整 Chain-of-Thought；Plan 仅作为可选显式信号。

- 不依赖单一 LLM Judge 作为安全硬边界；硬阻断应有确定性策略或可验证的数据流依据。

- 不在线复现真实组织或第三方系统漏洞；CVE 演示仅在隔离沙箱、假凭据和 canary endpoint 中完成。

## 5. 核心用户旅程

```text
User 请求“检查 GitHub issue #123 并给出修改建议”
↓
Agent Hook 记录 User Intent 与来源
↓
Agent 调用 github.get_issue(123)
↓
MCP Tool Response 中出现间接注入 → Context Guard 标记 UNTRUSTED_EXTERNAL
↓
Agent 候选调用 fs.read(~/.ssh/id_rsa)
↓
Action IR = FILE_READ / CREDENTIAL
Intent IR = CODE_REVIEW / current_repo / no credential access
↓
Policy Engine = BLOCK
↓
Trace DAG：Issue #123 → Main Agent → fs.read → BLOCK
```

## 6. 功能需求

| **ID** | **P** | **需求**                   | **验收标准**                                                                |
|--------|-------|----------------------------|-----------------------------------------------------------------------------|
| FR-1.1 | P0    | Direct Injection 检测      | 支持用户输入扫描，输出 risk/type/evidence span/source；公开测试集可批量运行 |
| FR-1.2 | P0    | Indirect Injection ingress | Web/Document/Issue/MCP Response 至少 3 种真实来源经过统一 ContextChunk      |
| FR-1.3 | P1    | Memory Write/Read Guard    | 污染写入与后续读取均产生 SecurityEvent，并支持 BLOCK/QUARANTINE             |
| FR-2.1 | P0    | Intent IR                  | 结构化 goal/effects/scope/required side effects/forbidden effects           |
| FR-2.2 | P0    | Action IR                  | fs/net/exec/git/sub-agent 五类工具统一归一化                                |
| FR-2.3 | P0    | Alignment Engine           | 能解释 scope violation / effect escalation / missing authorization          |
| FR-3.1 | P0    | Policy DSL                 | 至少 10 个 predicate，支持文件/网络/exec/git/sub-agent                      |
| FR-3.2 | P0    | 三态决策                   | ALLOW/ASK/BLOCK 均有端到端场景；ASK approval 与参数绑定                     |
| FR-4.1 | P0    | Trace/Span                 | 100% P0 Tool Call 具有 trace_id/span_id/parent_span_id                      |
| FR-4.2 | P1    | Provenance/Taint           | SECRET/UNTRUSTED 至少两种标签跨 Agent/MCP 传播                              |
| FR-4.3 | P1    | DAG/Timeline               | 可视化攻击源、Agent、MCP、Tool、sink 和决策                                 |
| FR-5.1 | P1    | Normalization              | NFKC、零宽、confusable、大小写/全半角、空白重构                             |
| FR-5.2 | P1    | 红队回归                   | 接入 AI-Infra-Guard/公开 benchmark 进行回归                                 |

## 7. 非功能需求（SLO/SLA 目标）

| **类别**             | **MVP 目标**                     | **说明**                                         |
|----------------------|----------------------------------|--------------------------------------------------|
| Fast-path latency    | P95 ≤ 200 ms                     | 规则、缓存、小模型均命中时                       |
| Escalated path       | P95 ≤ 1.5 s                      | 需要语义模型/LLM 判别时，不含上游 Agent 本身耗时 |
| Trace coverage       | ≥ 99%                            | 受控 Demo Agent / MCP Proxy 范围                 |
| Decision determinism | 同一 input+policy version 可重放 | 记录 policy/model/version/hash                   |
| Audit retention      | 默认 7 天，可配置                | 敏感字段默认掩码/摘要化                          |
| Availability         | 单节点开发目标 99%               | 比赛环境不承诺企业级 HA                          |
| Security default     | 关键写/执行/外发 fail-closed     | 只读低风险可按租户配置 fail-open                 |

## 8. 成功指标

| **Metric**                     | **目标方向** | **MVP Gate**                       |
|--------------------------------|--------------|------------------------------------|
| Attack Success Rate            | ↓            | 防护后显著低于 no-defense baseline |
| Benign Task Success            | ↑/保持       | 相对 no-defense 降幅 ≤ 5pp         |
| Benign Block Rate              | ↓            | ≤ 5%（自建 hard benign 集）        |
| ALLOW/ASK/BLOCK Macro-F1       | ↑            | ≥ 0.85（自建验证集）               |
| Secret Exfiltration Prevention | ↑            | P0 canary 场景 100%                |
| Trace Source/Sink Accuracy     | ↑            | P0 黄金链路 100%                   |
| P95 Fast-path latency          | ↓            | ≤ 200 ms                           |

## 9. 里程碑与三人分工

| **阶段** | **A：系统/安全**                 | **B：算法/策略**                 | **C：评测/产品**                      | **Gate**          |
|----------|----------------------------------|----------------------------------|---------------------------------------|-------------------|
| W1-2     | MCP Proxy、event schema、adapter | Intent/Action IR、hard policy    | Demo Agent、UI skeleton、20 E2E cases | 黄金链路可跑      |
| W3-4     | Context Hook、provenance 基础    | Normalizer、Injection、Alignment | AgentDojo/InjecAgent、DAG UI          | 三态决策可演示    |
| W5-6     | Multi-MCP/Sub-Agent、性能        | Taint、Memory Guard、鲁棒性      | MSB/MPBench/Agent-SafetyBench         | benchmark 端到端  |
| W7-8     | 部署、审计、稳定性               | 阈值校准、ablation               | CVE sandbox、材料、演示               | 一键部署/一键回归 |

## 10. 风险与缓解

| **风险**                    | **影响**        | **缓解**                                                |
|-----------------------------|-----------------|---------------------------------------------------------|
| LLM 语义判别不稳定          | 误阻断/漏报     | 硬规则优先；模型只做风险信号；记录版本与阈值            |
| 闭源 Agent 无法拿完整上下文 | provenance 降级 | 提供 Hook 精确模式 + Proxy 兼容模式；字符 span 降级     |
| 策略过严                    | Utility 下降    | 加入 ASK；benign hard negatives；报告 over-block rate   |
| 三人开发时间不足            | 集成失败        | P0 优先：Proxy→IR→Policy→Trace；红队复用 AI-Infra-Guard |
| 日志泄密                    | 二次安全事件    | secret detection、字段掩码、最小 retention、访问控制    |

## Decision Log

| **ID** | **Decision**                                   | **Rationale**                                | **Status** |
|--------|------------------------------------------------|----------------------------------------------|------------|
| D-001  | 运行时形态采用 Agent Hook + MCP Proxy 双层     | Proxy 可强制执行，Hook 提供上下文/provenance | Accepted   |
| D-002  | Intent→Action 为硬主线，Plan 为可选信号        | 避免依赖不可见 CoT                           | Accepted   |
| D-003  | 三态决策而非二态 allow/deny                    | 减少过度阻断并满足赛题                       | Accepted   |
| D-004  | AI-Infra-Guard 用于红队/回归，不作为运行时内核 | 避免重复开发成熟扫描能力                     | Accepted   |

## Review Checklist

☐ P0/P1/P2 是否清晰，是否存在隐式范围扩张？

☐ 每个赛题能力是否有至少一个可自动验收 case？

☐ 成功指标是否同时覆盖 Security 与 Utility？

☐ 是否存在只能“报警”不能“阻断”的 P0 缺口？

☐ 三人分工是否能在 W2 前完成首次端到端集成？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/

说明：本文档采用可公开验证的大厂工程文档习惯，不声称复刻 OpenAI 或字节跳动未公开的内部模板、审批流或专有规范。
