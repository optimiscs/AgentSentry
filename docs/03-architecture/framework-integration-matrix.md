# 主流编程 Agent 接入覆盖矩阵与路线

更新日期：2026-09-12。状态：draft / capability_review_only。首批产品目标为 **Codex 与 Claude Code**，用户继续使用这些现成编程 Agent，由 AgentSentry 接入其 Hook、MCP 和执行环境提供安全控制。LangChain、CrewAI 等框架降为评测/自研 Agent 扩展，不能代替产品接入验收。当前已实现共用原生 Hook API、命令桥接和配置包生成器，并通过桥接层 HTTP/进程测试；两个真实产品客户端的端到端验收仍未完成。关联工作包：A02、A04、A05、A08、C06。

## 接入的三个层次

| 层次 | 接入内容 | 能作出的承诺 | 限制 |
|---|---|---|---|
| MCP 工具接入 | 客户端连接网关，将动作交给受控工具 | 对经过网关的已支持动作执行 ALLOW/ASK/BLOCK 与审计 | 不自动获得全部上下文、Memory，也不接管其他工具 |
| 产品 Hook 适配 | 接入用户输入、工具前后、会话和子 Agent 事件；绑定 session、来源与调用 ID | 对产品已暴露并实测覆盖的事件作关联与决策 | 不同客户端的事件、返回格式、异常处理不同；不可见状态不声明覆盖 |
| 执行边界约束 | 收回 Agent 的下游凭据、直接网络/文件权限，隔离执行器 | 通过旁路测试后，才能对所列资源声明强制控制 | 需要操作系统/容器/网络层配合，不能仅靠 MCP 或提示词实现 |

当前 stdio 和 Streamable HTTP 入口暴露 `scan_context`、`guarded_tool_call`；任务授权与审批使用独立操作员 API。它不是任意下游 MCP 工具目录的透明镜像：新增工具仍需可信注册、参数和副作用映射。通用注册 MCP 分支目前只允许 NET_EGRESS 语义，其他副作用需要专用资源适配器。下游 stdio 进程属于可信计算基；输出不可信并不意味着进程已被隔离。

## 首批产品目标

| 产品 | 官方接入能力 | 优先交付与待验证范围 | 当前验收 |
|---|---|---|---|
| **Codex CLI** | MCP；PreToolUse / PostToolUse 等 Hook | 首个自动化验收入口：用户任务、Bash、apply_patch、本地/MCP 工具及其结果；按固定版本验证 | REAL_PREHOOK_BLOCK / FULL_E2E_PENDING |
| **Codex 桌面端** | MCP 配置；共享能力须按实际桌面版本核实 | 在 CLI 适配基础上单独验证安装、启用、远程执行位置、审批和事件覆盖，不能用 CLI 结果直接替代 | NOT_RUN |
| **Claude Code** | MCP；PreToolUse / PostToolUse、用户输入和会话等 Hook | 同属首批目标：Bash、Read/Write/Edit、MCP 工具、工具返回和审批；验证配置和故障行为 | BRIDGE_VERIFIED / CLIENT_NOT_RUN |

