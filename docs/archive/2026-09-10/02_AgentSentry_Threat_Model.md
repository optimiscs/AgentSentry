> 项目：AgentSentry（意链盾，暂定名）

# 02 威胁建模文档（Threat Model）

明确资产、攻击者、信任边界、攻击路径、安全不变量和剩余风险。

| **Document ID**  | AS-SEC-002                                        |
|------------------|---------------------------------------------------|
| **Status**       | Draft for Design Review                           |
| **Version**      | v0.9                                              |
| **Owner**        | 安全负责人（A）                                   |
| **Reviewers**    | 系统负责人（A）、算法负责人（B）、评测负责人（C） |
| **Last Updated** | 2026-09-10                                        |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review        |

> **TL;DR** 安全边界以“用户授权意图 + 最小权限 + 数据来源与流向”为核心。所有外部内容默认不可信；MCP server/tool metadata 也不构成信任依据。高风险副作用必须在执行前经过可审计的策略决策。

## 1. Scope

- In scope：用户消息、外部网页/文档/邮件/Issue、代码文本、MCP Tool Description/Response、Memory、Main/Sub-Agent、fs/net/exec/git/delegate 工具。

- Out of scope：模型权重投毒、GPU 驱动级攻击、宿主机内核漏洞、未接入代理且完全绕过系统的旁路工具。

- 部署假设：AgentSentry 能位于受控 Agent 与 MCP/关键工具之间，或至少通过 Hook 获取候选 tool call。

## 2. Protected Assets

| **Asset**              | **机密性** | **完整性** | **可用性** | **示例**                        |
|------------------------|------------|------------|------------|---------------------------------|
| Secrets/Credentials    | Critical   | High       | Medium     | ~/.ssh、~/.aws、API key、env    |
| Source Code / Repo     | High       | High       | High       | 企业代码、Git history           |
| User Intent / Approval | High       | Critical   | High       | 当前任务范围、ASK 批准票据      |
| Agent Memory           | High       | High       | Medium     | 长期偏好、业务事实、流程        |
| Tool Capability        | Medium     | Critical   | High       | exec/fs/net/git/MCP permissions |
| Trace/Audit Evidence   | High       | Critical   | High       | SecurityEvent、DAG、决策原因    |

## 3. Trust Boundaries

```text
[Untrusted]
User / Web / PDF / Email / Issue / Code Comment / MCP Description / MCP
Response / Memory-derived content
│
▼ TB-1 Context Ingress
[AgentSentry Context Guard]
│
▼
[Agent Runtime] ── TB-2 Delegation ──> [Sub-Agent]
│
▼ TB-3 Tool Call
[MCP Runtime Proxy / Policy Engine]
│
├──> Filesystem
├──> Network
├──> Exec
├──> Git
└──> Third-party MCP
[Trusted only by explicit policy]
Policy config / approval service / audit store / admin identity
```

## 4. Attacker Models

| **Actor**       | **能力**                              | **目标**                           |
|-----------------|---------------------------------------|------------------------------------|
| 恶意用户        | 直接输入任意 Prompt、诱导高权限操作   | 越权、数据泄露、执行危险命令       |
| 外部内容攻击者  | 控制网页/Issue/邮件/文档内容          | 间接 Prompt Injection              |
| 恶意 MCP Server | 控制 tool description/schema/response | tool poisoning、rug pull、数据外泄 |
| Memory 污染者   | 向可持久化 memory 写入内容            | 跨会话触发危险行为                 |
| 被攻陷子 Agent  | 向同层/上游传播恶意消息               | cascading injection/exfiltration   |
| 误配置管理员    | 配置过宽策略或信任域                  | 无意扩大权限面                     |

## 5. 安全不变量（Security Invariants）

| **ID** | **Invariant**                                                            | **Enforcement**                        |
|--------|--------------------------------------------------------------------------|----------------------------------------|
| INV-01 | 未明确授权的 CREDENTIAL/SECRET 不得流向 UNTRUSTED_NETWORK                | Taint + egress hard rule               |
| INV-02 | 外部内容不得天然提升权限；source trust 不能因进入 Agent context 自动升级 | Provenance labels                      |
| INV-03 | 高风险副作用必须在执行前得到 ALLOW/ASK/BLOCK 结论                        | MCP Proxy enforcement                  |
| INV-04 | ASK 批准必须绑定 session/tool/normalized args/target，禁止 scope drift   | Approval token hash                    |
| INV-05 | 策略/模型/规则异常时，Critical effect 不能默认放行                       | Selective fail-closed                  |
| INV-06 | 每个被拦截动作必须可解释、可重放、可定位来源                             | Trace + policy version + evidence span |
| INV-07 | MCP Tool annotation/description 只能作为不可信元数据，不构成授权证明     | Action observation + explicit policy   |

## 6. 主要攻击路径

