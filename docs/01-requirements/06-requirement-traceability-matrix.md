# 06 需求追踪矩阵 / RTM

文档 ID：AS-DOC-06 ｜ 状态：`draft` ｜ 更新：2026-09-12

[返回导航](../README.md)

13 条 FR、7 条 NFR、10 条 Gate、14 条 SR、6 项目标，共 50 项。状态由实际测试工件同步；regression_covered 表示有回归覆盖，不等于全部需求验收通过。所有人工签收仍为 false。设计与验收细节保存在 [机器可读矩阵](requirements.json)。

| 需求 | 内容 | 任务 | 测试主题 | 实现 / 验证 |
|---|---|---|---|---|
| FR-1.1 | 直接注入检测 | A03, C03 | TC-01 | implemented_development_scope / regression_covered |
| FR-1.2 | 间接注入入站 | A02, A03 | TC-02, TC-03 | implemented_development_scope / regression_covered |
| FR-1.3 | 内存污染防护 | A05, B06, C06 | TC-04, TC-05 | implemented_development_scope / regression_covered |
| FR-2.1 | IntentIR | B01, B02 | TC-06, TC-07 | implemented_development_scope / regression_covered |
| FR-2.2 | ActionIR | B03, A04 | TC-08, TC-09, TC-10 | implemented_development_scope / regression_covered |
| FR-2.3 | 对齐校验 | B03, B07 | TC-11 | implemented_development_scope / regression_covered |
| FR-3.1 | 策略 DSL | B04 | TC-12 | implemented_development_scope / regression_covered |
| FR-3.2 | 三态决策 | B05, C05 | TC-13, TC-14, TC-15, TC-16 | implemented_development_scope / regression_covered |
| FR-4.1 | 全链路埋点 | C02, A02 | TC-17 | implemented_development_scope / partial_scope_verified |
| FR-4.2 | 溯源与污点 | C06, B06, A05 | TC-18, TC-19 | implemented_development_scope / partial_scope_verified |
| FR-4.3 | DAG与时间线 | C05, C06 | TC-20 | implemented_development_scope / partial_scope_verified |
| FR-5.1 | 对抗样本归一化 | A03, A05 | TC-21 | implemented_development_scope / regression_covered |
| FR-5.2 | 红队回归 | C04, C06, C07 | TC-22 | partial / adapter_contract_only |
| NFR-01 | 快速链路 | A06 | TC-35 | partial / measured_limited |
| NFR-02 | 复杂链路 | A06, B02 | TC-36 | pending_acceptance / not_run |
| NFR-03 | 总Trace覆盖 | C02 | TC-17 | partial / regression_covered |
| NFR-04 | 确定性 | B08 | TC-40 | partial / regression_covered |
| NFR-05 | 审计留存 | C02, A07 | TC-28, TC-29 | partial / regression_covered |
| NFR-06 | 单节点可用性 | A07, C08 | TC-42 | pending_acceptance / not_run |
| NFR-07 | 安全默认 | B04 | TC-26, TC-30 | partial / regression_covered |
| GATE-01 | 公开ASR | C04, C07 | TC-39 | pending_acceptance / not_run |
| GATE-02 | A相对改善 | A03, C04 | TC-39 | pending_acceptance / not_run |
| GATE-03 | ASB效果 | B07, C04 | TC-39 | pending_acceptance / not_run |
| GATE-04 | 良性效用 | B07, C03 | TC-37 | pending_acceptance / not_run |
| GATE-05 | 良性误拦 | B07, C03 | TC-37 | pending_acceptance / not_run |
| GATE-06 | 三态Macro-F1 | B07, C03 | TC-37 | pending_acceptance / not_run |
| GATE-07 | 检测Macro-F1 | A03, C03 | TC-38 | pending_acceptance / not_run |
| GATE-08 | P0外泄 | B06, C03 | TC-18, TC-24 | pending_acceptance / synthetic_regression_only |
| GATE-09 | 黄金溯源 | C02, C06 | TC-20 | pending_acceptance / not_run |
| GATE-10 | 污点TPR | C06, B06 | TC-19 | pending_acceptance / not_run |
| SR-01 | 执行前门控 | A02, A04 | TC-13, TC-23 | implemented_development_scope / partial_scope_verified |
| SR-02 | 授权来源与上限 | B02, B04 | TC-07 | implemented_development_scope / regression_covered |
| SR-03 | 凭据外发限制 | B06, A04 | TC-18, TC-24 | implemented_development_scope / regression_covered |
| SR-04 | 审批不可漂移 | B05 | TC-14, TC-15, TC-16 | implemented_development_scope / regression_covered |
| SR-05 | 硬拒绝不可审批覆盖 | B04, B05 | TC-25 | implemented_development_scope / regression_covered |
| SR-06 | 故障默认关闭 | B04, A02 | TC-26 | implemented_development_scope / regression_covered |
| SR-07 | 规范化执行一致 | A04, B03 | TC-09, TC-10, TC-27 | implemented_development_scope / regression_covered |
| SR-08 | 来源标签保留 | C06, A05 | TC-19, TC-20 | implemented_development_scope / partial_scope_verified |
| SR-09 | 工具元数据不授权 | A03, B04 | TC-03 | implemented_development_scope / regression_covered |
| SR-10 | 审计最小化 | C02, A07 | TC-28, TC-29 | implemented_development_scope / regression_covered |
| SR-11 | 证据与安全默认独立 | C02, A02 | TC-30 | implemented_development_scope / regression_covered |
| SR-12 | 委派不扩权 | B06, A04 | TC-19, TC-31 | implemented_development_scope / regression_covered |
| SR-13 | 重试不重复副作用 | B05, A02 | TC-16, TC-32 | implemented_development_scope / regression_covered |
| SR-14 | 管理与展示隔离 | A07, C05 | TC-33, TC-34 | implemented_development_scope / regression_covered |
| G1 | 注入入口覆盖 | A03, A05 | TC-01, TC-02, TC-03, TC-04, TC-05 | partial / regression_covered |
| G2 | 语义行为归一化 | B02, B03 | TC-06, TC-08, TC-11 | partial / regression_covered |
| G3 | 精细策略管控 | B04, B05 | TC-12, TC-13 | partial / regression_covered |
| G4 | 证据溯源 | C02, C06 | TC-17, TC-19, TC-20 | partial / partial_scope_verified |
| G5 | 检测漏检兜底 | A04, B06 | TC-18, TC-23 | partial / partial_scope_verified |
| G6 | 轻量部署 | A06, A07 | TC-35, TC-41 | partial / measured_limited |

[原始测试记录](../evidence/runtime-tests.json) · [报告与限制](../05-validation/18-test-benchmark-report.md)
