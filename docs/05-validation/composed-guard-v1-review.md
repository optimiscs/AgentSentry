# 输入清洗与动作授权的首个组合候选

2026-09-13。状态：**离线检查通过，真实模型评估尚未启动，完整 benchmark 未验收。** 任务模型和防护模型默认关闭思考。本轮继续推进原完整目标，没有把输入参考的全量运行作为产品验收终点。

这次解决的是一个实际缺口：此前清洗参考会处理工具返回内容，但没有调用任务授权；任务授权配置则只使用规则隔离。现在同一候选可以同时运行两层。

流程为：受信用户任务生成授权计划 → 动作执行前检查硬策略及精确参数 → 已允许工具返回原始数据 → 扫描并保留风险标签 → 生成删除注入片段后的 actor 视图 → 下一次动作再次接受授权检查。原始观察用于来源审计；被隔离的原始观察不因文本被清洗就恢复举证资格。清洗模型不能批准动作，额外收件人、秘密外发和未计划工具仍要被拒绝。

核心新增代码是候选中的 `src/agentsentry/context/defense.py`。AgentDojo 和 ASB 共用该模块；ASB 覆盖直接注入后缀、原生 OPI 后的工具观察及检索记忆。调用配置选择集中在 `benchmarks/context_options.py`。输入清洗 prompt 沿用 v5，参数审核沿用 v6，硬策略文件没有改动。[设计决定](../adr/adr-012.md)、[完整补丁](../../artifacts/lab3090-composed-guard-v1/changes.patch)

## 已完成的代码检查

| 检查 | 结果 | 能证明什么 |
|---|---:|---|
| 契约、清洗、传输与配对单测 | 149 通过，另 2 个 subtest | 协议、来源限制、模式选择与未知计分 |
| AgentDojo 原生模拟流程 | 16 通过 | 两层都运行；正常邮件执行，越权 CC、风险来源和 SECRET 不放行 |
| ASB 原生模拟流程 | 17 通过 | 三类入口使用共享清洗；未计划工具不执行；被上游捕获的清洗失败仍计未知 |

三类检查的实际命令返回码均为 0。初次原生检查 16/16 和 ASB 16/16 已通过；补充错误计分检查、抽取共同断言后分别复测，最终 ASB 为 17 条。没有实际调用模型、外发邮件或启动攻击工具服务，因此这些数不能换算为 ASR、任务效用或检测 F1。[单测日志](../../artifacts/lab3090-composed-guard-v1/unit-checks-initial.log)、[AgentDojo 日志](../../artifacts/lab3090-composed-guard-v1/native-checks-final.log)、[ASB 日志](../../artifacts/lab3090-composed-guard-v1/asb-checks-final.log)、[机器证据](../evidence/composed-guard-v1.json)

72 个首方 Python 文件共 72,561 个显著 token。新增测试最初带来 114 个规范化重复 token；将相同的“拒绝邮件不得执行”检查收敛到共用断言后，最终 50-token 精确/规范化克隆覆盖为 **352/1312**，与父版本相同，比例约 0.485%/1.808%。没有隐藏测试文件；benchmarks 中的模拟检查一直计入该审计。比例下降来自分母增加，不作为消除旧重复或算法原创性的证明。[初次审计](../../artifacts/lab3090-composed-guard-v1/duplication.json)、[最终审计](../../artifacts/lab3090-composed-guard-v1/duplication-final.json)

## 下一轮实际模型对照

已经固定 35 条/组的命令：同样 19 个正常任务和 16 个开发攻击，baseline 对完整组合，使用同一候选源码、Qwen3.5-9B、seed 0、输出 4096、15 步、300 秒超时和每组 2 workers。两组都显式选择 joint 组合参数，baseline 按其消融定义不调用防护。[待执行命令](../../artifacts/lab3090-composed-guard-v1/jobs.json)、[未启动状态与前提](../../artifacts/lab3090-composed-guard-v1/planned-status.json)

当前两张卡仍在运行此前冻结的 [v5 全量输入参考](context-filter-v5-review.md)。新模型任务尚未启动，也没有设定后台自动启动；下一步须先核对这两组的真实终态和输出覆盖。既有运行出错或观察超时不能作为重复发起作业的理由。

21:49 北京时间的实查为 baseline 242/1046、参考 176/1046，已记录项均有效；两个原进程身份匹配，129 个 v5 源文件及 132 个组合源文件哈希不变。[带时间的快照](../../artifacts/lab3090-composed-guard-v1/parent-progress.json)

35 条选择沿用已知开发样本，不属于独立留出；此前 v6 的四条固定轨迹全部 ASK，本次离线组合并未证明解决了漏来源、动态日期或正文验证问题。风险标签仍按整条观察排除，可能继续损害正常任务。待真实对照明确差异后，再决定是否调整字段级来源和计划，不通过扩大权限或忽略条件来提高分数。

## 恢复与范围

[冻结包](../../artifacts/lab3090-composed-guard-v1/source-candidate.tar.gz) SHA256：`bc422e1904b790dd8988b0c0bdbed63b62f6d8e913fbc92c38c010a3ba87548a`，132 个源文件。解压后将配套 [candidate-manifest.json](../../artifacts/lab3090-composed-guard-v1/candidate-manifest.json)放入根目录；包内源文件及从父版本重建的补丁均核对通过。[冻结与导入来源](../../artifacts/lab3090-composed-guard-v1/freeze.json)、[补丁重建核对](../../artifacts/lab3090-composed-guard-v1/patch-rebuild-check.json)

输入清洗、计划约束和来源分析已有相关研究，见 [PromptArmor 等比较](research-baselines-2026-09-12.md)及 [AgentArmor/Interbolt 核查](graph-and-provenance-baseline-review.md)。本轮只是使完整组合可测，没有新增论文成绩或 SOTA 排名。生产 Hook/MCP 的组合持久化、真实 Codex/Claude Code 全流程、ASB mixed 效用、其他基准、独立标注、重复/消融及固定资源延迟要求继续保留。
