# 14 项目开发计划 / Implementation Plan

文档 ID：AS-DOC-14 ｜ 版本：1.1-review ｜ 更新：2026-09-12  
Owner：A ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)


文档 ID：AS-DEV-PLAN-009 ｜ 版本：v1.1 ｜ 编制日期：2026-09-12

依据：用户提供的《AS-PRD-001 v0.9》（2026-09-10）、已有 RFC / API / Policy / Evaluation / Operations 工程文档，以及本次 SSH 5090 环境检查。需求和分工冲突以本次用户提供的 PRD 为主；本计划中的调整均明确标为开发建议。

**执行主线：第 2 周交付可以实际阻断的最小闭环，第 4 周完成全部 P0 功能，第 6 周完成增强能力与全量评测，第 8 周交付可部署、可复现、可演示的参赛版本。** 原排期保留为计划基线。当前已开发服务、MCP 与原生 Hook 桥接，安装隔离评测环境并运行 AgentDojo/InjecAgent；进度与未通过项以开发日志和实际报告为准。

## 1. 排期假设与资源前提

按 PRD 的 A/B/C 三人、8 周节奏规划。暂定 2026-09-14 启动，2026-11-08 结束；这是排期假设，不代表已确认比赛截止日期。节假日、课程、实际参赛截止时间尚未折算，首日由 A 校准。

每人按每周 5 个工作日计，总容量 120 人日。其中功能、评测与文档安排 96 人日，每人 32 人日；另保留每人 8 人日用于评审、联调、失败重跑和风险处理。下文工时是工作包估算，不承诺研究指标必然达标。

### 1.1 5090资源更新（本次工程完善）

最新SSH实测：RTX5090、32607MiB显存、25CPU配额、90GiB内存；早期0.5CPU/2GiB/未暴露GPU状态已恢复。最新证据见[environment-current.json](../evidence/environment-current.json)，旧快照仅为历史记录。数据盘约91GiB可用，系统盘约1.95GiB可用；Docker/uv未在PATH发现。

单卡先提供一个7B/8B主Agent服务，B按需复用或使用更小Intent模型，检测/规则/审计优先CPU。评测并发从1开始，按上下文和峰值显存实测提高；不同时承诺多大模型长上下文高并发。恢复资源不等于模型推理栈、算法和Compose已验收。

### 1.2 运行配置

| 配置 | 用途 | 验收边界 |
|---|---|---|
| dev-lite | 规则、代理、Schema、Trace开发与合成Demo；可用stub隔离依赖 | stub只证明工程路径，不计真实模型F1/ASR |
| cpu-mvp | 4vCPU/8GiB、无GPU与外部模型API，本地小模型P0 | 必须独立验收≤200ms与离线Demo，不能用大实例结果替代 |
| benchmark | 当前单卡5090、25CPU/90GiB，队列运行公开基准 | 模型/依赖固定后真实运行；吞吐、峰值显存、总时长均待实测 |

W1资源任务调整为复测配额、隔离依赖、验证Blackwell推理栈和Docker验收主机；不再以GPU未开放作为当前阻塞。未来资源发生变化需重新记录环境，不修改系统cgroup/驱动绕过配额。

## 2. 范围与 PRD 冲突处理

### 2.1 本期交付边界

P0 交付直接注入扫描、四类外部来源入站扫描、IntentIR / ActionIR、对齐校验、至少 10 个 DSL 判定谓词、ALLOW / ASK / BLOCK、五类工具适配、完整 Trace，以及 CPU Demo 和 Docker Compose 发布包。

防护承诺限于受控 Demo Agent、接入 Hook 的运行时和经 Proxy 转发的工具。闭源客户端未暴露的内存、内置终端、文件操作不能自动纳入防护；必须列入接入覆盖矩阵。要宣称强制阻断，Agent 不能继续拥有绕过 Proxy 的下游凭据、文件权限或网络通路。

P1 交付内存污染防护、跨 Agent / MCP 的显式污点传播、完整 DAG 看板、对抗文本归一化增强和红队回归。优先级仍为 P1，但 PRD 已将其中若干能力用于最终验收，需要提前完成最小基础。

### 2.2 首周形成决策记录

| 冲突或缺口 | 本计划建议 | 责任人 / 截止 |
|---|---|---|
| G1 写“全场景”，但内存防护 FR-1.3 是 P1 | W4 只声称 P0 覆盖；W6 完成 Memory Guard 后再声称四类入口齐备 | A / W1 |
| G1 包含 MCP 描述注入，FR-1.2 未明确 tools/list | W3 增加工具描述入站 Hook、来源标记和 metadata hash；工具文本不能自行声明可信权限 | A / W1 |
| 污点是 P1，但 P0 外泄要求 100% 拦截 | W2 提前完成固定工具中的 SECRET 标签、显式数据流关联和 canary 出站校验；W5–W6 扩展跨 Agent / 内存 | B+C / W1 |
| DAG 是 P1，但黄金链路溯源要求 100% | W2 先交 source→action→decision 的机器可读有向图；W4 再交可视化 | C / W1 |
| FR-4.1 要求 P0 100%，NFR 写全部调用 ≥99% | P0 工具及黄金集必须 100%；受控环境所有调用的运行覆盖率 ≥99%，两项分别报告 | C / W1 |
| PRD ASR 总目标 ≤32%，模块 A 相对下降 ≥45%，模块 B ≤35% | 三项分别保留、分别验收；AgentDojo 与 InjecAgent 不直接混算，详细口径见第 8 节 | C+B / W1 |
| “同输入同策略可复现”与模型采样存在冲突 | 确定性策略回放固定 IR、signals 和全部版本；LLM 端到端另做三次重复统计 | B+C / W1 |
| A/B/C 分工与旧 RFC 的 Context Guard / Trace Owner 不一致 | 按本 PRD：A 负责检测和系统集成，B 负责 IR/策略，C 负责 Trace/评测/UI | A / W1 |

