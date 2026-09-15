# AgentSentry 工程文档导航

产品入口：[项目首页](../README.md) · [使用指南](getting-started.md)。首页编辑依据见 [六个万星 Agent 项目 README 分析](00-discovery/readme-benchmark-analysis.md)。

本目录按用户要求组织30类生命周期文档。当前已有在 5090 运行的开发版服务、控制台及自动化测试；实际结果见 [测试报告](05-validation/18-test-benchmark-report.md)。工程回归通过不等于公开基准或发布验收完成。新设计没有人工签字批准，历史快照与当前规范分开。

2026-09-13 实验已迁移到双卡 Lab3090，使用新 Conda 环境与 Qwen/Qwen3.5-9B；本轮 ASB 小样和 PIGuard 输入诊断已完成，综合 benchmark 仍未验收。[迁移与结果](04-development/lab3090-migration-and-resume.md) / [恢复证据](evidence/lab3090-recovery.json) / [当前开发计划](04-development/14-implementation-plan.md)。5090 的旧环境记录保留为[历史环境证据](evidence/environment-current.json)，不能视为 Lab3090 配置或当前在线状态。

新增 [归因防护成本与强基线评审](05-validation/causal-proxy-budget-and-baseline-review.md)：35 条真实开发轨迹的 CPU token 核对已完成，没有新增模型效果；任务与防护继续默认关闭思考。

新增 [MPBench 跨会话评测准备](05-validation/mpbench-lifecycle-preparation.md)：全量字段隔离、正常记忆写入期望和未知结果计分已实现；真实记忆及裁判运行尚待完成。

后续 [产品记忆存储适配](05-validation/memory-runtime-adapter.md)已通过103项检查，包含独立进程读取、隔离和来源保留；原生 Agent 与语义效果评估仍待完成。

[原生 Codex 记忆接入](05-validation/native-codex-memory.md)已通过6个真实 CLI 进程的 MCP/存储验证及37项检查；模型回复为预设数据，没有新 benchmark 分数。[DeepSeek Harness / Flash实测与标注](05-validation/deepseek-harness-flash.md)已跑通，用户最新目标为五基准11,940场景/记录的详细模型行为评估，持续使用授权API额度；尚未全量完成。

## 30类文档

| 编号 | 文档 | Owner | 状态 |
|---|---|---|---|
| 01 | [项目立项 / One Pager](00-discovery/01-project-one-pager.md) | A | 初稿已完善/待人工评审 |
| 02 | [市场与竞品分析](00-discovery/02-market-competitor-analysis.md) | A | 初稿已完善/待人工评审 |
| 03 | [可行性调研 / Tech Spike](00-discovery/03-feasibility-tech-spike.md) | A+B | 初稿已完善/待人工评审 |
| 04 | [产品需求文档 / PRD](01-requirements/04-prd.md) | A | 初稿已完善/待人工评审 |
| 05 | [User Story / Use Case](01-requirements/05-user-stories-use-cases.md) | C | 初稿已完善/待人工评审 |
| 06 | [需求追踪矩阵 / RTM](01-requirements/06-requirement-traceability-matrix.md) | C | 初稿已完善/待人工评审 |
| 07 | [威胁模型 / Threat Model](02-security/07-threat-model.md) | A+B | 初稿已完善/待人工评审 |
| 08 | [安全需求 / Security Requirements](02-security/08-security-requirements.md) | B | 初稿已完善/待人工评审 |
| 09 | [隐私与合规评审](02-security/09-privacy-compliance-review.md) | A | 初稿已完善/待人工评审 |
| 10 | [总体设计 / System Design RFC](03-architecture/10-system-design-rfc.md) | A | 初稿已完善/待人工评审 |
| 11 | [架构决策记录 / ADR](03-architecture/11-adr-index.md) | A+B+C | 初稿已完善/待人工评审 |
| 12 | [API 与数据模型规范](03-architecture/12-api-data-schema.md) | B | 初稿已完善/待人工评审 |
| 13 | [安全策略规范](03-architecture/13-security-policy-spec.md) | B | 初稿已完善/待人工评审 |
| 14 | [项目开发计划 / Implementation Plan](04-development/14-implementation-plan.md) | A | 初稿已完善/待人工评审 |
| 15 | [实现记录 / Dev Log](04-development/15-implementation-record-dev-log.md) | A+B+C | 已建立，记录事实/持续维护 |
| 16 | [测试计划 / Test Plan](05-validation/16-test-plan.md) | C | 初稿已完善/待人工评审 |
| 17 | [评测与 Benchmark 计划](05-validation/17-evaluation-benchmark-plan.md) | C | 初稿已完善/待人工评审 |
| 18 | [测试与 Benchmark 报告](05-validation/18-test-benchmark-report.md) | C | 已生成真实测试报告/持续更新 |
| 19 | [安全评审与红队报告](05-validation/19-security-review-red-team-report.md) | A+C | 模板已建立/尚未执行 |
| 20 | [发布计划与上线检查表](06-release/20-release-plan-launch-checklist.md) | A | 初稿已完善/待人工评审 |
| 21 | [变更记录与版本说明](06-release/21-changelog-release-notes.md) | A | 已建立，记录事实/持续维护 |
| 22 | [回滚计划](06-release/22-rollback-plan.md) | A | 初稿已完善/待人工评审 |
| 23 | [部署指南](07-operations/23-deployment-guide.md) | A | 初稿已完善/待人工评审 |
| 24 | [运维手册](07-operations/24-operations-runbook.md) | A+C | 初稿已完善/待人工评审 |
| 25 | [SLO 与监控规范](07-operations/25-slo-monitoring-spec.md) | A+C | 初稿已完善/待人工评审 |
| 26 | [安全事件响应计划](07-operations/26-incident-response-plan.md) | A | 初稿已完善/待人工评审 |
| 27 | [事故复盘](08-improvement/27-postmortem.md) | A+C | 模板已建立/尚未触发 |
| 28 | [项目里程碑复盘](08-improvement/28-project-retrospective.md) | A+B+C | 模板已建立/尚未触发 |
| 29 | [技术债务清单](08-improvement/29-technical-debt-list.md) | A+B+C | 已建立，记录事实/持续维护 |
| 30 | [弃用与迁移计划](08-improvement/30-deprecation-migration-plan.md) | A+B | 未来流程初稿/当前不执行 |

