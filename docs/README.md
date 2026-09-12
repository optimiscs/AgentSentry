# AgentSentry 工程文档导航

本目录按用户要求组织30类生命周期文档。当前已有在 5090 运行的开发版服务、控制台及自动化测试；实际结果见 [测试报告](05-validation/18-test-benchmark-report.md)。工程回归通过不等于公开基准或发布验收完成。新设计没有人工签字批准，历史快照与当前规范分开。

最新服务器实测为25CPU配额、90GiB内存、RTX5090 32607MiB显存；已有本地 Qwen2.5-7B / vLLM 推理实测，Docker 部署待验证。[环境证据](evidence/environment-current.json) / [当前开发计划](04-development/14-implementation-plan.md)。

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

[核心机制与代码导读](03-architecture/core-innovation-and-code-guide.md)按活动实现、接入范围与研究候选分别说明，并提供源码入口和实验局限。

接入范围与后续路线：[主流编程 Agent 接入矩阵](03-architecture/framework-integration-matrix.md)（Codex / Claude Code 优先，产品端到端验收未执行）。

01立项→04PRD→07威胁模型/08安全要求→10RFC/12API/13Policy→06RTM→14计划→16/17测试评测→20发布/23部署/25监控。团队每周维护15实现记录、21变更记录与29债务清单。

## 机器可读资料与校验

[文档目录](catalog.json)、[50项需求/约束](01-requirements/requirements.json)、[24个工作包](04-development/development_backlog.json)、[42个测试设计](05-validation/test-cases.json)、[文档一致性检查](evidence/documentation-check.json)。这些数量是设计资产，不是通过的业务测试数量。

校验命令在工程根目录运行`python3 scripts/validate_docs.py`或`make docs-check`，检查30项文档存在、内部链接、FR/任务/测试/设计引用、96人日与状态/证据一致性。不会运行模型或Benchmark。

## 来源与冲突规则

用户最新PRD原文优先于旧Markdown，当前已修正四类入站来源和Owner冲突。新增实施解释列入ADR/RTM，未确认项保留明确Owner和截止。编号AS-DOC表示新导航编号，不覆盖原AS-PRD/RFC等历史文档ID。

[来源说明](sources.md)；[原PRD](plans/2026-09-12/AS-PRD-001_v0.9_用户原文.txt)；[历史计划](plans/2026-09-12/AgentSentry_项目开发计划_v1.0.md)；旧工程文档位于archive/2026-09-10，作为历史资料不再作为当前唯一规范。

文档状态：draft=待评审设计；active_record=事实记录或持续清单；template_not_run=执行后填真实结果；template_not_triggered=事件/里程碑触发后填；draft_future=未来迁移流程。最终签收以RTM和实际证据为准。
