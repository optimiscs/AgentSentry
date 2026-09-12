# 12 API 与数据模型规范

文档 ID：AS-DOC-12 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：B ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

2026-09-12 补充：IntentIR 新增 `authorized_destination_hashes`，ActionIR 新增 `destination_hashes`，默认空列表，旧会话保持原有保守语义。字段由受信任务解析器/适配器构造，不能由不可信工具内容增加；绑定完整目标，继续纳入完整 Intent/Action 审批快照。详见 [ADR-008](../adr/adr-008.md)，导出 Schema 与 OpenAPI 随 make verify 同步。

## API状态与版本

以下接口为待实现合同，路径采用`/v1`。Schema当前为`1.0-draft`，W2冻结前不声称稳定兼容；冻结后删除/改语义需升major，新增字段/枚举需显式UNKNOWN处理。Draft变动同步ADR与契约测试。

| Method / Path | 输入→输出 | 身份与关键错误 |
|---|---|---|
| POST /v1/context/scan | ContextChunk→RiskSignal | 会话范围认证；超长/未扫描明确报错，不返回假安全 |
| POST /v1/intent/resolve | 已认证任务+静态授权上限→IntentIR | 外部source不能更新；unresolved不授权 |
| POST /v1/action/decide | session+ActionIR→Decision | 下游只能经Proxy执行，直接拿Decision不能跳过执行再校验 |
| POST /v1/approval | approval_id+approve/deny→状态/受限票据 | 当前用户权限验证、CSRF/Origin、原子消费 |
| GET /v1/traces/{trace_id} | 身份→脱敏事件/图 | 对每次trace读取做会话/角色范围校验 |
| POST /v1/policies/validate | draft规则→编译错误/冲突 | 管理身份；validate不自动发布策略 |
| GET /healthz、/readyz | 存活/依赖与模式 | 不暴露密钥/敏感路径；ready可区分cpu、semantic、audit降级 |

应用错误码包含SECURITY_BLOCKED、USER_APPROVAL_REQUIRED、APPROVAL_INVALID、POLICY_ERROR、INTENT_UNRESOLVED、TRACE_DEGRADED、RESOURCE_CHANGED、RESULT_UNKNOWN。错误属于协议结果还是HTTP错误由SDK契约测试固定；不得把业务BLOCK伪装为网络成功执行。

## 公共字段与枚举

对象均携带schema_version及必要的trace_id/session_id/agent_id，source_refs引用稳定来源ID。Decision只有ALLOW/ASK/BLOCK。TrustLevel为TRUSTED/UNTRUSTED/UNKNOWN；外部来源标签UNTRUSTED_EXTERNAL属于标签集合，不是单独权限授权。资源类包含REPO/SECRET/CREDENTIAL/PII/INTERNAL/PUBLIC/SYSTEM/UNKNOWN。

| 对象 | 必要字段与校验 |
|---|---|
| ContextChunk | chunk_id、来源type/id、trust、raw/canonical证据引用、char_span_map、标签；原文不默认持久化 |
| RiskSignal | chunk_id、risk/type/score、evidence spans、source_refs、model/threshold/normalizer版本；只作信号 |
| IntentIR | intent_id/version、actor/permission_snapshot_hash、goal、allowed_scopes/effects、forbidden_effects、sensitive_access、unresolved、evidence_source_refs |
| ActionIR | action_id、tool/server身份及version/hash、effects数组、规范化资源/目标、resource_version、args_hash、source_refs、adapter_version；复合effect逐一校验 |
| AlignmentResult | aligned、deviation_types、expected/actual scope/effect、evidence refs、human explanation；不能只给自由文本理由 |
| Decision | decision_id、action_id、decision、reason_codes、matched_policies、risk、policy/intent/model/adapter版本、expires_at、latency；ALLOW要在执行前仍有效 |
| ApprovalToken | approval_id、actor、permission_hash、session/action、tool/server、args/target/resource版本、intent/policy版本、expires_at、nonce、signature；客户端不控制签名字段 |
| SecurityEvent | event_id、trace/span/parent、actor/agent、action/decision、event_type、wall_time、sequence、source_refs、脱敏payload；根span的parent允许null |
| ProvenanceEdge | edge_id、from/to、kind(call/data_flow/derived_from)、evidence_ref、confidence、observed/inferred；只把有证据的边计入精确黄金图 |

