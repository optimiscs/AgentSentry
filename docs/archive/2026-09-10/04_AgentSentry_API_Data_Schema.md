> 项目：AgentSentry（意链盾，暂定名）

# 04 接口与数据模型规范（API & Schema Spec）

冻结三人协作的事件、IR、API、版本与兼容性契约。

| **Document ID**  | AS-API-004                                 |
|------------------|--------------------------------------------|
| **Status**       | Draft for Design Review                    |
| **Version**      | v0.9                                       |
| **Owner**        | 系统负责人（A）                            |
| **Reviewers**    | 算法负责人（B）、评测负责人（C）           |
| **Last Updated** | 2026-09-10                                 |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review |

> **TL;DR** 所有模块只通过版本化 Schema 交互。核心对象为 ContextChunk、IntentIR、ActionIR、Decision、ApprovalToken、SecurityEvent、TraceSpan。任何安全相关字段不得以自由文本替代结构化枚举。

## 1. Versioning Rules

- 所有外部 API 使用 /v1；事件 payload 带 schema_version。

- 新增 optional 字段为 backward compatible；删除/重命名/语义变化必须升 major version。

- 决策回放必须保存 policy_version、model_version、normalizer_version。

- 枚举新增默认必须被旧消费者按 UNKNOWN 处理，禁止 silent ALLOW。

## 2. Core Enums

```text
Decision = ALLOW | ASK | BLOCK
TrustLevel = TRUSTED | UNTRUSTED | UNKNOWN
SourceType = USER | SYSTEM | WEB | DOCUMENT | EMAIL | ISSUE | CODE |
MCP_DESCRIPTION | MCP_RESPONSE | MEMORY | SUB_AGENT
Effect = FILE_READ | FILE_WRITE | NET_EGRESS | EXEC | GIT_COMMIT |
GIT_PUSH | DELEGATE | MEMORY_READ | MEMORY_WRITE | OTHER
ResourceClass = PUBLIC | REPO | INTERNAL | PII | SECRET | CREDENTIAL |
SYSTEM | UNKNOWN
RiskLevel = INFO | LOW | MEDIUM | HIGH | CRITICAL
```

## 3. ContextChunk

```text
{
"schema_version": "1.0",
"chunk_id": "ctx_01H...",
"trace_id": "tr_01H...",
"session_id": "sess_...",
"agent_id": "agent_main",
"source_type": "ISSUE",
"source_id": "github://org/repo/issues/123",
"trust_level": "UNTRUSTED",
"raw_text": "...",
"canonical_text": "...",
"char_span_map": [{"raw":[10,30],"canonical":[10,29]}],
"labels": ["UNTRUSTED_EXTERNAL"],
"created_at": "2026-09-10T12:00:00+08:00"
}
```

## 4. IntentIR

```text
{
"schema_version": "1.0",
"intent_id": "int_...",
"session_id": "sess_...",
"goal": "code_review",
"allowed_effects": ["FILE_READ"],
"allowed_scopes": ["repo://current/**"],
"required_effects": [],
"side_effect_policy": {
"NET_EGRESS": "DENY",
"GIT_PUSH": "UNKNOWN"
},
"sensitive_access": "DENY",
"unresolved": ["whether_commit_is_requested"],
"evidence_source_refs": ["user:msg_001"],
"confidence": 0.91
}
```

## 5. ActionIR

```text
{
"schema_version": "1.0",
"action_id": "act_...",
"trace_id": "tr_...",
"agent_id": "agent_main",
"tool_name": "filesystem.read_file",
"effect": "FILE_READ",
"resource": "file:///home/user/.ssh/id_rsa",
"resource_class": "CREDENTIAL",
"destination": null,
"destructive": false,
"normalized_args_hash": "sha256:...",
"source_refs": ["github://org/repo/issues/123"]
}
```

## 6. AlignmentResult

```text
{
"aligned": false,
"deviation_types": ["SCOPE_VIOLATION",
"SENSITIVE_ACCESS_NOT_AUTHORIZED"],
"risk": "CRITICAL",
"evidence": {
"allowed_scope": "repo://current/**",
"actual_resource": "file:///home/user/.ssh/id_rsa"
},
"explanation": "User task is code review in current repository; action
accesses credential outside scope."
}
```

## 7. Decision