官方依据：[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、[Codex Hooks](https://learn.chatgpt.com/docs/hooks)、[Claude Code Hooks](https://code.claude.com/docs/en/hooks)。本地只读核验 CLI 为 0.153.4，5090 为 0.154.0-alpha.6.2，帮助包含 MCP 管理和 Hook 信任选项；未将“命令存在”算作接入成功。

Codex 当前官方 Hook 文档列出 Bash、apply_patch、MCP 与其他本地函数工具；托管 WebSearch 不走该路径，write_stdin 不再次触发执行前 Hook。文档还注明 PreToolUse 的 ask 返回尚不受支持、MCP Hook 错误可继续执行，因此不能直接把本项目 ASK 枚举透传给客户端。适配要实现明确暂停/阻断与独立审批恢复，并验证故障时的行为。以上是文档能力核对，尚非安装版本实测。

Claude Code 的 PreToolUse 可覆盖内置与 MCP 工具，但部分 Hook 超时或错误不阻断，且 @ 文件引用不触发这个工具 Hook；应按路径单独处理。两者均不能只因拥有 Hook 就宣称整个执行环境已受强制控制。

## 评测与自研 Agent 扩展（后续）

以下“可适配”是基于官方扩展接口的工程判断，不等于本项目已支持所有版本；实现前需要锁定精确版本。

| 对象 | 官方可用接入点 | AgentSentry 适配方向 | 当前验收 |
|---|---|---|---|
| LangChain / LangGraph | MCP adapters、工具拦截器；LangChain Agent 的模型/工具 middleware | 按评测需要接入；自定义 LangGraph 节点需显式覆盖 | NOT_RUN |
| CrewAI | MCP 工具集成、工具执行前后 Hook | 复用通用客户端，映射 Hook、任务、Memory 和委派；处理 Hook 异常放行语义 | NOT_RUN |
| AutoGen | McpWorkbench 和工具适配器，支持 stdio / Streamable HTTP | 先验证 MCP；再包装运行时消息、工具、Memory 与跨 Agent 事件 | NOT_RUN |
| Google ADK | MCPToolset、模型/工具执行前后 callback | 将 callback 与 session、工具结果和 Memory 操作关联 | NOT_RUN |
| 自研 Python / TypeScript Agent | 若可替换工具执行函数或调用网关 API | 按统一协议适配；不要求框架原生支持 MCP | NOT_RUN |

官方依据：[LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp)、[LangChain Agent middleware](https://docs.langchain.com/oss/python/langchain/agents)、[CrewAI MCP](https://docs.crewai.com/en/mcp/overview)、[CrewAI Tool Hooks](https://docs.crewai.com/en/learn/tool-hooks)、[AutoGen MCP](https://microsoft.github.io/autogen/stable/reference/python/autogen_ext.tools.mcp.html)、[ADK MCP](https://adk.dev/tools-custom/mcp-tools/)、[ADK callbacks](https://adk.dev/callbacks/types-of-callbacks/)、[Claude Code Hooks](https://code.claude.com/docs/en/hooks)。本次仅核对接口文档；这些框架未安装到核心服务环境，也未调用模型 API。

两个需要在适配中验证的具体风险：CrewAI 文档说明普通 Hook 异常可能被吞掉并继续执行，应转换成其明确阻断结果；Claude Code 文档说明部分命令/HTTP Hook 的超时或错误不会阻断，且 `@` 文件引用不触发 PreToolUse。它们说明覆盖范围和故障行为必须按接口逐项验证，不能把“提供 Hook”直接等同于强制边界。对应依据见上表官方 Hook 文档。

## 不能接入或不能完整控制的情形

1. 封闭托管 Agent 只提供“提交任务/取得结果”，不允许自定义工具、MCP、执行前 Hook 或控制执行环境：无法把内部工具执行接到本项目网关；最多检查外部输入/输出。
2. 客户端允许 MCP，但内置终端、浏览器、文件、插件或服务端执行无法替换或禁用：可以接入 MCP 部分，不能声明整套 Agent 已受控。
3. 只有执行后日志或 tracing callback：可以审计，无法在副作用发生前阻断。
4. 未开放的 Memory、上下文或内部推理：不能声明已完整捕获；不以获取私有思维链作为接入条件。
5. 仅支持旧 SSE 或不同认证/传输能力的客户端：当前 stdio / Streamable HTTP 入口未必直接兼容，需要额外适配和测试。

是否能接入由具体版本、扩展接口、部署方式和权限决定，不按产品名称建立永久“不能接入”黑名单。

## 产品适配需要补充的架构

现有 `/api/tools/call` 会执行动作，不能把它直接当作原生工具 Hook 的“允许/拒绝查询”，否则可能先在网关执行一次、客户端随后再执行一次。已新增 `/api/hooks/evaluate`、`/api/hooks/claim`、`/api/hooks/report`：评估/独立审批只授予 ready，claim 原子消费一次执行许可，由客户端自行执行并回报；网关不会执行该原生工具。客户端回报明确标记 `execution_verified=false`，不能作为可信执行收据。

两条路径使用同一策略内核：原生 Bash/文件工具经 Hook 决策后由客户端执行并回报；受控 MCP 工具由网关决策和执行。原生路径需要额外验证参数/资源变化、审批绑定及执行位置；没有受限执行环境时仅声明已覆盖的 Hook 控制。任意 shell 命令不能靠命令名或字符串匹配假装已获得精确副作用语义，不支持的语义应明确限制。客户端可见数据才可上报，任务授权不得从不可信工具文本中提取并自动授予。

5090 承载安全服务和测试环境。Hook 应安装在实际 Agent 运行的主机；Agent 在用户电脑运行时，连接远程网关并不会自动迁移它的文件与终端执行位置。配置包必须标清本地、SSH 远程和桌面端的支持范围。

## 历史框架工作量估算（不作为产品排期）

以下保留上一轮针对可修改框架的估算，不适用于 Codex / Claude Code 完整产品适配。产品工作量需先核验固定版本、原生工具路径、ASK 恢复和旁路约束后重估；不能把改配置的耗时当作完整防护验收耗时。不同层次包含重叠工作，不可直接相加。

| 范围 | 粗估工作量 | 验收内容 |
|---|---|---|
| MCP 最小演示 | 0.5–2 人日 | 配置、授权 session、正常调用、阻断、一次审批恢复 |
| 首个完整框架适配 | 5–10 人日 | 自动上下文、工具结果、Memory/委派中实际使用的路径、审批暂停恢复、幂等与故障回归 |
| 通用客户端成熟后的相近框架适配 | 2–5 人日/框架 | 事件与 schema 差异、版本锁定、同一套契约测试 |
| 包含宿主工具的强制隔离 | 额外 1–3 周或更多 | 文件/网络/凭据边界、子进程、旁路和干净部署测试；受部署环境约束 |

主要复杂度来自操作语义、审批恢复、Memory/跨 Agent 来源关联以及阻止绕过，协议握手只占其中一部分。单卡 5090 不决定框架兼容性，模型推理资源需按实际模型另外评估。

## 下一阶段实施顺序

按用户明确的产品定位，A02 优先交付 Codex / Claude Code 接入。原框架优先路线已被本节替代；原 96 人日保留为历史基线，新增接口和产品验证的剩余工作量在 Spike 后重估。

1. **Codex / Claude Code 能力 Spike**：固定版本和运行主机，验证 Hook schema、拦截点、超时/断网、配置启用及原生工具旁路；两者同属首批目标。
2. **共用 Hook 桥接层**：补只评估不执行的接口、客户端事件归一化、任务/session 绑定、ASK 暂停恢复、原生执行结果关联；保留 MCP 网关执行路径。Agent 不持有操作员审批凭据。
3. **产品接入包与真实 E2E**：先以 Codex CLI 建立可重复测试，再完成 Claude Code；Codex 桌面端单独验证。交付安装/卸载配置、运行位置说明、覆盖表和证据，用户无需迁移到其他 Agent 框架。
4. **执行隔离与扩展**：与 A04/A07 验证文件、网络、凭据和子进程边界；之后再按评测需要考虑框架适配及其他编程 Agent 产品。

每个产品适配验收至少证明：ALLOW 仅执行一次；ASK 批准前副作用计数不增加且批准后不重复；BLOCK 副作用计数为零；已覆盖上下文自动上报并关联返回；超时/取消/网络错误不导致放行或重复副作用。原生工具和 MCP 分开提供实际证据，Memory/委派仅在实现并验证后标为覆盖。宣称强制控制还必须补凭据、网络、文件和子进程旁路测试。最新工程测试与 20 条黄金回归不能代替这些产品验收。

## 当前原生桥接覆盖（native-posix-2）

支持 Read、Write、Edit、逐目标检查的 apply_patch，以及字面量 `cat` / `pwd`、精确的 `cat ASCII路径 | head -n 正整数`（1–9999行）。拒绝其他脚本/管道、shell 展开、重定向、后台执行、符号链接、受控根外路径及 `.codex` / `.claude` / `.agents` 控制文件。cwd 必须与网关实际文件工作区完全一致；不接受客户端自称的本地/远程映射。此限制意味着它还不能承载常规编程 Agent 的完整终端工作流。

`scripts/prepare_client_hooks.py` 只生成受保护配置包，不修改全局客户端设置。默认 PreToolUse 全匹配，未知工具（含 MCP）拒绝；MCP 网关作为另一条已验证执行路径保留，尚未宣称两条路径已在真实客户端完成组合验收。桥接 UserPromptSubmit 只上报上下文，不能自动创建任务或扩大权限。

34 条 Hook 回归覆盖单次 claim、审批前无执行、参数/文件/Intent 漂移、拒绝/重启/并发/结果重放和有界只读管道，以及两种事件格式的真实 HTTP 与独立命令进程。这些回归使用事件夹具；真实 Codex Spike 见下节，Claude 实际会话仍未运行。安装失败或宿主不触发 Hook 的旁路仍需宿主隔离和客户端专项验收。

## 真实 Codex CLI Spike

5090 上 Codex CLI 0.154.0-alpha.6.2 使用本地 Qwen7B Responses 服务，忽略用户配置、保留只读沙箱，仅启用经过审查的本项目 Hook。真实用户输入和 PreToolUse 已到达网关；模型请求 `cat README.md | head -n 1`，旧适配器拒绝并把结果传回客户端，未产生 claim。详见 [实测证据](../evidence/codex-cli-spike.json)。

已根据实际命令补精确只读管道语法，9个新回归覆盖允许、凭据/越界、伪装引号、重定向、展开、额外管道和命令拼接。真实 Codex ALLOW/ASK 完整链路仍未验收：独立沙箱探测返回 bwrap namespace 权限错误。既有登录还在本地 provider 下自动尝试刷新并返回地区限制403；未重试或修改限制。后续 Spike 遇到既有账户 auth 文件即停止，要求独立配置的本地测试账户/环境。

一次性 Hook 信任使用官方面向已审查自动化脚本的机制，没有保存全局信任修改。此结果仅证明固定版本上的实际执行前阻断事件，不证明整套产品兼容或全面强制隔离。