[公开 Benchmark 实测与验收](05-validation/public-benchmark-report.md)：原生数据与模型已运行，效用/格式有效率尚未达标，正式验收未通过。

[论文与基准比较](05-validation/research-baselines-2026-09-12.md)记录已核对的原论文、配置差异和本次优化依据；[内部代码重复审计](05-validation/code-duplication-report.md)记录共享模块重构的可复现统计。

[创新性、强基线与研究差距](05-validation/novelty-and-sota-assessment-2026-09-13.md)补充2026年8月相近工作、逐基准比较条件和研究工期，明确工程价值与尚未证明的算法贡献。

[Benchmark 实时进度](05-validation/live-benchmark-progress.md)在 5090 每15秒更新，本地镜像随证据回收刷新；进度工件由服务器写入，常规源码同步不会覆盖它。

## 当前推荐阅读顺序

[输入清洗与动作授权组合候选](05-validation/composed-guard-v1-review.md)：两层已接通并通过 149 项单测、16 项 AgentDojo 和 17 项 ASB 模拟检查；没有新增模型成绩。35 条/组对照命令已固定，等待当前全量输入参考结束后核对启动条件。

[当前完整防护流程与真实 bad cases](05-validation/defense-flow-and-bad-cases-lab3090.md)按真实 ASB 运行记录说明触发的防护步骤、产品主线未覆盖的分支，以及过度拦截、记忆漏检和协议失败。

[ASB v3 优化实测](05-validation/asb-contract-v3-review.md)：两组各40条均有效，防护组放行8次正常调用，已知攻击执行9→0；完整任务效用仍未成立，综合验收未通过。

[AgentDojo v4 正常任务及攻击复测](05-validation/agentdojo-lab3090-contract-v4-review.md)：计划协议错误8→0；正常完成基线8/8、防护4/8。16条/组攻击对照已结束，已判定攻击成功3→0，但防护有1条未知；完整验收仍未通过。

[核心机制与代码导读](03-architecture/core-innovation-and-code-guide.md)按活动实现、接入范围与研究候选分别说明，并提供源码入口和实验局限。

[v5 证据格式诊断与代码量](05-validation/task-contract-v5-diagnostic.md)：证据清单由代码生成，修复两条解码协议错误；仍存在编造日期和遗漏正文核验。仅固定轨迹诊断，未产生新 benchmark 成绩，未进入产品主线。

