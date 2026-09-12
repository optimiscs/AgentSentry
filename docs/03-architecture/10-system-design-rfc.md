# 10 总体设计 / System Design RFC

文档 ID：AS-DOC-10 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：A ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

## 设计决策

采用Hook提供上下文与任务合同、Proxy强制执行前门控、确定性Policy统一决策。MVP使用模块化单仓库，默认一个API进程承载网关/决策/审计接口，沙箱Executor与可选模型服务分进程；不引入多租户微服务平台。

```text
授权通道 → IntentIR ──────────────────────┐
外部来源 → ContextChunk/RiskSignal ───────┤
Agent → Proxy暂停 → ActionIR ─────────────┤
                                        ▼
              Alignment + 显式数据流 + DSL（硬拒绝优先）
                   ├ BLOCK：零下游执行
                   ├ ASK：持久化pending → 身份审批 → 重新校验
                   └ ALLOW → 冻结动作 → 受限Executor → MCP/工具
                                                      │
                    响应重新入站Context Guard ◀────────┘
所有事件 → 脱敏/缓冲 → SQLite Trace → DAG/时间线/报告
```

| 模块 | Owner | 责任与接口 |
|---|---|---|
| schemas/ | B | 唯一公共合同、枚举、版本与兼容性；JSON可跨进程 |
| gateway/ | A | Hook、stdio/HTTP MCP Proxy、暂停、取消、结果关联 |
| context/ | A | 多来源分块/检测、raw↔canonical坐标、Memory入站 |
| adapters/ | A+B | 参数与真实对象归一化、复合effects、执行对象绑定 |
| intent/ | B | 权限有上限的任务合同、对齐/未决项 |
| policy/ | B | DSL编译、优先级、审批验证、确定性决策 |
| provenance/ | C | 显式标签/边持久化、传播与推断标记；B消费谓词 |
| trace/ | C | 脱敏审计、去重、图重建、回放 |
| dashboard/ | C | 事件/审批/DAG/评测四个视图 |
| benchmarks/ | C | 各基准独立环境，统一manifest和原生指标转换 |

## 关键控制流

合同生成只接可信任务通道，权限上限来自静态配置；模型输出不能改策略。Action归一化失败不默认ALLOW；绑定执行对象版本/参数hash。Policy先检查硬拒绝、显式DENY，再看ASK可覆盖授权，最后是明确允许/默认策略。复合动作每个effect都受约束，任一硬拒绝使整个动作BLOCK。

ASK动作进入持久化状态机：pending→approved/denied/expired/cancelled；approved通过再校验和原子claim后才进入executing→succeeded/failed/unknown。进程重启或签名key/policy版本变化使未消费旧审批失效；执行结果未知不能当成功，也不能盲重试。

MCP受控版本先通过官方SDK固定版本兼容验证。工具描述、tools/list更新和工具响应都回到不可信入站链路；拒绝请求保持原request/action关联。客户端支持矩阵分别写Hook完整模式和Proxy兼容模式的可观测范围，不承诺闭源CoT或不可见Memory。

## 存储与故障

SQLite WAL单写者记录不可变事件，event_id幂等去重；trace树使用parent_span，数据DAG使用单独ProvenanceEdge。不同边类型不得混为因果。存储故障使用有界本地缓冲；BLOCK不等待写入成功，缓冲耗尽停止新的高危ALLOW。API模型/策略异常仍遵循安全默认，不绕过以维持健康指标。

## 性能与部署

规则解析/资源分类缓存，Intent按任务版本复用；缓存key包含权限/策略/工具/资源版本，不缓存跨会话ALLOW或复用审批token。长上下文分块可并行检测，但未扫描内容不得进入“已安全”的决策。GPU只承载语义模型/评测Agent，CPU硬规则不依赖GPU。

Proxy持有下游访问能力，Agent与不可信工具不能接触宿主真实凭据。只绑定127.0.0.1仍需API身份/Origin保护。系统路径/网络隔离必须以TC-23旁路测试证明，容器可运行本身不等于隔离正确。

## 当前未决项

MCP SDK/模型/推理框架精确版本、容器验收主机、最大输入和并发预算在W1 Spike后冻结。当前开发版实现与边界见 [ADR-007](../adr/adr-007.md)，可运行接口已导出 OpenAPI；完整模型/容器/效果验收仍未完成。完整安全规则及故障判定见对应规范，发布前须完成RTM证据签收。

## 当前 Hook + MCP 落地范围

首批面向 **Codex / Claude Code** 现成编程 Agent，产品能力、原生工具与 MCP 两条执行路径及后续路线见 [主流编程 Agent 接入矩阵](framework-integration-matrix.md)。当前没有完成这两个产品的端到端验收；框架适配为后续评测扩展。

MCP Proxy 已提供 stdio 和 Streamable HTTP 接口，tools/call 经过执行前策略门控。Agent Hook 侧目前提供任务建立、context/scan、scan-batch 及来源引用接口，仍需 Agent 集成方主动上报；尚未实现 Codex / Claude Code 自动 Hook 接入，也没有全量上下文/Memory 捕获。原生工具 Hook 还需补只评估不执行的决策接口及结果关联，不能把会执行动作的 tools/call 当作审批查询。普通宿主 Agent 的直接文件或网络操作需要独立隔离，不能由 MCP 协议接入本身推导出强制安全边界。
