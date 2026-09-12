> 项目：AgentSentry（意链盾，暂定名）

# 03 总体技术设计（System Design / RFC）

冻结运行时架构、关键控制流、组件职责、失败模式与方案取舍。

| **Document ID**  | AS-RFC-003                                        |
|------------------|---------------------------------------------------|
| **Status**       | Draft for Design Review                           |
| **Version**      | v0.9                                              |
| **Owner**        | 系统负责人（A）                                   |
| **Reviewers**    | 安全负责人（A）、算法负责人（B）、评测负责人（C） |
| **Last Updated** | 2026-09-10                                        |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review        |

> **TL;DR** 采用双层执行架构：Agent Hook 负责捕获任务意图、上下文来源与可选计划；MCP Runtime Proxy 作为强制执行点拦截候选工具调用。所有输入与动作被规范化为 ContextChunk / IntentIR / ActionIR，经 Injection、Alignment、Taint、Policy 合并后产生 ALLOW/ASK/BLOCK，并写入 Trace DAG。

## 1. Architecture Overview

```text
┌─────────────────────────────┐
User / Web / Memory ──>│ Agent Hook / Context Guard │
└────────────┬────────────────┘
│ ContextChunk + IntentIR
▼
┌──────────────────────┐
│ Security Decision │
│ - Injection │
│ - Alignment │
│ - Taint/Dataflow │
│ - Policy DSL │
└──────────┬───────────┘
│ ALLOW / ASK / BLOCK
▼
Agent ── tools/call ──> ┌──────────────────────┐
│ MCP Runtime Proxy │
└──────────┬───────────┘
│
┌─────────────┼──────────────┐
▼ ▼ ▼
fs net exec/git/MCP
All events ───────────────────────────────> Trace Store ──> DAG/Timeline
UI
AI-Infra-Guard / Benchmarks ─────────────> Regression Runner
```

## 2. Component Responsibilities

| **Component**     | **职责**                                                          | **P** | **Owner** |
|-------------------|-------------------------------------------------------------------|-------|-----------|
| Agent Hook        | 捕获 user task、context segments、可选 plan、sub-agent delegation | P0    | A         |
| Context Guard     | 来源标记、normalization、injection signal                         | P0    | B         |
| Intent Engine     | 生成/更新 Task Contract（IntentIR）                               | P0    | B         |
| Action Adapter    | fs/net/exec/git/delegate/MCP → ActionIR                           | P0    | A+B       |
| Alignment Engine  | scope/effect/side-effect 偏离检测                                 | P0    | B         |
| Taint Engine      | SECRET/UNTRUSTED 等标签传播                                       | P1    | B         |
| Policy Engine     | DSL evaluate + priority + decision reason                         | P0    | B         |
| Approval Service  | ASK 交互与 scoped token                                           | P0    | A+C       |
| MCP Proxy         | 执行前强制 gate、调用转发、响应 hook                              | P0    | A         |
| Trace Store       | SecurityEvent/Span 记录、replay                                   | P0    | A         |
| DAG Dashboard     | 攻击路径、时间线、证据、策略命中                                  | P1    | C         |
| Regression Runner | AI-Infra-Guard + benchmark 自动回归                               | P1    | C         |

## 3. End-to-End Control Flow

1.  Session 建立：生成 trace_id，Hook 记录 user_message 并创建 source_ref=user:\<msg_id\>。

2.  Intent Engine 生成 IntentIR；低置信度字段标记 unresolved，不凭空授权。

3.  Agent 获取外部内容：Context Guard 保存 raw/canonical 两种视图，标记 source/trust/evidence spans。

4.  Agent 产生候选 tool call：MCP Proxy 暂停转发并转换为 ActionIR。

5.  Decision Engine 并行计算 injection signal、alignment、taint flow、hard policy。

6.  若 hard block 命中，直接 BLOCK；否则按 policy priority 计算 ALLOW/ASK/BLOCK。

7.  ASK 进入 Approval Service；授权票据绑定 session/tool/args/target/policy version。

8.  ALLOW 后代理真实工具调用；工具响应再次经过 Context Guard 并继承 source_refs。

9.  每一步写 SecurityEvent/Span；Dashboard 根据 parent_span/source_refs 构建 DAG。

## 4. Decision Pipeline

```text
candidate_tool_call
│
├─ normalize_action() -> ActionIR
├─ resolve_intent() -> IntentIR
├─ align(IntentIR, ActionIR)
├─ propagate_taint(source_refs, arguments)
├─ evaluate_hard_rules()
└─ evaluate_semantic_rules()
│
┌────┴────┐
│ │
BLOCK score/policy
│
┌───────┼────────┐
│ │ │
ALLOW ASK BLOCK
│
approval token
│
execute
```

## 5. Intent Model

IntentIR 是任务授权合同，不等价于自然语言摘要。它只表达安全相关的“允许做什么、针对什么资源、允许哪些副作用、哪些未知”。未明确字段默认 UNKNOWN，不推断为 ALLOW。