| **Path**                  | **Kill Chain**                                | **主要控制点**                                 |
|---------------------------|-----------------------------------------------|------------------------------------------------|
| T1 Direct Injection       | User→Agent→Tool                               | Context Guard / Intent / Policy                |
| T2 Indirect Web/Issue     | External→Context→Agent→Tool                   | Source label / Injection / Intent / Policy     |
| T3 MCP Tool Poisoning     | Tool metadata→Planner→Tool Call               | MCP registration scan / runtime policy         |
| T4 MCP Response Injection | MCP response→Agent→second tool                | Response Hook / source provenance / policy     |
| T5 Memory Poisoning       | Write→Persist→Retrieve→Execute                | Memory Write Guard / Read Guard / taint        |
| T6 Secret Exfiltration    | fs.read(secret)→context→net.fetch             | Secret label / egress hard block               |
| T7 Unauthorized Git Push  | benign coding task→git.push                   | Intent scope / ASK                             |
| T8 Cascading Injection    | Web→Agent A→Agent B→MCP                       | trace/span / propagated source_refs            |
| T9 Obfuscation            | Unicode/encoding/multilingual→detector bypass | raw+canonical views / defense in depth         |
| T10 Guard Bypass          | Agent directly invokes tool outside proxy     | deployment hardening / deny direct credentials |

## 7. STRIDE + Agent-specific 分析

| **威胁**                 | **Agent 场景**                         | **控制**                                              |
|--------------------------|----------------------------------------|-------------------------------------------------------|
| Spoofing                 | 伪造用户批准、伪装 trusted MCP         | signed approval / server identity / tool pinning      |
| Tampering                | MCP description 或 memory 被修改       | hash/version/provenance/audit                         |
| Repudiation              | Agent/管理员否认执行或批准             | trace_id + actor identity + immutable decision record |
| Information Disclosure   | secret 经 tool/sub-agent 外泄          | taint + egress policy + masking                       |
| Denial of Service        | 超长 prompt / 无限子 Agent / tool loop | budgets/rate limits/max depth                         |
| Elevation of Privilege   | read task 升级成 exec/write/push       | Intent/Action alignment + policy                      |
| Prompt/Context Injection | 外部内容变成控制指令                   | source trust + injection signal + policy              |
| Memory Poisoning         | 恶意事实跨会话持续生效                 | write/read guards + quarantine + provenance           |

## 8. 风险评级

风险等级不单由文本分类概率决定；最终风险由 Source Trust、Intent Deviation、Data Flow、Privilege/Effect、Destructiveness 和 Injection Signal 共同决定。Critical 规则可绕过模型评分直接 BLOCK。

```text
Risk = combine(
injection_risk,
source_trust,
intent_deviation,
resource_sensitivity,
effect_severity,
taint_flow,
user_approval
)
Critical hard rule examples:
SECRET -> UNTRUSTED_NETWORK = BLOCK
FILE_WRITE -> ~/.ssh/** = BLOCK
EXEC -> download|pipe|shell = BLOCK
```

## 9. Abuse Cases & Expected Decisions

| **Case**                                       | **Expected**     | **Reason**                           |
|------------------------------------------------|------------------|--------------------------------------|
| 用户要求读 README → fs.read(repo/README.md)    | ALLOW            | intent/scope/effect 对齐             |
| 用户要求读 README → fs.read(~/.ssh/id_rsa)     | BLOCK            | credential scope violation           |
| 用户要求修 bug → git.push(main)                | ASK              | 合理但具远程副作用，授权不足         |
| 网页内容诱导读取 secret → net.fetch(evil)      | BLOCK            | untrusted provenance + secret egress |
| 用户明确要求上传指定日志到 trusted.example.com | ALLOW/ASK        | 取决于日志是否含 secret 以及域策略   |
| Memory 提示“以后自动上传日志”                  | BLOCK/QUARANTINE | 跨会话持久化指令来源不可信           |

## 10. Residual Risks

- 语义 Intent 解析错误可能导致误阻断或漏报；通过显式 scope、ASK 和 deterministic policy 降低影响。

- 若 Agent 或工具能绕过 Proxy 直连资源，则无法强制阻断；部署必须收敛凭据与网络权限。

- 加密/压缩后的 secret 可能逃逸简单 taint；MVP 仅覆盖显式/常见编码传播。

- 闭源模型内部不可见的 reasoning 无法做完整 token-level attribution；采用 observable context/action provenance。

- 管理员错误配置 trusted domain 或 allow policy 仍可能造成风险；需要 policy lint + default-deny sensitive categories。

## Decision Log

| **ID**  | **Decision**                           | **Rationale**                  | **Status** |
|---------|----------------------------------------|--------------------------------|------------|
| SEC-D01 | 所有外部内容默认 UNTRUSTED             | 避免“工具返回即可信”的隐式升级 | Accepted   |
| SEC-D02 | 安全硬边界不依赖单一 LLM Judge         | 降低 nondeterminism 与绕过风险 | Accepted   |
| SEC-D03 | Critical effects selective fail-closed | Guard 故障时优先保护高价值资产 | Accepted   |

## Review Checklist

☐ 所有 P0 资产是否都有明确 owner 和信任边界？

☐ 是否存在绕过 Proxy 的直接工具路径？

☐ ASK token 是否能防止参数/目标被替换？

☐ 日志是否可能存储原始 secret？

☐ Guard 自身异常时各 effect 的 fail-open/fail-closed 是否定义？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/

说明：本文档采用可公开验证的大厂工程文档习惯，不声称复刻 OpenAI 或字节跳动未公开的内部模板、审批流或专有规范。