```text
{
"decision_id": "dec_...",
"decision": "BLOCK",
"risk_level": "CRITICAL",
"reason_codes": ["SECRET_RESOURCE", "INTENT_SCOPE_VIOLATION"],
"matched_policies": ["sensitive_credential_read@1.2.0"],
"human_message": "Blocked credential access outside the user's
authorized repository scope.",
"policy_version": "2026.09.10.1",
"model_versions": {"injection":"pg2-86m-x", "intent":"local-llm-y"},
"latency_ms": 43
}
```

## 8. ApprovalToken

```text
{
"approval_id": "apr_...",
"session_id": "sess_...",
"action_id": "act_...",
"tool_name": "git.push",
"normalized_args_hash": "sha256:...",
"target": "repo://current/branch/dev",
"expires_at": "2026-09-10T12:20:00+08:00",
"approved_by": "user:...",
"signature": "..."
}
```

校验原则：任何 tool_name、target、args hash、session_id 不匹配均视为未授权，不允许 approval scope drift。

## 9. SecurityEvent / TraceSpan

```text
{
"event_id": "evt_...",
"trace_id": "tr_...",
"span_id": "sp_17",
"parent_span_id": "sp_12",
"event_type": "TOOL_DECISION",
"agent_id": "agent_main",
"agent_depth": 0,
"source_refs": ["github://org/repo/issues/123"],
"taint_labels": ["UNTRUSTED_EXTERNAL", "SECRET"],
"action_id": "act_...",
"decision_id": "dec_...",
"timestamp": "2026-09-10T12:03:14.128+08:00"
}
```

## 10. HTTP APIs

| **Method** | **Path**              | **用途**             | **关键响应**               |
|------------|-----------------------|----------------------|----------------------------|
| POST       | /v1/context/scan      | 扫描 ContextChunk    | risk/labels/evidence spans |
| POST       | /v1/intent/resolve    | 创建或更新 IntentIR  | IntentIR                   |
| POST       | /v1/action/decide     | 候选 ActionIR 决策   | Decision                   |
| POST       | /v1/approval          | 提交/拒绝 ASK        | ApprovalToken/status       |
| GET        | /v1/traces/{trace_id} | 获取事件与 DAG       | nodes/edges/events         |
| POST       | /v1/policies/validate | DSL lint/compile     | errors/warnings            |
| GET        | /healthz              | liveness             | 200/503                    |
| GET        | /readyz               | dependency readiness | dependency status          |

## 11. MCP Proxy Interception Contract

Proxy 必须在真实 tool execution 前完成 /v1/action/decide。ALLOW 才可转发；ASK 必须暂停并等待 scoped approval；BLOCK 返回标准化 tool error，并禁止请求到达下游 MCP。

```text
tools/call request
-> parse MCP name + arguments
-> ActionAdapter.to_ir()
-> POST /v1/action/decide
ALLOW -> forward
ASK -> suspend -> approval -> verify token -> forward
BLOCK -> synthetic MCP error (security_blocked)
```

## 12. Error Model

| **Code**               | **Meaning**                        | **Client handling**            |
|------------------------|------------------------------------|--------------------------------|
| SECURITY_BLOCKED       | Policy explicitly blocked action   | show reason; do not auto-retry |
| USER_APPROVAL_REQUIRED | ASK                                | request approval UI            |
| APPROVAL_INVALID       | scope/expiry/signature mismatch    | re-request approval            |
| POLICY_ERROR           | policy invalid/unavailable         | follow fail-safe table         |
| INTENT_UNRESOLVED      | insufficient authorization context | ASK or clarify                 |
| TRACE_DEGRADED         | audit store unavailable            | continue only per effect risk  |

## 13. Data Retention & Redaction

- raw_text 默认只保留必要窗口；secret 命中后优先保存 hash/类型/位置，不保存完整密钥。

- tool arguments 中 credential、token、Authorization header 进入日志前掩码。

- trace 导出支持 sanitized 模式，用于比赛材料和复盘。

- 默认 retention 7 天；配置允许更短。

## Review Checklist

☐ 所有模块是否只依赖 schema，而非内部 Python 对象？

☐ UNKNOWN 枚举是否默认安全处理？

☐ ApprovalToken 是否覆盖所有可被替换的关键参数？

☐ SecurityEvent 是否足以重建 DAG 与重放决策？

☐ 日志 schema 是否避免存储完整 secret？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/

说明：本文档采用可公开验证的大厂工程文档习惯，不声称复刻 OpenAI 或字节跳动未公开的内部模板、审批流或专有规范。
