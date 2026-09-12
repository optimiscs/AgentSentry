> 项目：AgentSentry（意链盾，暂定名）

# 08 部署与运维设计（Deployment & Operations）

定义部署拓扑、配置、观测、日志安全、故障降级、发布和回滚。

| **Document ID**  | AS-OPS-008                                 |
|------------------|--------------------------------------------|
| **Status**       | Draft for Design Review                    |
| **Version**      | v0.9                                       |
| **Owner**        | 系统负责人（A）                            |
| **Reviewers**    | 安全负责人（B）、评测负责人（C）           |
| **Last Updated** | 2026-09-10                                 |
| **Target**       | 研究生网络安全创新大赛 / MVP Design Review |

> **TL;DR** MVP 采用 Docker Compose 单机部署：gateway/proxy、decision service、trace store、dashboard 可分进程但共享版本化配置。高风险工具凭据只暴露给 Proxy，不直接暴露给 Agent，从部署层防止绕过。运行时遵循最小权限、审计、可回滚和 selective fail-closed。

## 1. Deployment Topology

```text
Host / VM
┌──────────────────────────────────────────────────────┐
│ Agent / Demo Agent │
│ │ │
│ ├── Agent Hook ───────> Decision Service │
│ │ │ │
│ └── MCP client ──> MCP Runtime Proxy ──> MCP/Tools │
│ │ │
│ ├──> Trace Store │
│ └──> Approval API │
│ │ │
│ Dashboard <──────────────────────── Trace/Decision │ │
└──────────────────────────────────────────────────────┘
Red-team/benchmark containers are isolated from production path.
```

## 2. Container Set

| **Service**           | **Port**      | **权限**                          | **依赖**                  |
|-----------------------|---------------|-----------------------------------|---------------------------|
| agentsentry-gateway   | 8080          | 接 Agent/MCP；不直接持久化 secret | decision                  |
| agentsentry-decision  | 8081          | 只读 policy/model/config          | optional model runtime    |
| agentsentry-trace     | 8082/internal | 写 audit store                    | SQLite/Postgres           |
| agentsentry-dashboard | 3000          | 只读 sanitized trace + approval   | trace/gateway             |
| benchmark-runner      | none/internal | sandbox only                      | AI-Infra-Guard/benchmarks |

## 3. Hardware Profiles

| **Profile** | **CPU/RAM**      | **GPU**             | **用途**                      |
|-------------|------------------|---------------------|-------------------------------|
| Minimal     | 4 vCPU / 8 GB    | None                | 规则 + 轻量 classifier + demo |
| Recommended | 8 vCPU / 16 GB   | 可选 1×消费级 GPU   | 本地语义模型/高并发评测       |
| Benchmark   | 16+ vCPU / 32 GB | 按 Agent model 需要 | 并行公开 benchmark            |

MVP 的安全硬规则必须在无 GPU 条件下可运行；GPU/LLM 不得成为阻断 Critical rule 的单点依赖。

## 4. Configuration

```text
config/
runtime.yaml
policy.yaml
trusted_domains.yaml
sensitive_resources.yaml
models.yaml
logging.yaml
runtime.yaml key examples:
mode: shadow | enforce
fail_safe:
FILE_READ: allow_if_low_risk
FILE_WRITE: deny
NET_EGRESS: deny
EXEC: deny
GIT_PUSH: deny
approval_timeout_seconds: 600
max_agent_depth: 3
```

## 5. Secrets & Credentials

- 下游 MCP/API 凭据优先只挂载给 MCP Proxy，而不是 Agent 进程。

- 配置文件不得保存明文生产密钥；使用环境变量/secret mount。

- 日志默认屏蔽 Authorization、Cookie、API key、SSH private key 内容。

- 比赛 Demo 使用 CANARY_SECRET\_\*；严禁真实 SSH/AWS 凭据。

## 6. Observability

| **信号**     | **指标/字段**                                           | **告警**                     |
|--------------|---------------------------------------------------------|------------------------------|
| Decision     | allow/ask/block count, reason_code                      | critical block spike         |
| Latency      | decision p50/p95, model p95                             | fast-path p95 \> budget      |
| Availability | health/ready, dependency errors                         | decision service unavailable |
| Security     | secret egress attempts, sensitive write, dangerous exec | 任何 Critical event          |
| Utility      | ask rate, benign block rate                             | 异常升高                     |
| Audit        | trace gap %, dropped events                             | trace gap \> 1%              |

## 7. Logging & Audit