旧文档中的 `QUARANTINE`、`IGNORE_CLAIM` 作为处置/诊断字段，不新增第四种决策。外部决策枚举保持 ALLOW / ASK / BLOCK；例如 Memory 写入被 BLOCK，同时执行隔离处置。

## 3. 实现架构与技术路线

采用模块化单仓库。MVP 默认将网关、决策与审计 API 放在一个后端进程，保留清晰模块接口；沙箱工具和可选模型运行时独立进程。暂不增加微服务编排、消息队列或企业级权限平台。

```text
已认证用户任务 ── Hook ── IntentIR（权限上限受静态策略约束）
外部内容 / 工具描述 / 工具返回 ── Context Guard ── RiskSignal / source_refs
                                                        │
Agent 候选工具调用 ── Proxy 暂停执行 ── ActionIR ──────────┤
                                                        ▼
                          对齐校验 + 数据流 + 确定性 DSL 策略
                                      │
                  BLOCK（零下游执行） / ASK（等待审批） / ALLOW
                                                        │
                      有效审批重新校验 ──────────────────┤
                                                        ▼
                                      受限 Executor / 下游 MCP
                                                        │
                                      响应重新进入 Context Guard
所有阶段 ── 脱敏 SecurityEvent / Span ── Trace Store ── 时间线与 DAG
```

