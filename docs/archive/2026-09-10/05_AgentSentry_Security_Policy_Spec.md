> 项目：AgentSentry（意链盾，暂定名）

# 05 安全策略规范（Security Policy Spec）

定义 Policy DSL、优先级、内置规则、审批语义和策略治理。

| **Document ID**  | AS-POL-005                                 |
|------------------|--------------------------------------------|
| **Status**       | Draft for Design Review                    |
| **Version**      | v0.9                                       |
| **Owner**        | 安全/算法负责人（B）                       |
| **Reviewers**    | 系统负责人（A）、评测负责人（C）           |
| **Last Updated** | 2026-09-10                                 |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review |

> **TL;DR** 策略采用“确定性硬规则优先 + 语义条件补充 + scoped approval”的设计。任何文本分类器或 LLM 结果都只是 signal；Critical data flow 与敏感副作用由 deterministic policy 强制执行。

## 1. Policy Decision Semantics

| **Decision** | **定义**                                                   | **典型场景**                      |
|--------------|------------------------------------------------------------|-----------------------------------|
| ALLOW        | 当前 Intent、资源范围与副作用授权充分，且无高风险数据流    | 读 repo/README                    |
| ASK          | 动作可能合理，但授权/范围/副作用存在可由用户消除的不确定性 | 修 bug 后 git.push                |
| BLOCK        | 命中不可接受风险或明确违反安全不变量                       | secret→unknown network、写 ~/.ssh |

## 2. Priority & Conflict Resolution

```text
1. Critical Hard Block
2. Explicit Deny in user/org policy
3. Valid scoped ApprovalToken for ASK-eligible rule
4. ASK
5. Explicit Allow
6. Default policy by Effect/ResourceClass
NOTE: approval cannot override non-overridable Critical Hard Block.
```

## 3. DSL v1 Grammar（概念版）

```text
rule <name> severity <level> [overridable true|false] {
when
<predicate>
[and|or <predicate> ...]
then
ALLOW | ASK("message") | BLOCK("message")
}
Supported predicates (P0):
action.effect
action.tool
resource.matches(pattern)
resource.class
destination.domain
destination.trust
intent.allows(effect)
intent.scope_contains(resource)
flow.has(label)
source.type
source.trust
agent.depth
approval.valid
```

## 4. P0 Built-in Policies

| **ID**  | **Rule**                       | **Condition**                                                          | **Decision**       | **Severity**  |
|---------|--------------------------------|------------------------------------------------------------------------|--------------------|---------------|
| POL-001 | Sensitive filesystem write     | FILE_WRITE + ~/.ssh/\*\*\|~/.aws/\*\*\|/etc/cron.\*                    | BLOCK              | Critical      |
| POL-002 | Credential egress              | NET_EGRESS + flow.has(CREDENTIAL\|SECRET) + destination!=TRUSTED       | BLOCK              | Critical      |
| POL-003 | Download pipe execute          | EXEC + command pattern curl/wget + pipe shell                          | BLOCK              | Critical      |
| POL-004 | Encoded execute                | EXEC + base64/hex decode + shell execution                             | BLOCK              | High/Critical |
| POL-005 | Unexpected git push            | GIT_PUSH + intent.allows(GIT_PUSH)!=true                               | ASK                | High          |
| POL-006 | Credential read outside intent | FILE_READ + resource.class=CREDENTIAL + intent sensitive_access!=ALLOW | BLOCK              | Critical      |
| POL-007 | Cross-scope write              | FILE_WRITE + !intent.scope_contains(resource)                          | ASK/BLOCK          | High          |
| POL-008 | Secret to sub-agent            | DELEGATE + flow.has(SECRET\|CREDENTIAL)                                | BLOCK              | High          |
| POL-009 | Unknown network egress         | NET_EGRESS + destination.trust=UNKNOWN + intent network!=ALLOW         | ASK                | Medium/High   |
| POL-010 | Excessive delegation           | DELEGATE + agent.depth\>=configured_max                                | BLOCK              | Medium        |
| POL-011 | Memory persistent instruction  | MEMORY_WRITE + source.trust=UNTRUSTED + instruction_like=true          | QUARANTINE/BLOCK   | High          |
| POL-012 | Tool metadata privilege claim  | source=MCP_DESCRIPTION + claims_trust=true                             | IGNORE_CLAIM/ALERT | Medium        |

