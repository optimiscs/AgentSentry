# 来源与证据边界

主输入：[用户AS-PRD-001 v0.9原文](plans/2026-09-12/AS-PRD-001_v0.9_用户原文.txt)。原8份Markdown工程文档及汇编按原名归档于archive/2026-09-10；TRIDENT Sentinel竞品报告归档于archive/2026-09-08。现行30文档按AgentSentry运行时防护定位重新整理。

资源证据来自本次SSH只读探测：[environment-current.json](evidence/environment-current.json)。历史快照保存在plans/2026-09-12/5090_environment_snapshot.json，不能把历史受限配额视为当前状态。

本次新核验的一手资料包括[Check Point/Lakera运行时防护](https://docs.lakera.ai/guard)、[Invariant官方仓库](https://github.com/invariantlabs-ai/invariant)、[NeMo执行等rails](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types)、[AI-Infra-Guard](https://github.com/Tencent/AI-Infra-Guard)、[Promptfoo红队指南](https://www.promptfoo.dev/docs/red-team/)。具体支持哪些结论见02竞品文档，不引用厂商自报效果作为独立测评。

公开基准一手入口见17评测计划，MCP实现应锁定[官方Python SDK](https://github.com/modelcontextprotocol/python-sdk)和选定[协议规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。网页可更新，版本/commit须在执行Spike时冻结。

没有客户访谈/营收、业务实现、Benchmark实测、法律合规结论、生产事故或正式产品发布事实。报告模板必须等待真实执行再填写。文档目录校验只是资料质量检查。