- 每个特权动作记录 actor/session/agent/tool/target/decision/policy version。

- Audit log 与普通 debug log 分离；默认 JSON Lines，便于 SIEM 接入。

- 敏感字段先 redaction 后落盘；raw secret 只在测试隔离环境且显式开启。

- Security decision 记录输入 hash 与必要 evidence，不依赖不可审计的自由文本理由。

## 8. Health & Fail-safe

| **Dependency**  | **Failure**               | **Action**                                                    |
|-----------------|---------------------------|---------------------------------------------------------------|
| Policy Engine   | unavailable/compile error | write/exec/egress/push fail-closed                            |
| Injection Model | unavailable               | 继续 Intent/Policy/Taint；记录 degraded                       |
| Intent Model    | unavailable               | 使用 cached contract；未知高风险 → ASK/BLOCK                  |
| Trace Store     | unavailable               | bounded local buffer；Critical block 不依赖存储成功           |
| Dashboard       | unavailable               | 不影响自动 BLOCK；ASK 超时则不执行                            |
| Downstream MCP  | timeout                   | safe retry only if idempotent; prevent duplicate side effects |

## 9. Deployment Procedure

1.  检查 Docker/Compose、端口、磁盘与时间同步。

2.  生成本地配置并运行 policy validate。

3.  启动 trace/decision/gateway/dashboard。

4.  运行 /healthz 与 /readyz。

5.  以 shadow 模式接入 Demo Agent，验证 trace 覆盖。

6.  运行 10 个 e2e-smoke；确认 sanitized log。

7.  启用 enforce-critical；再次运行攻击/benign case。

8.  如进入比赛演示，加载固定 policy/model/benchmark manifest。

## 10. Rollback

- 镜像采用 immutable tag + digest；保留 previous-known-good。

- Policy 与 binary 解耦版本；支持单独 rollback policy。

- 若新版本误阻断严重，可先切回 shadow，但 Critical hard block 集不随意关闭。

- 回滚后自动执行 smoke regression 并记录 rollback event。

## 11. Incident Runbook

| **事件**                 | **第一动作**                             | **后续**                                 |
|--------------------------|------------------------------------------|------------------------------------------|
| 疑似 secret exfiltration | 冻结相关 trace/session，阻断 destination | 旋转 canary/真实凭据；导出 sanitized DAG |
| 大量误阻断               | 检查最近 policy/model version            | rollback policy；对 hard benign 回归     |
| Guard 被绕过             | 收敛 Agent 网络/凭据，强制 Proxy 路径    | 补 deployment control 与测试             |
| Audit 泄露敏感信息       | 停止导出/限制访问                        | 删除或重加密；修 redaction；复盘         |
| MCP server 行为突变      | 临时 quarantine server/tool              | 比较 tool metadata/schema/hash；重新扫描 |

## 12. Productionization Backlog（比赛后）

- PostgreSQL/ClickHouse 审计存储、HA、多租户、RBAC、OIDC。

- OPA/Rego adapter、SIEM/SOC integration、policy-as-code workflow。

- mTLS、MCP server identity attestation、tool pinning/rug-pull monitoring。

- Kubernetes sidecar/daemon deployment 与组织级 policy distribution。

## Review Checklist

☐ Agent 是否仍持有可绕过 Proxy 的下游凭据？

☐ Critical effect 的 fail-safe 是否明确并经过故障测试？

☐ 所有 audit log 是否默认脱敏？

☐ rollback 是否同时覆盖 binary 与 policy？

☐ clean machine 是否可依据本文档在 30 分钟内完成部署和 smoke？

## 公开参考原则

- ByteDance DeerFlow public RFC practice: implementation 前先以 RFC 明确问题、资源/权限映射、架构方案、开放问题和实施边界。参考：github.com/bytedance/deer-flow/docs/plans/2026-07-10-pluggable-authorization-rfc.md

- ByteDance DeerFlow documentation organization: Architecture / API / Auth Design / Configuration / Setup 分离管理，强调设计与接口边界。参考：github.com/bytedance/deer-flow/backend/docs/README.md

- OpenAI public Supplier Security Measures: 要求 documented Secure Development / Security-by-Design process，覆盖 planning、coding、testing、deployment、maintenance，并要求审计日志与特权操作可追责。参考：openai.com/policies/supplier-security-measures/

说明：本文档采用可公开验证的大厂工程文档习惯，不声称复刻 OpenAI 或字节跳动未公开的内部模板、审批流或专有规范。