```text
IntentIR {
goal: "code_review",
allowed_effects: [FILE_READ],
allowed_scopes: ["repo://current/**"],
required_effects: [],
side_effects: { git_push: UNKNOWN, network_egress: DENY },
sensitive_access: DENY,
unresolved: ["whether_user_wants_commit"]
}
```

## 6. Tool/Action Model

| **Effect** | **Risk**        | **示例**                           | **默认处理**             |
|------------|-----------------|------------------------------------|--------------------------|
| FILE_READ  | Low→Critical    | README / ~/.ssh/id_rsa             | 按 resource_class+scope  |
| FILE_WRITE | Medium→Critical | repo file / ~/.ssh/authorized_keys | 敏感路径 hard block      |
| NET_EGRESS | Medium→Critical | trusted API / unknown domain       | 结合 taint/domain        |
| EXEC       | High            | pytest / curl\|bash                | 命令语义与 allowlist     |
| GIT_PUSH   | High            | dev/main                           | 默认需要显式授权或 ASK   |
| DELEGATE   | Medium→High     | sub-agent task                     | 限制 secret 传播与 depth |

## 7. Caching & Performance

- Policy parsing、resource classification、trusted-domain lookup 做本地缓存。

- IntentIR 在 session 内增量更新，避免每次工具调用重新大模型解析。

- Fast-path：hard rule + cached Intent + deterministic adapter，不调用 LLM。

- Escalation：仅 unresolved/ambiguous 行为进入语义模型；语义模型超时后按 effect risk 决定 ASK/BLOCK。

## 8. Failure Modes & Degradation

| **故障**                         | **低风险读**                    | **写/执行/外发**                   | **记录**         |
|----------------------------------|---------------------------------|------------------------------------|------------------|
| Injection classifier unavailable | 继续 Intent/Policy              | 继续 hard policy，必要时 ASK/BLOCK | DEGRADED_MODEL   |
| Intent Engine unavailable        | 基于已有 Intent/cache；否则 ASK | 默认 ASK/BLOCK                     | DEGRADED_INTENT  |
| Policy Engine parse error        | 可配置 fail-open                | fail-closed                        | POLICY_ERROR     |
| Trace Store unavailable          | 本地 buffer                     | 执行决策不阻塞 ≤ buffer limit      | AUDIT_DEGRADED   |
| Approval UI unavailable          | 不影响 ALLOW                    | ASK 视为未批准                     | APPROVAL_TIMEOUT |

## 9. Alternatives Considered

| **方案**                            | **优点**           | **缺点**                                | **结论**                |
|-------------------------------------|--------------------|-----------------------------------------|-------------------------|
| 仅 Prompt Injection Classifier      | 快、简单           | 漏检后无第二道防线；无法覆盖 tool abuse | Reject                  |
| 仅 MCP Proxy                        | 强制执行点清晰     | 缺用户意图、context provenance          | Reject as sole layer    |
| 仅 Agent Hook                       | 上下文丰富         | 可能无法强制阻断第三方工具              | Reject as sole layer    |
| LLM Judge 决定所有动作              | 语义强             | 延迟/成本/不确定/可注入                 | Reject as hard boundary |
| Hook + Proxy + deterministic policy | 安全/解释/兼容平衡 | 工程复杂度较高                          | Accept                  |

## 10. Repository Layout

```text
agentsentry/
gateway/
mcp_proxy/
agent_hook/
context/
normalizer.py
injection.py
provenance.py
intent/
intent_ir.py
action_ir.py
alignment.py
policy/
parser.py
engine.py
approval.py
rules/
taint/
labels.py
propagation.py
trace/
event.py
span.py
dag.py
dashboard/
regression/
ai_infra_guard/
benchmarks/
tests/
docker-compose.yml
```

## 11. Rollout Strategy

- Phase 0 Shadow：只记录，不阻断；校准 benign false positives。

- Phase 1 Enforce Critical：仅 SECRET_EGRESS、sensitive write、dangerous exec 强阻断。

- Phase 2 Enable ASK：git.push、跨 scope write、未知外发进入审批。

- Phase 3 Full Policy：启用 tenant policy、memory guard、multi-agent taint。

## Decision Log

| **ID**  | **Decision**                                                  | **Rationale**                                 | **Status** |
|---------|---------------------------------------------------------------|-----------------------------------------------|------------|
| RFC-D01 | 采用 Hook + MCP Proxy                                         | 同时获得语义上下文和强制执行能力              | Accepted   |
| RFC-D02 | Policy 优先级 Hard Block \> Explicit Approval \> ASK \> ALLOW | 安全规则确定性                                | Accepted   |
| RFC-D03 | 所有 tool response 重新进入 Context Guard                     | 二阶注入/taint 可追踪                         | Accepted   |
| RFC-D04 | AI-Infra-Guard 放在 regression 层                             | 复用红队资产，不混入 production decision path | Accepted   |

## Review Checklist

☐ 是否存在组件职责重叠或循环依赖？

☐ 所有高风险 tool call 是否都经过单一 enforcement point？

☐ IntentIR 未知字段是否会被错误解释成允许？

☐ Response ingress 是否和 User ingress 同样被监控？

☐ Shadow→Critical→ASK rollout 是否支持快速回滚？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/