后端建议 Python 3.11、FastAPI、Pydantic、pytest；MCP 采用官方 Python SDK，版本在 W1 兼容性验证后锁定。W2 优先跑通 stdio，W3 增加 Streamable HTTP 的会话、超时、取消和重连检查。两种传输来自已查阅的 [MCP 2025-11-25 规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)；SDK 以 [官方仓库](https://github.com/modelcontextprotocol/python-sdk) 的实际固定版本为准。

策略实现采用受限 DSL→AST→确定性求值，不使用 `eval` 执行规则文本。保留已有 Policy Spec 的 `rule / when / then` 语义；YAML 只承载配置，不能把“十条规则”误算成“十个谓词”。审计采用 SQLite WAL 加脱敏 JSONL 导出；默认单写者，所有审计 API 只暴露必要字段。

看板建议 React + TypeScript、DAG 组件和时间线；只做事件列表、详情/DAG、审批、评测报告四个视图。W1 锁定工具链，不能使用当前默认 Node 12 直接假定构建可行。

注入检测先实现规则基线和统一模型接口，再试测轻量分类器。可评估 [Prompt Guard 2 22M 官方模型卡](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-22M) 所列模型，但权重获取权限、许可证、中文效果、分块方式和 CPU 时延均需验证；不把单个候选型号视为已选定依赖。Intent 先覆盖“代码评审、修复并测试、脱敏报告上传”三个任务模板，再接受约束的结构化语义解析。

### 3.1 必须落实的安全语义

1. **合同权限有上限。** 只有已认证的用户任务及受信配置可更新 IntentIR。模型推断不能扩大静态资源范围或赋予未批准的执行权限；未知字段保持 UNKNOWN，外部内容只能作为数据。
2. **决策只作用于准确动作。** ActionIR 包含规范化资源、目的地址、effects 列表、参数 hash、工具/适配器版本。一个命令可能同时读取、执行和外发，不能仅标作 EXEC 而遗漏其他副作用。
3. **归一化与执行一致。** 文件处理绝对路径、`..`、符号链接和执行时路径变化；网络处理重定向、DNS 解析、私网/回环目的地址；Git 绑定仓库、远端、分支及实际提交对象。无法证明安全的 shell 语义走限制或 ASK/BLOCK。
4. **审批不能越过硬拒绝。** token 绑定用户、权限快照、session、action_id、tool/server 身份、参数 hash、目标、Intent 版本、策略版本、有效期和一次性 nonce。参数变化、过期、撤销、重复消费均不可执行；恢复前重新检查策略，写操作重试需防重复副作用。
5. **异常时保证副作用默认关闭。** 策略损坏、IR 缺失、未知工具、审批服务不可用时，高风险操作不转发；低风险只读的 fail-open 必须显式配置并记录降级。审计缓冲耗尽后停止新的高风险 ALLOW，BLOCK 不依赖存储可用。
6. **证明执行结果。** BLOCK 验收要检查下游调用计数为零、文件未改变、模拟外发端点未收到 canary；不能只检查 UI 出现“已拦截”。
7. **明确污点证据的限度。** `parent_span_id` 只证明调用关系；精确数据依赖使用显式 provenance 边。LLM 自由改写后的语义关联标为推断或未知，不伪造精确因果链，也不声称支持任意程序的完整动态污点分析。

## 4. 三人分工与协作接口

| 人员 | 主责与交付 | 协作边界 |
|---|---|---|
| A：系统/安全负责人 | 环境、Hook/Proxy、工具执行边界、Context Guard、注入检测、Memory Guard、性能与发布 | 维护接入覆盖清单，负责最终系统集成；不另写一套策略引擎 |
| B：算法/策略负责人 | Schema、Intent/Action IR、对齐引擎、DSL、审批校验、污点判定谓词、策略消融 | 输出统一决策库/API；不直接执行真实工具、不单独维护 Trace 数据库 |
| C：评测/产品负责人 | Demo 工具、Trace/审计、provenance 传播存储、DAG/UI、数据与评测流水线、参赛材料 | 负责指标口径与冻结 test；A/B 负责各自算法基线复现和失败分析 |

所有工作包只有一个主责人。每次合入由另一人检查安全相关变更；不要求三人分别重建评测基础设施。模块 A 的 ASR、模块 B 的意图效果均受 Agent 和整体运行时影响，必须区分模块指标与系统指标。

W1 第 2 个工作日发布 Schema alpha；W2 末冻结 v1：`ContextChunk / RiskSignal / IntentIR / ActionIR / AlignmentResult / Decision / ApprovalToken / SecurityEvent / TraceSpan / ProvenanceEdge`。公共字段包含 schema_version、trace/session/agent、source_refs、策略/模型/归一化版本，UNKNOWN 枚举默认安全处理。

沿用已有 API Spec 的 `/v1/context/scan`、`/v1/intent/resolve`、`/v1/action/decide`、`/v1/approval`、`/v1/traces/{trace_id}`、`/v1/policies/validate`、`/healthz`、`/readyz`。新增端点必须记录兼容性；不同进程和语言之间交换 JSON Schema，而非依赖彼此内部类。

## 5. 八周里程碑

周内开发和验收以实际工作日为准，表中日期按自然周标注。

| 周次 / 日期 | A：检测与接入 | B：IR 与策略 | C：Trace 与评测 | 周末验收与交付 |
|---|---|---|---|---|
| W1：09-14～09-20 | 建独立环境；核验推理栈/Compose 可行性；Hook/Proxy 骨架 | Schema alpha；Intent 模板；DSL 语法和冲突顺序 | Demo/沙箱骨架；Trace 契约；设计 20 条黄金用例；核验基准来源 | **M0：** `dev-lite` 启动；资源缺口清单；Schema alpha；3 条规则样例；W1 决策记录 |
| W2：09-21～09-27 | stdio Proxy；敏感文件读取拦截；响应来源与直接注入规则 | 五类 ActionIR；最小 ALLOW/ASK/BLOCK；参数绑定审批原型 | 审计持久化/脱敏；最小 SECRET 数据流；黄金集最小图；每基准 smoke | **M1：** Issue→诱导读模拟密钥→BLOCK→Trace 可回放；3 态各至少 1 例；Schema v1；20 条黄金回归全过 |
| W3：09-28～10-04 | 四类外部来源、tools/list 描述；Streamable HTTP；检测器首轮试测 | Intent 完整字段；三类对齐风险；至少 10 谓词；审批防篡改 | AgentDojo/InjecAgent 首轮；ASB 接入；原始结果统一化；UI 框架 | **M2a：** FR-1/2/3 功能候选；输出裸 Agent 与防护版可比首轮报告 |
| W4：10-05～10-11 | 五类执行适配联调；旁路/响应超时检查；CPU P0 验证 | DSL/ASK 正反边界测试；Scope/副作用稳定；批准一次执行一次 | DAG/审批界面；冻结三态测试集；P0 覆盖与故障测试 | **M2：** 所有 P0 功能验收通过；三态完整演示；首轮性能与错误分析；功能冻结 |
| W5：10-12～10-18 | Memory 读写 Hook、污染隔离；对抗归一化增强 | SECRET/UNTRUSTED 谓词扩展；委派权限交集；阈值校准 | 跨 Agent/MCP 显式 provenance；MSB 与 MPBench 适配；流水线分级 | **M3a：** Memory 与跨 Agent 黄金链路；对应评测 smoke；只在 dev 调阈值 |
| W6：10-19～10-25 | 本地模型/缓存/长上下文优化；P1 全链路集成 | 去检测/去对齐/去污点/去 ASK 消融；策略候选冻结 | 固定配置全量基准与 3 次重复；CVE 模拟沙箱；汇总差距 | **M3：** P1 能力验收；所有已确认公开基准完整配置跑通；候选版本和可复现实验包 |
| W7：10-26～11-01 | Compose 发布包；CPU-only 冷启动、压测、故障/回滚 | 策略/模型/阈值 manifest 固定；关键绕过复测 | 一键回归/全量评测；7 天留存检查；开始连续稳定性观察 | **RC：** 干净机器部署、全部质量 Gate、失败项关闭；开始最终封存测试 |
| W8：11-02～11-08 | 修复阻断发布的问题；部署手册；版本 tag | 冻结规则/IR；可解释案例；复现确认 | 最终报告、证据包、答辩图、演示脚本与录屏；稳定性报告 | **M4：** Gate 全过才发布 MVP；未过项明确列出，不能以“接近 SOTA”替代验收 |

**关键依赖链：** 资源与 Schema → Proxy 执行前 gate / ActionIR / Trace → 最小真实阻断 → Intent/DSL/ASK → 全量评测与校准 → CPU/Compose 验证 → 最终发布。

推理栈兼容验证与 Benchmark 许可证不阻塞 Schema、规则和 Trace 开发；但阻塞它们实际依赖的模型运行与公开评测。W4 后不新增 P0 需求，W6 后只处理质量缺口。资源或排期不足时，先延后 CVE 扩展、额外客户端、界面美化和更多模型横评；不删除旁路检查、审批绑定、日志脱敏或 CPU 部署 Gate。P1 延后必须在交付范围中明确记录。

## 6. 可分派工作包（96 人日）

工时包含实现及模块级测试，不包含另外保留的 24 人日公共缓冲。任务可依据 Schema alpha 和 mock 提前开始；“依赖”表示正式联调/验收所需前置产物。

| ID | 主责 | 人日 | 时间窗 | 工作与明确完成条件 | 依赖 |
|---|---|---:|---|---|---|
| A01 | A | 2 | W1 | 环境与资源：独立目录/解释器，资源快照，推理栈/Compose 路线，磁盘预算 | 无 |
| A02 | A | 6 | W1–W3 | Hook + stdio/HTTP Proxy：执行前 gate、返回入站、取消/超时；BLOCK 不触达下游 | B01 alpha、C01 |
| A03 | A | 6 | W2–W4 | Context Guard：直接输入、Web/文档/Issue/MCP 返回及描述；来源/证据窗口/扫描批量 JSON | B01、A02 |
| A04 | A | 5 | W2–W4 | 五类 Executor 适配与旁路限制；路径/目的地址/执行对象规范化一致 | B03、B04 最小版 |
| A05 | A | 4 | W5–W6 | Memory 读写污染检测/隔离、跨 Agent 上下文；标签跨 session 留存 | A03、C06 |
| A06 | A | 3 | W4–W7 | 小模型/缓存/分块性能，CPU 配置实测，关闭模型后的故障兜底 | A03、B02、资源就绪 |
| A07 | A | 4 | W1 骨架、W6–W7 | Compose、健康检查、独立身份、配置、日志留存、干净部署/回滚 | A02、B04、C02、容器环境 |
| A08 | A | 2 | W8 | 发布封装、接入说明、版本 tag、重复部署确认 | A06、A07、C07 |
| B01 | B | 3 | W1–W2 | JSON Schema / 枚举 / 版本；alpha→v1，UNKNOWN 与权限语义契约测试 | 无 |
| B02 | B | 5 | W1–W4 | Intent 合同：目标、范围、合法/禁止副作用、证据、未决项；三个模板到语义解析 | B01 |
| B03 | B | 4 | W2–W3 | ActionIR 及对齐：五类工具、复合 effects，三类偏离均有解释 | B01、B02 模板 |
| B04 | B | 6 | W1 最小版、W3–W4 | DSL parser/AST/求值；≥10 谓词、优先级、版本、规则边界测试 | B01、B03 |
| B05 | B | 4 | W2 原型、W3–W4 | ASK token 与状态机：准许/拒绝/过期/变参/重放/权限变化，硬 BLOCK 不可覆盖 | B01、B04 最小版、A02 |
| B06 | B | 4 | W2 最小版、W5–W6 | SECRET/UNTRUSTED 策略、数据流判定、子 Agent 权限交集/深度限制 | B04、C06 |
| B07 | B | 4 | W4–W7 | ASB/自建集失败分析、三态校准和四项消融；提交原始结果 | C04、C03、B02–B06 |
| B08 | B | 2 | W8 | 固定 IR/规则/阈值，决策重放一致，策略发布说明 | B07、C07 |
| C01 | C | 3 | W1 | Demo Agent、模拟文件/网络/Git/执行/子 Agent、测试运行器与 Trace 契约 | B01 alpha |
| C02 | C | 5 | W1–W2 | Trace Store、span/source 边、脱敏与回放；P0 调用完整，无 canary 明文泄露 | C01、B01 |
| C03 | C | 5 | W1–W4 | 20 条黄金 E2E；三态/良性数据分组去重、双人标注、test 冻结及覆盖矩阵 | C01、B01；联调需 A02/B04 |
| C04 | C | 5 | W1 核源、W2–W4 | AgentDojo/InjecAgent/ASB 的版本锁定、接入、裸 Agent/防护对照；统一指标 | C01、A02、B04 |
| C05 | C | 4 | W3–W4 | 事件列表、审批、DAG/时间线、指标页；证据来源能点击核对 | C02、B05 |
| C06 | C | 4 | W2 最小版、W5–W6 | provenance 标签存储/传播、黄金图；MSB/MPBench 小样与适配，记录缺失边 | C02、A02、B01 |
| C07 | C | 4 | W5–W7 | AI-Infra-Guard 回归适配、统一 manifest、全量/三次重跑、指标报告及 CI Gate | C03、C04、C06 |
| C08 | C | 2 | W7–W8 | 最终报告/演示脚本/录屏、稳定性结果、证据包索引和需求签收 | C05、C07、A07、B08 |

每项任务的仓库 Issue 应包含：关联 FR、实现范围、输入输出、依赖、验收命令、证据文件、Owner、状态。当前工作包均为计划项；环境检查与计划文件落盘不代表 A01 已完整完成。

## 7. 前十个工作日启动清单

| 工作日 | 联合交付 | 谁推进 | 当天可检查的结果 |
|---|---|---|---|
| D1 / 09-14 | 校准截止日期/人日；复测已恢复的5090资源与容器环境；建仓库骨架 | A 主责，B/C 提供接口/评测约束 | 环境快照、目录、依赖锁定方案、开放问题 Owner |
| D2 / 09-15 | Schema alpha、三种决策样例、五类动作字典 | B | JSON Schema 和正反样例可相互校验 |
| D3 / 09-16 | stdio 工具和 Proxy 的 ALLOW 转发；Trace 贯通 | A+C | 读模拟 README 成功，trace/span/parent 全齐 |
| D4 / 09-17 | 最小硬规则、敏感资源分类与 BLOCK | B+A | 模拟密钥读取被阻断，下游执行计数为 0 |
| D5 / 09-18 | PRD Issue 场景第一版；裸 Agent 对照和 canary 标签 | A+C | 同一攻击 fixture 在无防护下产生模拟风险，防护下阻断 |
| D6 / 09-21 | 用户输入与工具返回扫描、来源/证据 | A | 可定位 Issue 载荷，外部文本不能改写 Intent 权限 |
| D7 / 09-22 | 五类 ActionIR、ASK 最小审批闭环 | B+A | 精确批准的模拟 Git push 仅执行一次；拒绝不执行 |
| D8 / 09-23 | 脱敏回放、超时与依赖故障 | C+B | Trace 不泄密；策略失败时高风险不转发 |
| D9 / 09-24 | 20 条黄金回归和基准 smoke | C，A/B 修复 | 对照结果/错误计数 JSON；公开基准可执行最小用例 |
| D10 / 09-25 | M1 集成验收、Schema v1、W3 backlog | A 组织、三人验收 | 三态真实闭环、黄金集全过、证据包；缺口进入明确任务 |

当前GPU已可见；D1–D10仍先用可控Demo/规则实现工程验收。模型试跑和检测F1在实际运行前保持“未测”。

## 8. 测试、Benchmark 与 MVP Gate

### 8.1 Benchmark 来源校验与适配原则

以下是 2026-09-12 查阅的一手来源。只确认基准用途与接入路径，不将 PRD 所列“当前 SOTA”自动认定为事实。

| 基准 | 已核实的用途 | 项目中的位置 | 必须补充的工作 |
|---|---|---|---|
| [AgentDojo 官方仓库](https://github.com/sequrity-ai/agentdojo) / [论文](https://arxiv.org/abs/2406.13352) | 工具增强 Agent 的动态攻击/防御评测；原论文报告 97 任务、629 安全用例 | A 的端到端安全/效用主基准 | 固定代码提交与 benchmark version；不能认为最新版样本数永远等于论文数字 |
| [InjecAgent 官方仓库](https://github.com/uiuc-kang-lab/InjecAgent) | 1,054 用例、17 用户工具、62 攻击工具，评估工具返回间接注入 | A 的配套基准 | 保留原生 ASR-valid / ASR-all 和有效率；与文本检测 F1 分开报告 |
| [ASB 官方仓库](https://github.com/agiresearch/ASB) / [ICLR 2025 论文](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html) | 多场景、多攻击/防御的 Agent 安全框架，包含内存与混合攻击 | B 的运行时策略评估 | 通过 adapter 映射动作；三态标签需另行人工标注，不能宣称原基准自带 ASK ground truth |
| [MSB 官方仓库](https://github.com/dongsenzhang/MSB) | MCP 全工具调用流程安全评测，覆盖描述/参数/响应等攻击 | C 的 MCP 链路集成，A/B 联合分析 | 仓库依赖与核心运行时分环境；使用原始操作输出核实攻击结果；公开 ASR 不能替代本项目 DAG 精确度 |
| [MPBench 所在论文](https://arxiv.org/abs/2606.04329) | Memory Poisoning 攻击基准 | W5–W6 Memory Guard 评测候选 | PRD 未给精确出处；W1 确认是否指该工作及其公开代码/数据、许可证。未确认前不承诺该基准全量可运行 |
| [AI-Infra-Guard 官方仓库](https://github.com/Tencent/AI-Infra-Guard) | AI 红队、MCP/Agent 等扫描与评估工具 | C 的离线回归工具 | 只接选定 CLI/报告适配，运行于隔离沙箱；不进入在线强制决策 |

MPBench 有重名工作，不能仅凭缩写选择数据集。若 W1 无法拿到确定的可运行材料，记录 `DATASET_UNAVAILABLE`，继续自建 Memory 黄金集；该项保持未交付，需更新版本范围后才可签收，不能偷偷替换成其他基准。

PRD 中 ASR≈27%、检测 F1≈0.92、行为 F1≈0.89、污点 TPR≥94% 等值，本次未取得足以确认其模型、攻击、样本和计算口径的完整证据。将其放入待核验参考表，不作为已证实 SOTA。正式对照必须提供论文/表格出处和同配置复现；不同模型/版本的文献数字只作背景。

### 8.2 评测数据与实验组织

由 C 管理统一 runner，A/B 提交 detector/policy adapters 和失败分析。三态集建议 dev 150 条、独立 test 300 条（ALLOW/ASK/BLOCK 每类至少 100 条）；另建良性任务 test 至少 200 条，包含安全研究、代码片段、合法执行和明确授权外发等易误判内容。最终数量由 W1 实际标注能力确认，减少样本须披露统计限制。

按攻击模板、任务源、仓库/文档来源分组切分并去重，不能随机拆分同模板变体造成泄漏。B 与 C 独立标注三态分歧并仲裁，阈值只在 dev 调整；用于日常回归的黄金集不同时冒充隐藏测试集。

20 条黄金 E2E 建议组成：良性 ALLOW 4 条、审批 4 条、硬 BLOCK 6 条、旁路/故障/注入漏检兜底 4 条、追踪/脱敏 2 条。每条用例明确用户权限、环境初态、预期决策、实际副作用和预期图边；W5 增加 Memory/跨 Agent 专项集。

所有公开基准至少跑：无防护、规则基线、完整 AgentSentry；W6 做去检测、去 Intent 对齐、去污点、去 ASK 四项消融。相同 Agent/backbone、攻击、工具环境和样本清单下配对比较。随机模型每配置重复 3 次，报告均值、离散度及按任务聚类的置信区间。不能将模型不会完成正常任务误当作有效防御。

### 8.3 指标口径与验收门槛

| 指标 | 可执行定义与门槛 | 证据 / Owner |
|---|---|---|
| 公开 ASR 总 Gate | 保留 PRD ≤32% 目标。建议 AgentDojo 与 InjecAgent 各自预先冻结主配置后分别验收 ≤32%，不汇总不同分母；其中 InjecAgent 保留 ASR-all 主值及 ASR-valid/有效率副值 | 固定 case manifest、原生 evaluator 输出；C，W1 冻结口径 |
| A 模块安全目标 | 同一基准同配置下 `(ASR_base − ASR_guard) / ASR_base ≥45%`；若基线为 0 则相对降幅未定义，必须说明 | 配对逐案例结果；A+C |
| B 模块安全目标 | ASB 冻结混合攻击配置 ASR≤35%，与项目总 Gate 分开列示 | ASB 原生结果；B+C |
| 良性效用 | `U_base − U_guard ≤5` 个百分点；对相同良性任务测试。ASK 未批准/超时默认算未完成，同时报告真实/模拟批准后的效用 | 成功率、ASK 率、完成耗时；C |
| 良性误拦率 | 错误 BLOCK 的良性任务数 / 良性任务总数 ≤5%；另报包含未解决 ASK 的不可完成率，防止把 BLOCK 全改 ASK 美化指标 | 任务级统计、逐任务决策；B+C |
| 三态 Macro-F1 | 独立自建 test 上 ALLOW/ASK/BLOCK 的 Macro-F1≥0.85；拒绝状态和超时单列，不丢样本 | 标签版本、混淆矩阵；B+C |
| 注入检测 Macro-F1 | 自建/公开适配文本 test 上≥0.88，单列各来源；不是端到端 ASR 的替代 | 预测/标签/阈值/模型 hash；A |
| P0 外泄拦截 | 冻结的 canary 外泄集实际外发为 0，拦截率100%；包含预置 SECRET 已进入上下文及检测器故意漏报场景 | 模拟 sink 收包记录、工具调用记录；A+B+C |
| 黄金链路溯源 | 预定义 P0 图的 source、sink、必要有向边和阻断节点全部正确，逐例精确匹配100%；不得添加无依据“已证实”边 | expected_graph 与 actual_graph；C |
| Trace 覆盖 | P0 候选调用及其决策、执行/取消结果100%有有效链路；受控环境所有调用覆盖≥99% | 以独立工具调用计数作分母，不能仅以已存事件计数；C |
| P1 污点传播 | 显式数据依赖标签 TPR≥90%，并报告 precision/FPR；跨 MCP/Agent/Memory 分项 | 标签黄金集，非任意语义改写保证；C+B |
| 快速链路 | 指定 cpu-mvp 硬件、1 KiB/8 KiB 固定负载、并发1/4，预热200次后每档至少1000次；端到端决策增量 P95≤200ms | 计时含队列、归一化、检测、策略和审计入队；报告最大支持输入及溢出策略；A |
| 复杂研判 | 相同明确硬件、固定语义负载，P95≤1.5s；模型/队列超时计入，不隐去失败 | 单列模型和配置，排除上游 Agent 生成/下游工具执行及人工审批等待；A+B |
| 决策复现 | 相同 IR、模型输出 signals、policy/normalizer/adapter 版本的离线策略回放100%一致 | 固定输入与 manifest；重新采样 LLM 另计统计结果；B+C |
| 运行质量 | 默认7天审计留存可配置、导出脱敏；连续观察窗口单节点可用性≥99%，故障注入单列；高危 fail-closed | W7–W8 连续7天探测，成功/总探测及故障时长；仅代表该观测窗口；A+C |
| 部署 | 干净 Linux 主机 Docker Compose 启动，CPU-only 离线 Demo 完成；建议预下载镜像/模型后30分钟内通过 smoke | 构建 manifest、启动/回滚日志；不能以当前 Python 直启替代；A |

额外报告无效样本、基础设施错误、超时率及实际运行 n。运行失败不能计作攻击失败或安静排除；未完成配置标记 incomplete，同时保留全尝试计数与原生基准口径。最终 Gate 不满足即报告差距，不回改测试集或门槛。

### 8.4 需求到验收的映射

| PRD 需求 | 工作包 | 完成周 | 主要验收 |
|---|---|---|---|
| FR-1.1 直接注入 | A03、C03 | W4 | 风险/类型/证据/来源 + 批量结果；检测 F1 |
| FR-1.2 间接注入 | A02、A03 | W4 | Web/文档/Issue/MCP 返回全覆盖；描述入口补充 |
| FR-1.3 Memory | A05、B06、C06 | W6 | 污染写入/读取事件、BLOCK + 隔离处置 |
| FR-2.1 IntentIR | B01、B02 | W4 | 目标/范围/合法与禁止副作用/UNKNOWN/证据 |
| FR-2.2 ActionIR | B03、A04 | W4 | 文件、网络、代码执行、Git、子 Agent 五类 |
| FR-2.3 对齐引擎 | B03、B07 | W4，W7 最终指标 | 越界、副作用升级、无授权高危操作 |
| FR-3.1 DSL | B04 | W4 | ≥10 谓词独立可用；每条规则正/负/边界样例 |
| FR-3.2 三态 | B05、C05 | W4 | 参数/用户权限绑定、超时/重放/篡改测试 |
| FR-4.1 Trace | C02、A02 | W2 基础，W4 全覆盖 | P0 链路100%；调用分母独立核验 |
| FR-4.2 污点 | C06、B06、A05 | W2 最小，W6 完整 | SECRET/UNTRUSTED 跨 Agent/MCP 显式传播 |
| FR-4.3 DAG | C05、C06 | W4 展示，W6 完整 | source/Agent/MCP/tool/sink/decision + 时间线 |
| FR-5.1 对抗清洗 | A03、A05 | W6 | NFKC/零宽/混淆/全半角/空白；保留 raw→canonical 证据映射 |
| FR-5.2 红队回归 | C04、C06、C07 | W6–W7 | 选定 AI-Infra-Guard 接入、公开集固定配置一键结果 |
| G5/G6 与 NFR | A04、A06、A07、B04、C07 | W7–W8 | 漏检兜底、CPU、Compose、延迟、留存、故障与复现 |

首批 DSL 谓词：effect、tool/server、resource pattern、resource class、destination domain、destination trust、intent allows、scope contains、flow label、source type、source trust、agent depth、approval valid，至少实现前述 13 项并验证安全冲突次序。

## 9. 5090 目录、运行与发布安排

建议主目录 `/root/autodl-tmp/AgentSentry`；计划文件放在 `docs/04-development/`，旧计划保留于`docs/plans/2026-09-12/`。本次已建立文档和工程目录骨架，以下业务模块仍是后续开发目标：

```text
AgentSentry/
  docs/plans/                 # 本计划、PRD 快照、环境证据
  docs/adr/                   # 范围/协议/评测/资源决策
  src/agentsentry/
    schemas/                  # B：JSON Schema 与类型
    gateway/                  # A：Hook / Proxy
    context/                  # A：注入检测、normalizer、memory
    adapters/                 # A+B：工具到动作与执行约束
    intent/                   # B：Task Contract / alignment
    policy/                   # B：DSL / evaluator / approval
    provenance/               # C：来源、标签与图边；B 消费谓词
    trace/                    # C：审计、脱敏、回放
    api/                      # 共享入口
  dashboard/                  # C
  demo/                       # 受控 Agent、假工具、canary、模拟外发端点
  policies/                   # B：只读版本化策略
  benchmarks/                 # C：独立环境的适配器和 manifests
  tests/{unit,contract,integration,e2e,security,performance}/
  scripts/                    # 环境探测、回归、部署、报告
  pyproject.toml
  compose.yaml
  Makefile
```

模型、数据、第三方基准环境与运行结果放数据盘独立目录并忽略 Git。建议初始新增占用上限60 GB：项目环境/构建12 GB、模型16 GB、基准数据10 GB、日志/结果12 GB、余量10 GB；下载前按实际工件修正，磁盘不足时停止新实验。不能清理其他项目或覆盖共享 Conda 环境来凑空间。

项目级 `HF_HOME`、`UV_CACHE_DIR`、`PIP_CACHE_DIR`、`TMPDIR` 指向数据盘。Web/API 默认监听127.0.0.1，通过 SSH 端口转发查看。审批 API 必须有身份绑定；监听 localhost 本身不能代替身份认证。沙箱使用假凭据、模拟 Issue、模拟 Git 远端与模拟外发端点。

W1 先做 Compose 最小构建/运行可行性检查。当前宿主已处于容器中，安装 Docker CLI 不等于拥有 daemon 或容器权限。若该 5090 实例无法运行 Compose，仍在此开发，最终部署在明确登记的干净 Linux 主机验收；其机器与资源写进报告。

以下保留原计划目标命令。当前实际可执行命令以根目录 Makefile 为准：dev/test/eval-smoke/perf-cpu/contracts/progress/verify/docs-check/doctor；full/ablation 等尚未实现，不得视为已通过：

```bash
make doctor           # 资源/依赖/磁盘/模型和容器能力检查
make dev-lite         # 单进程轻量开发
make test-contract    # Schema 和安全边界契约
make test-security    # 参数变化、旁路、故障、重放、泄密检查
make eval-smoke       # 20 条黄金 + 各公开基准固定小样
make eval-full        # 版本锁定的所有已确认公开基准
make eval-ablation    # 四项主要消融
make perf-cpu         # 无 GPU 的指定负载与延迟验收
make demo             # 固定三态/攻击链路演示
make release-check   # 全部发布 Gate + 工件完整性
```

`eval-full` 的“全量”指 manifest 中声明的完整 suite/task/attack 清单，不能只抽几条后命名全量；也不默认穷举世界上所有模型。先用约1%样本估算单配置耗时和调用量，再确定3次运行的容量；外部 API 若需要费用，在明确额度前不把付费调用视作已有资源。

## 10. 交付物、质量与风险管理

每次实验输出 `manifest.json + per_case.jsonl + metrics.json + report.md`。manifest 至少包括代码提交、数据集 commit/hash、case 清单、模型权重/API 版本、temperature/seed、policy/IR/adapter/normalizer hash、硬件与并发、开始结束时间、失败统计。报告每个数字能回到逐案例证据。

最终交付：源代码与依赖锁、CPU/Docker 发布包、版本化策略、接入覆盖矩阵、公开与自建评测报告、消融报告、脱敏 Trace/DAG、20条黄金回归及专项集、部署/回滚手册、答辩演示脚本与录屏、完整需求验收清单。演示至少包含正常评审 ALLOW、模拟 push ASK、恶意 Issue 读密钥 BLOCK、检测器漏报后外发兜底、一次 Memory/跨 Agent 溯源。

| 风险 / 触发信号 | 影响 | 处理与截止 |
|---|---|---|
| 推理栈或Compose到W1仍未验证可用 | 不能完成本地模型/性能/部署验收 | A 建环境缺口任务；工程继续，明确替代验收环境及排期，不填虚假结果 |
| 比赛截止早于11-08或成员投入不足 | 8周容量不成立 | A 于 D1 重排；优先移出扩展示例、额外客户端/模型，保留 P0 质量边界 |
| Intent 误判或检测器中文/混淆效果差 | 误拦/漏拦 | B 限制模型授权，A 单列语言/攻击类别错误；先规则兜底，再 dev 校准 |
| Agent 仍能自行执行 shell/联网 | 网关可被绕过 | A 在 W4 前完成权限/网络隔离与负向测试；否则限制产品防护范围 |
| 仅用文本匹配声称污点和因果图精确 | 证据不成立 | C 分离显式边、推断边；黄金集验证真实数据依赖，B 只消费定义明确的标签 |
| Benchmark 依赖冲突、数据不可用 | 全量回归失败 | C 独立环境与版本锁；W1 核源、W2 smoke；未跑完保持 incomplete |
| 审批过多、三态“误拦”被低估 | 看似安全但任务不可用 | C 同报 ASK 率、未完成率、审批耗时，B 按真实标签校准 |
| 复杂链路超过1.5s / CPU快路径超200ms | NFR失败 | A 提前W4测量；限制输入、缓存/小模型、队列预算；降级须披露且不隐藏超时 |
| 多基准与三次重复超出资源 | W6–W8无法冻结 | C 先预算，固定1个主Agent配置；额外模型作扩展，所有删减记录到清单 |
| 调参使用test或SOTA口径不一致 | 结果不可比较 | C 冻结分组test和配置；A/B只看dev调参；出处不足的SOTA留待核验 |

## 11. 待关闭决策与完成定义

| ID | 待确定事项 | 暂行方案 | Owner / 截止 |
|---|---|---|---|
| OQ-01 | 实际比赛截止日期、三人可投入时间 | 09-14启动、8周、每人32人日计划+8人日缓冲 | A / D1 |
| OQ-02 | 5090推理栈兼容性及Compose验收主机 | 资源已恢复；推理栈/CPU性能/Compose仍须实测 | A / W1 |
| OQ-03 | Agent/检测器/Intent模型及权重权限 | 一个主配置，先小样比较，不预填模型效果 | A+B / W1候选、W3固定主配置 |
| OQ-04 | MPBench具体项目与可运行材料 | 2606.04329为候选，不能只凭缩写确认 | C / W1 |
| OQ-05 | ASR总Gate的分母、聚合和显著性口径 | AgentDojo/InjecAgent分别主配置≤32%；报告配对差与95%CI | C+B / W1 |
| OQ-06 | CPU负载/最大输入和复杂链路适用硬件 | 4vCPU/8GiB、1/8KiB、并发1/4作为提案 | A+C / W1冻结 |
| OQ-07 | PRD隐含P0污点/溯源基础、负责人冲突 | 按第2节前移最小能力，按本PRD分工 | A+B+C / W1 |

一个工作包完成须同时具备代码/配置、关联 FR、可运行验收、机器可读结果和必要文档。M1 可以使用模拟工具验证工程链路，最终安全/效用必须由实际 Agent 运行和冻结数据支持。发布需要所有适用 MVP Gate 达标；当前仍待确认的外部资源与基准不得默认为通过。

本计划附带 [development_backlog.json](./development_backlog.json)，包含24个工作包的Owner、工时、时间窗、依赖与完成条件，全部初始状态为 `planned`；[历史计划校验](../plans/2026-09-12/plan_validation.json) 记录工时、日期与需求ID覆盖检查。检查结果仅证明计划内部一致，不代表产品功能或指标已经通过验收。

## 开发执行状态同步

2026-09-12 已落地可运行网关、MCP、审批、受限执行器和控制台，状态来自 [开发日志](15-implementation-record-dev-log.md) 与 [任务清单](development_backlog.json)。原 96 人日 +24 缓冲是计划估算，不是本次实际消耗。下一阶段保留本地模型、公开基准/独立 test、外部 Agent 隔离、Docker 干净环境、七天稳定性和独立评审。

A02 的首批产品目标明确为 **Codex 与 Claude Code**。顺序为：固定版本/执行主机与 Hook 能力 Spike → 共用 Hook 决策桥接层 → Codex CLI 和 Claude Code 真实 E2E / 安装配置包 → Codex 桌面端单独验证 → 执行隔离与其他扩展。框架集成仅按后续评测需要安排，不能代替现成编程 Agent 的接入验收。现有 tools/call 会执行工具，需要新增只评估不执行的 Hook 接口，并分开关联原生工具与网关执行结果，避免重复副作用。详细范围见 [主流编程 Agent 接入矩阵](../03-architecture/framework-integration-matrix.md)。上述产品集成均未实现和验收；原 96 人日作为历史基线保留，Spike 后重估剩余工作。

## 2026-09-12 实施状态更新

A02 已完成 decision-only Hook API、单次 claim、独立审批与客户端结果关联、stdlib 命令桥接和配置包生成器；25 条桥接测试通过。Codex/Claude 实际安装、完整终端语义、MCP 组合、宿主旁路尚未验收。

C04 已接入固定提交的 AgentDojo 与 InjecAgent 原生数据/判定器，在已有 Qwen2.5-7B-Instruct 上运行。初次小样暴露原生格式无效和良性效用显著下降；先保留全量首轮证据，再按开发集改进 Intent/资源授权与长上下文/输出预算。ASB、独立标注 test 和完整消融仍是阻断验收的工作，不能因低 ASR 提前签收。