[输入清洗同模型参考对照](05-validation/context-filter-reference.md)：修复版两组各24条全部有效，正常完成均8/8，攻击成功3/16→0/16；存在误删，统计显著性及完整系统验收尚未成立。已扩大到两组各97条正常任务。

接入范围与后续路线：[主流编程 Agent 接入矩阵](03-architecture/framework-integration-matrix.md)（Codex / Claude Code 优先，产品端到端验收未执行）。

01立项→04PRD→07威胁模型/08安全要求→10RFC/12API/13Policy→06RTM→14计划→16/17测试评测→20发布/23部署/25监控。团队每周维护15实现记录、21变更记录与29债务清单。

## 机器可读资料与校验

[文档目录](catalog.json)、[50项需求/约束](01-requirements/requirements.json)、[24个工作包](04-development/development_backlog.json)、[42个测试设计](05-validation/test-cases.json)、[文档一致性检查](evidence/documentation-check.json)。这些数量是设计资产，不是通过的业务测试数量。

校验命令在工程根目录运行`python3 scripts/validate_docs.py`或`make docs-check`，检查30项文档存在、内部链接、FR/任务/测试/设计引用、96人日与状态/证据一致性。不会运行模型或Benchmark。

## 来源与冲突规则

用户最新PRD原文优先于旧Markdown，当前已修正四类入站来源和Owner冲突。新增实施解释列入ADR/RTM，未确认项保留明确Owner和截止。编号AS-DOC表示新导航编号，不覆盖原AS-PRD/RFC等历史文档ID。

[来源说明](sources.md)；[原PRD](plans/2026-09-12/AS-PRD-001_v0.9_用户原文.txt)；[历史计划](plans/2026-09-12/AgentSentry_项目开发计划_v1.0.md)；旧工程文档位于archive/2026-09-10，作为历史资料不再作为当前唯一规范。

文档状态：draft=待评审设计；active_record=事实记录或持续清单；template_not_run=执行后填真实结果；template_not_triggered=事件/里程碑触发后填；draft_future=未来迁移流程。最终签收以RTM和实际证据为准。

[全量 97 正常任务清洗复核](05-validation/context-filter-benign97-review.md)：基线完成 89/97、清洗参考完成 87/97，存在错误和真实误删，验收未通过。

[v6 参数来源定位诊断](05-validation/task-contract-v6-diagnostic.md)：137 项代码检查通过，四条真实审核仍 ASK，尚无任务完成率提升证据。

[完整模型提示词](05-validation/model-prompts-2026-09-13.md)与[GPU 历史/真实客户端核查](05-validation/runtime-audit-2026-09-13.md)：没有可信的一小时硬件利用率均值，没有云模型防护测试；Codex 仅部分真实拦截，Claude 为事件夹具。

[清洗模式与单次调用候选对照](05-validation/context-filter-mode-comparison.md)：同一批选定输入的正常误删 8/16→0/16，32 条无处理错误；不能据片段删除声明 ASR 为零。两组各 97 个正常任务复测已结束，均完成 89/97；仍有错误和验证码误删，未验收。

[白话版评估报告](05-validation/evaluation-history-plain-language.md)：按“改了什么、任务做完几件、攻击得逞几次”说明进展，保留 24 轮记录和任务数量图。

[历次评估、代码修改与前后变化](05-validation/evaluation-history-and-code-changes.md)：汇总 24 组真实模型 benchmark 配对，并附效果/延迟折线图和可重建数据，以及固定输入诊断、离线协议回放、CPU/模型速度测试；按版本区分收益、退化与未运行项。

[v5 清洗与全量运行](05-validation/context-filter-v5-review.md)：新增邮件固定输入全部保留；35 条/组原生小样均有效，正常完成均 19/19、攻击成功 3/16→0/16。全量 1046 条/组已启动，未填写最终分数；任务与防护默认关闭思考，仍为参考模式。

[AgentArmor / Interbolt 基线核查](05-validation/graph-and-provenance-baseline-review.md)：补充图依赖、来源门控及 OPI/混合攻击口径，作者分数与本项目实测分开。

[SecOPD 强基线与复现条件](05-validation/secopd-baseline-review.md)：补充自适应攻击与训练防御的比较，作者结果与本项目运行分开记录。
