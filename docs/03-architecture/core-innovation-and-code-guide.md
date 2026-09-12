# 核心机制、创新边界与代码导读

日期：2026-09-13。本文以当前主线实现为准，隔离候选单独标明。服务器工程路径为 `5090:/root/autodl-tmp/AgentSentry`。

当前系统的核心定位是面向编程 Agent 的工具执行安全层：把任务权限、候选动作、上下文风险和审批条件组合成可检查、可执行、可追踪的控制流程。以下属于已实现的工程机制；独立算法原创性和公开基准综合增益尚未证明。文献对照见[创新性评估](../05-validation/novelty-and-sota-assessment-2026-09-13.md)，低代码重复率不构成新颖性证明。

## 1. 任务契约与动作语义统一

`IntentIR` 表示任务允许的作用范围、副作用、权限上限和明确禁止项；`ActionIR` 表示实际工具、资源、参数摘要、副作用和风险标签。工具先被规范化，再由策略引擎决定 ALLOW、ASK 或 BLOCK。文件修改、网络发送、委派和记忆写入可以沿同一控制流程检查。

阅读入口：[数据模型](../../src/agentsentry/schemas/models.py) → [任务解析与对齐](../../src/agentsentry/intent/contracts.py) → [工具规范化](../../src/agentsentry/adapters/registry.py) → [策略引擎](../../src/agentsentry/policy/engine.py)。主线 `resolve()` 使用保守模板及正则，并非通用语义理解模型；这也是未明确授权动作容易触发 ASK 的原因。

## 2. 执行前检查与硬性权限约束

`Runtime.call()` 负责规范化、策略检查、审计和动作状态转换，获准后才进入工具分发。`Engine.decide()` 优先处理无效资源、静态权限上限、不可覆盖的阻断策略和明确禁止项；人工批准也必须通过这些检查。策略解析、扫描或必要审计失败时阻断执行。

阅读入口：[运行时 call / _decision / _execute](../../src/agentsentry/gateway/runtime.py)、[策略 DSL](../../src/agentsentry/policy/dsl.py)、[默认策略](../../policies/default.aspolicy)。例如，带 SECRET 标签的数据外发或委派会触发硬阻断，风险记忆写入可被隔离。

## 3. 审批绑定具体动作，限制重放与资源替换

`_binding()` 把用户、会话、权限与任务快照、策略版本、完整 ActionIR 和运行代次绑定起来，`_sign()` 使用 HMAC 签名并绑定到期时间。`approve()` 重新解析当前资源、比较绑定并再次执行策略检查，随后以原子状态转换消费审批。存储层 `claim()` 限制同一动作重复分发；恢复时将不确定的执行状态保留为 unknown，避免直接重试副作用。

阅读入口：[运行时 _binding / _sign / approve](../../src/agentsentry/gateway/runtime.py)、[存储 recover / claim](../../src/agentsentry/trace/store.py)。这是针对审批后参数或资源变化、重复执行的具体控制机制，不等于所有外部工具都具备事务回滚或端到端 exactly-once 保证。

## 4. 风险来源跨上下文、记忆和委派保留

扫描生成风险标签及来源引用。记忆记录保存标签、来源和原会话，读取时检查归属与隔离状态并重新扫描；创建子会话时收缩权限范围，继承禁止项、上下文标签及来源引用。`trace()` 生成调用关系、显式数据引用和上下文暴露三类边，供检查决策依据。

阅读入口：[上下文扫描](../../src/agentsentry/context/scanner.py)、[运行时 create_session / scan / _memory_write / trace](../../src/agentsentry/gateway/runtime.py)。这提供可观察来源的追踪，不代表完整追踪了模型内部信息流，也不构成因果归因证明。

## 5. 主流 Agent 的接入层

[MCP 入口](../../src/agentsentry/gateway/mcp_server.py) 把受控工具调用接到运行时；[原生 Hook](../../src/agentsentry/gateway/native_hooks.py) 提供候选动作检查、领取许可和结果回报流程，面向 Codex / Claude Code 的有限文件工作流。Hook 自身不执行候选工具，客户端回报也不是可信执行器收据。

接入层复用同一权限和策略机制，是产品工程价值。当前支持范围有限，真实 Codex / Claude Code 全流程、宿主旁路和隔离验收仍未完成，不能描述成已覆盖所有原生工具。

## 6. 研究候选：任务计划与动态参数证据

隔离版本[task-plan-v1](../../artifacts/development/task-plan-v1/src/agentsentry/intent/task_plan.py) 的 `TaskPlanner.prepare()` 仅根据原始用户任务、操作权限及已审阅工具目录生成计划；`record()` 记录获准执行的观察；`_evidence_matches()` 校验关键参数的来源、JSON 指针、精确引用和受限数值运算；`review()` 将通过核验的结果绑定为临时精确动作契约，再交给常规策略引擎。

研究假设是：允许外部数据提供任务必需的动态参数，同时约束其改变操作目的、范围和次数的能力。例如，付款金额可能来自账单，但是否允许付款仍应受原任务和权限约束。参数确实来自某段数据，并不证明该数据真实，也不单独证明操作获得授权；候选仍依赖模型的语义核验。

该机制未进入主线。真实模型小样中，防护组仅 5/8 条有效，正常任务成功率从 4/4 降为 2/4；存在结构化协议失败和额外日期约束问题。[小样评审](../05-validation/task-plan-pilot-review.md)记录了失败，不支持宣称该候选已经改善整体效果。

## 阅读顺序与证据边界

建议先读 `runtime.py:383` 的统一入口，再读 `contracts.py:75`、`registry.py:109` 和 `engine.py:13`，之后检查审批、来源追踪和接入层。研究候选最后阅读，避免将候选能力误认为活动版本能力。

已完成的 InjecAgent v4 配对中，已判定的模拟攻击执行成功从 8 次降至 0 次，但防护组仍有 52/1054 条未知，保守 ASR 上界为 4.93%；AgentDojo 正常任务成功从 84/97 降至 59/97。当前能说明存在执行阻断作用，也存在明显效用代价，综合 benchmark 尚未验收。[公开验收报告](../05-validation/public-benchmark-report.md)。
