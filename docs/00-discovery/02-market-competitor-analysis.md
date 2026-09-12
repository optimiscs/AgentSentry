# 02 市场与竞品分析

文档 ID：AS-DOC-02 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：A ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

## 分析范围与结论

旧版TRIDENT Sentinel报告面向自动化红队平台，已原样归档。本页重新围绕AgentSentry的在线工具执行防护比较。查询日期为2026-09-12；仅使用官方文档/仓库的公开能力，未购买产品、未做同配置实测；未证实的能力不能推断为“竞品没有”。

| 对象 | 官方资料支持的能力 | 对AgentSentry的影响与验证空间 |
|---|---|---|
| Check Point AI Guardrails / Lakera | 官方列出提示攻击、数据泄漏、工具描述/响应以及偏离任务的Agent行为防护，提供SaaS与自托管形态 | 不以“理解任务偏离”“私有化”作独占卖点；比较精确审批、执行权限边界、证据与CPU资源成本。见[官方说明](https://docs.lakera.ai/guard) |
| Invariant Guardrails | 官方开源仓库定位为安全可靠Agent开发的guardrails；研究工作包含可描述工具调用关系的策略语言 | 不声称首创DSL/调用关联；选固定版本对比同一工具流的表达能力和绕过测试。见[官方仓库](https://github.com/invariantlabs-ai/invariant) |
| NVIDIA NeMo Guardrails | 文档覆盖输入、检索、对话、执行、输出多个阶段 | “多层防御”已有实现；要验证我们的Proxy是否确实控制实际执行。见[Guardrail Types](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types) |
| 腾讯 AI-Infra-Guard | 开源红队平台覆盖Agent/MCP/基础设施扫描及越狱评估 | 复用离线扫描与回归，不将扫描器作为运行时硬边界。见[官方仓库](https://github.com/Tencent/AI-Infra-Guard) |
| Promptfoo | 官方红队指南提供攻击生成/执行与评测工作流 | 作为回归方法与报告可读性的参考，不按扫描次数与在线阻断比较。见[官方指南](https://www.promptfoo.dev/docs/red-team/) |

## 可检验的差异假设

| 假设 | 试验设计 | 不成立时如何调整 |
|---|---|---|
| Intent合同和精确审批降低过度阻断 | 同一良性/攻击集比较规则、完整系统、去ASK；并报ASK未完成率 | 减少无收益的语义路径，改进任务授权UI |
| 检测漏报时仍能阻断敏感副作用 | 强制detector低风险，预置SECRET上下文，观察模拟sink | 修显式数据流/执行边界，不能只提高分类阈值 |
| 图证据更容易审计 | 独立标注source/边/sink，比较重建正确率和人工复查时间 | 将推断边降级显示，减少虚假因果解释 |
| 轻量部署适合赛事和小团队 | 干净CPU-only部署、相同负载P95、接入工时 | 缩减部署组件和模型，不以GPU结果替代CPU验收 |

## 市场与产品边界

首期服务受控代码Agent和研究/测试团队；企业身份、跨境数据、复杂多租户和SIEM集成留待验证需求后规划。当前没有可核验市场规模、收入、客户访谈或采购报价，不填估算市场份额。

W1由A/C安排3–5名目标使用者的访谈计划（尚未联系）：最近一次工具越权问题、现有审批成本、是否允许外部模型、可接受部署权限、报告所需证据。输出匿名需求与反例，不用受访数量代替市场验证。

更广泛的历史参考见[TRIDENT Sentinel原报告](../archive/2026-09-08/TRIDENT_Sentinel_竞品分析报告_2026-09-08.md)，其价格/版本与原定位不能直接沿用于AgentSentry。