## 正规化与执行快照

内部冻结的执行参数与审计脱敏参数分离。参数hash以确定性的规范化序列化计算，规范版本明确；低熵秘密摘要不能公开输出。执行前重验文件实际对象、Git commit、最终网络目的及策略/权限版本；相同字面参数但对象改变也令审批失效。

## 审批生命周期

```text
pending → denied / expired / cancelled
pending → approved → 原子claim与再校验 → executing
executing → succeeded / failed / unknown
```

对同一action重试使用幂等键；pending不占用无界HTTP线程，可以返回approval_id轮询/续接。与MCP长调用兼容方式在Spike确认；任何断连都不能自动视作批准。unknown状态需要执行器对账，不复用nonce或盲目重试。

## 回放与兼容测试

回放包含IR、风险signals、策略hash、模型/阈值/adapter/normalizer版本和必要数据流标签。对公开/合成输入允许完整语义复现；脱敏后的真实业务证据只保证指定的策略回放，不承诺重新生成同样模型文本。TC-08、12、15、17、40验证枚举、格式、权限和兼容边界；测试实现仍待开发。

## 开发版已实现接口（0.1.0.dev1）

可运行合同以 [OpenAPI](../generated/openapi.json)、[IntentIR](../generated/IntentIR.schema.json)、[ActionIR](../generated/ActionIR.schema.json)、[Decision](../generated/Decision.schema.json) 为准，由 `make contracts` 从代码导出。新版本 IntentIR 增加 maximum_effects；ActionIR 的 data_refs 是实际 body_ref/content_ref 数据引用，source_refs 只表示已观察上下文。

| 方法 / 路径 | 权限 | 行为 |
|---|---|---|
| GET /healthz | 无令牌 | 仅状态/版本；不泄露内部配置 |
| GET /api/me、/api/status | operator / agent | 身份与运行状态 |
| POST /api/sessions | operator | 从可信任务通道建立合同 |
| POST /api/context/scan、/scan-batch | operator / agent | 单条或最多 16 条；失败进入明确错误状态 |
| POST /api/tools/call | operator / agent | 候选动作门控，幂等 key 绑定完整请求 |
| POST /api/actions/{id}/cancel | operator / agent | 仅取消 pending，不假装撤销已产生副作用 |
| GET /api/approvals；POST /api/approvals | operator | 精确动作审批；批准后重新校验 |
| GET /api/actions/{id}/preview | operator | 完整参数脱敏预览与动作指纹 |
| GET /api/traces/{id}、/{id}/export | 读取 / operator 导出 | 脱敏事件、图、JSON 附件 |
| POST /api/actions/{id}/replay | operator | 固定原始 IR 与策略重放，不执行工具 |
| GET /api/policy；PUT /api/policy | operator | 版本冲突检查；热更新不可修改硬拒绝规则 |
| GET /api/reports | operator / agent | 已归档实测报告 |
| POST /api/demo/{issue,secret,approval,memory} | operator | 仅演示模式，使用合成数据 |
| /mcp/ | operator / agent | MCP Streamable HTTP，只有 scan_context / guarded_tool_call |

Bearer token 必须通过请求头传入；浏览器 Origin/Host/跨站检查独立于身份验证。API/stdio 从不把操作员 token 交给受控 Agent。当前是单操作员部署，不是企业多租户 RBAC。

## 原生产品 Hook 开发接口

新增 `/api/hooks/evaluate`、`/api/hooks/claim`、`/api/hooks/report`（身份必需），契约以 [OpenAPI](../generated/openapi.json) 为准。NativeCall 绑定 AgentSentry session、client（codex/claude-code）、客户端 session、tool_call_id、cwd、tool_name、tool_input；同 ID 不得改参。

evaluate 返回 ready / pending / blocked，仅决策不执行；pending 通过操作员 `/api/approvals` 审批。批准仅使许可 ready，claim 再核查完整 Intent/资源/策略/TTL，并原子消费一次许可。客户端执行完成后用不落审计明文的 receipt 回报；状态为 client_reported_succeeded/failed、`execution_verified=false`。网关 execution 账本不增加原生动作。重启后的 dispatched 为 unknown，ready 取消；不自动重复执行。

受控 MCP 仍走网关执行接口。此开发桥接不是透明任意工具代理，覆盖限制和真实产品未验收状态见 [接入矩阵](framework-integration-matrix.md)。