## 5. DSL Examples

```text
rule secret_egress severity critical overridable false {
when
action.effect == NET_EGRESS
and flow.has(SECRET)
and destination.trust != TRUSTED
then
BLOCK("Sensitive data cannot be sent to an untrusted destination")
}
rule git_push_without_authorization severity high overridable true {
when
action.effect == GIT_PUSH
and intent.allows(GIT_PUSH) != true
then
ASK("Agent wants to push code to a remote branch. Approve this exact
push?")
}
rule repo_read severity low overridable true {
when
action.effect == FILE_READ
and resource.class == REPO
and intent.scope_contains(resource)
then
ALLOW
}
```

## 6. Approval Semantics

- 批准必须是 action-specific，不存在“本会话后续全部允许”的隐式全局批准。

- 绑定：session_id、tool_name、normalized_args_hash、target、expires_at、policy_version。

- 参数发生任何安全相关变化，原 token 立即失效。

- Critical non-overridable 规则不能被用户批准覆盖；管理员变更 policy 才能修改。

- 默认审批有效期 10 分钟，可配置。

## 7. Intent-aware Policy Rules

| **用户任务**                            | **候选动作**                   | **Decision** | **理由**                    |
|-----------------------------------------|--------------------------------|--------------|-----------------------------|
| “总结 README”                           | fs.read(repo/README.md)        | ALLOW        | same scope/effect           |
| “总结 README”                           | fs.read(~/.ssh/id_rsa)         | BLOCK        | sensitive + scope violation |
| “修复并测试 bug”                        | exec(pytest)                   | ALLOW        | required effect，命令低风险 |
| “修复 bug”                              | git.push(main)                 | ASK          | 远程副作用未明确授权        |
| “把这份脱敏报告上传到 corp.example.com” | net.fetch(corp.example.com)    | ALLOW        | explicit trusted egress     |
| “分析日志”                              | net.fetch(unknown.com, secret) | BLOCK        | secret egress               |

## 8. Policy Lifecycle

1.  Author：安全负责人提交规则与测试 case。

2.  Lint：语法、死规则、冲突、over-broad wildcard 检查。

3.  Unit tests：每条规则至少 1 positive + 1 negative + 1 boundary case。

4.  Shadow：先观察命中率与 benign false positives。

5.  Approve：双人 Review 后进入 enforce。

6.  Version：发布 policy_version；历史 decision 保留引用。

7.  Rollback：一键切回 previous known-good policy。

## 9. Policy Security

- Policy 文件只允许管理员写，运行时只读挂载。

- 启动时计算 hash；变更写审计事件。

- 禁止从 MCP Tool Description 或模型输出动态生成可直接 enforce 的规则。

- 若未来支持 LLM policy suggestion，必须先进入 draft + human review。

## Decision Log

| **ID**  | **Decision**                                     | **Rationale**                    | **Status** |
|---------|--------------------------------------------------|----------------------------------|------------|
| POL-D01 | Critical hard rules 不可被普通用户 approval 覆盖 | 防止 social engineering 绕过     | Accepted   |
| POL-D02 | 默认 ASK 只用于“可合理授权”的灰区                | ASK 不能替代明确危险动作的 BLOCK | Accepted   |
| POL-D03 | 规则必须有自动测试才能进入 enforce               | 降低策略回归风险                 | Accepted   |

## Review Checklist

☐ 是否有 BLOCK 规则过宽导致正常任务不可用？

☐ 是否有 ASK 可以绕过 Critical invariant？

☐ 每个敏感 sink 是否有至少一个 hard rule？

☐ 策略冲突是否可确定性解决？

☐ Policy 变更是否可回滚和审计？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/
