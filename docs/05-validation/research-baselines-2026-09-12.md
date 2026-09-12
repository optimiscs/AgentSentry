# 公开基准与防御研究核对（2026-09-12）

状态：研究依据与待复现实验设计。下表是论文作者的结果，不能作为本项目验收结果，也不能将不同模型、攻击集合的数字排成统一 SOTA 榜单。

| 方法 / 原始来源 | 可核对的配置和结果 | 对本项目的启示与限制 |
|---|---|---|
| [IPIGuard，EMNLP 2025](https://aclanthology.org/2025.emnlp-main.53/)；[论文 v1](https://arxiv.org/html/2508.15310v1)；[作者代码](https://github.com/Greysahy/ipiguard) | 表 1：GPT-4o-mini、AgentDojo、Important Instructions，基线 ASR 27.19%、UA 49.92%；防护 ASR 0.64%、UA 57.07%。附录 G：Qwen2.5-7B 同时作为执行器和规划器，BU 35.05%、UA 33.55%、ASR 0.16%。 | 在读取不可信内容前规划工具依赖图；运行中只允许扩展查询工具。适合比较受信任务规划，但单纯工具白名单不能保护所有参数。这里的 Inj.Age. 是 AgentDojo 内的攻击名称，不等于完整 InjecAgent 数据集。 |
| [Task Shield，ACL 2025](https://aclanthology.org/2025.acl-long.1435/)；[论文](https://arxiv.org/abs/2412.16682) | 作者报告 GPT-4o、AgentDojo 的 ASR 2.07%、任务效用 69.79%。 | 按用户任务核对指令与工具调用。可作为语义核验比较对象；核验模型判定不能覆盖本项目凭据、秘密外发、静态权限上限等硬规则。 |
| [CaMeL](https://arxiv.org/abs/2503.18813)；[Google 原始代码](https://github.com/google-research/camel-prompt-injection) | 作者报告 AgentDojo 中 77% 任务可在其安全模型下完成，原生系统为 84%。仓库标注 Apache-2.0，且明确为研究工件。 | 将规划控制流与不可信数据处理隔离，按值记录来源和能力。我们采用精确目标绑定的工程方向；未实现其解释器，不能声称继承其形式安全保证。 |
| [PromptArmor v1](https://arxiv.org/html/2507.15219v1) | 主 Agent 为 GPT-4.1；629 个攻击场景，四种攻击的联合 ASR。表 1 的 GPT-4.1 核验器：ASR 0%、UA 72.02%、FPR 0.56%、FNR 0.13%。 | 检测并删除注入片段，保留正常内容，值得作为独立输入防御基线。四攻击取并集的 ASR 不能与本项目单攻击配置直接比较；其 FPR 也不等于本项目三态误 BLOCK。 |
| [PlanGuard v1，2026-04](https://arxiv.org/html/2604.10134v1) | InjecAgent 1,054 条；DeepSeek-V3.2 同时用于主 Agent 与防御。作者修改受害者系统提示以强制服从工具内容，报告 ASR 从 72.8% 到 0%。 | 先隔离规划，再做工具/参数两级核验。这个提示修改必须单独标记，不能复制其基线 ASR 到我们的原生提示配置。论文摘要与分组 FPR 的汇总口径需要进一步核对，暂不采用为验收参考值。 |
| [AgentSentry 论文 v1，2026-02](https://arxiv.org/html/2602.22724v1) | GPT-4o、GPT-3.5-turbo、Qwen3-Max，多种 AgentDojo 攻击；作者报告跨模型平均 UA 74.55%、ASR 0%。 | 在工具返回边界做反事实诊断并选择性净化。**该论文与本工程同名，但本工程不是该论文的复现，也未复制其实现。** 当前实现没有该反事实算法；对外介绍必须区分。 |
| [CausalArmor，Google Research，2026](https://research.google/pubs/causal-armor-efficient-indirect-prompt-injection-guardrails-via-causal-attribution/) | 官方摘要描述 AgentDojo 与 DoomArena 实验，当前已核对页面未给完整表格。 | 在高权限动作前按片段做 leave-one-out 归因，再定向净化和屏蔽受污染推理。只列为候选，不虚构性能、延迟或同配领先结论。 |
| [SecureClaw v1，2026-06](https://arxiv.org/html/2606.09549v1) | GPT-4o-mini；AgentDojo v1.1.2 的629攻击条目，ASR0.64%；正常效用70.10%→60.82%。ASB是5类DPI各400条，ASR0%、效用88.90%。 | 敏感读句柄、精确提交及拒绝后的恢复。ASB不是mixed；包含别名解析与仅对策略已允许动作的自动确认。按表计算正常效用损失9.28pp，不满足本项目5pp门槛。没有将同名OpenClaw插件当作论文代码。 |
| [ALRPHFS，Findings EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.1066/)；[预印本v1表2](https://arxiv.org/html/2505.19260v1) | v1以GPT-4o-mini评测ASB的mixed分类ACC82.50%、四类平均ACC83.13%；Claude-3.5配置mixed ACC67.50%。 | 离线风险模式去重及快慢分层核验值得比较。ACC不等于执行ASR或三态Macro-F1；不能计算1−ACC作为我们的攻击成功率。正文概括与分组表不完全一致，保留版本及表格口径。 |
| [MSB v2 的 MCIP 对照](https://arxiv.org/html/2510.15994v2)；[MCIP作者代码](https://github.com/HKUST-KnowComp/MCIP) | 表4中Qwen3-8B的ASR为47.23%→24.04%，PUA为51.15%→48.34%；12种攻击类型取平均。 | 工具级分类器是可复现比较对象，但需要实际MCP工具与返回结果防护。不同模型与工具版本的数字不能作为我们的达标证据；当前尚未运行MCIP。 |
| [MPBench v2](https://arxiv.org/html/2606.04329v2)；[PIGuard作者权重](https://huggingface.co/leolee99/PIGuard) | 表3的现成PIGuard为TPR38.33%/FPR0.33%；70B PromptArmor为67.67%/1.00%。 | 支持增加独立神经检测对照，也表明现成输入检测器不足以覆盖记忆投毒。固定权重CPU分窗全量诊断已完成：TPR30.76%、FPR20.41%；我们的窗口与分母单列，不声称复现这些论文分数或完成记忆验收。 |

## 数据与比较条件

[ASB 原论文 v3](https://arxiv.org/html/2410.02644v3)覆盖 13 个模型、11 种防御、4 种混合攻击。DPI、IPI、记忆投毒会破坏不同信任来源；不能把全部用户文本视为可信来处理其 DPI+IPI+MP 配置。当前已下载固定提交的 ASB，但原入口依赖在线嵌入和裁判，尚未完成本地混合攻击复现，也没有足够证据宣布某个方法是该配置的最新 SOTA。

本项目正式比较仍遵循[评测计划](17-evaluation-benchmark-plan.md)：相同数据提交、原生判定器、模型权重、提示、推理预算、种子与攻击清单。AgentDojo 当前固定版本有 949 个攻击配对，不能拿论文旧版 629 条的结果直接对比。InjecAgent 原生无良性任务完成判定器；“没有调用攻击工具”与“完成正常任务”必须分别报告。ASB 的字符串成功条件与实际模拟工具调用需并列核查，不能把注入文本删除率当 ASR。

## 本次实施与下一步

1. 已修复英文授权动词漏识别和单词子串误匹配；保留静态边界、明确否定及敏感操作硬限制。
2. 已增加完整接收目标哈希绑定。仅受信用户任务中的明确字面目标可授予目标权限；工具响应、正文提及的地址、模型补充接收方不能授予权限。HTTP 重定向要求另行提交受控动作。
3. 已合并两个运行器的模型传输、模型配置读取、源码哈希和恢复检查；原生判定器没有被改写。新增辅助源码哈希参与配对验证。
4. 活动版本仍是粗粒度 Effect 合约。隔离的[task-plan-v1候选](../adr/adr-010.md)已实现受信任务规划和参数来源核验，真实模型小样正在等待v4配对结束；生产持久化及真实客户端集成尚未完成。后续应与IPIGuard/Task Shield/PromptArmor在同配置下比较。不能以扩大允许范围代替任务约束。
5. 历史7B v3正常任务配对损失5.15pp；最新27B v4基线84/97成功、防护59/97成功，效用损失25.77pp，防护8条未完成评估。更强主模型暴露出31个正常任务需要ASK的授权瓶颈。后续必须验证受信任务规划和参数来源约束；当前报告仍为 NOT_ACCEPTED，不扩充权限或自动批准来改变结论。

## 来源与代码复用

论文方法借鉴与代码复制分别记录。上述论文及作者仓库提供设计依据；本次新增目标绑定、共享运行器代码为本项目实现，没有复制上述防御仓库代码。AgentDojo/InjecAgent 的原生工具、提示和判定器通过固定上游源码调用，其版本与许可在数据来源工件中保留；不计入自研代码量。

同名论文及已有同名软件包意味着公开发布前需要明确项目名称与归属。当前仅使用本地开发源码，不从 PyPI 安装同名包覆盖本工程。

代码重复统计见[内部重复审计](code-duplication-report.md)。该统计只衡量仓库内部 Python 片段重复，不证明外部原创性，也不能转换成学校或比赛的查重比例。

## ASB 原生判定器的可执行核查

`scripts/audit_asb_evaluator.py` 只提取并校验两段已审阅的纯评分函数，不导入云端入口。两个合成反例在实际工具执行次数为0时，仅将攻击目标/正常工具成就文字放入初始用户消息，就分别得到原生攻击成功/任务成功。证明该原生指标是全文字符串代理，不能单独证明工具执行结果；不是ASB模型评测，也不对真实攻击发生率作推断。后续必须保留原生分数并另列受控模拟执行判定。[证据](../evidence/asb-evaluator-audit.json)。


补充研究结论：当前没有核实到与本项目ASB mixed、模型、原生判定器和人工ASK处理完全一致的统一SOTA排名。后续比较必须同时记录攻击入口、检索/记忆配置、确认处理和真实模拟执行，不能把DPI零ASR、分类准确率或论文自定义效用直接映射到本项目验收。[精确合约候选](../adr/adr-009.md)提供独立实现的动作约束基础，尚未实现上述论文的完整算法。

ASB的四种混合配置与缓存记忆数量已完成[源码协议核查](asb-protocol-preparation.md)，尚未运行本地混合攻击评测。

MSB固定源码已建立2000场景索引，发现实际任务数64与论文65不同，并用纯评分夹具复现4个原生评分问题，详见[MSB协议准备](msb-protocol-preparation.md)。这些是适配与判定核查，没有启动真实MCP攻击服务。

MPBench固定源码完整解析6240个对象，保留拼接JSON、重复上下文及缺失目标。当前规则对全部外部字段的攻击召回率为2.78%、良性误报率0.40%，属于公开数据输入诊断；PIGuard对照使用固定0.5阈值，6240条全有效：TPR30.76%、FPR20.41%、二分类Macro-F1为0.5184；完整2048-token输入对照待运行。[数据与诊断说明](mpbench-protocol-and-diagnostic.md)

PIGuard作者训练/验证/测试材料已按固定提交完成[重叠审计](piguard-data-provenance.md)，发现公开验证与测试的复用及训练数据质量问题；整段匹配为零也不能证明当前checkpoint未接触相似攻击。后续同配置比较需要注明模型数据来源，不以这些公开材料代替本项目独立标注集。

2026-09-13补充：[创新性与强基线评估](novelty-and-sota-assessment-2026-09-13.md)新增Progent、AgentWatcher、2026年8月的AgentFlow/Bounded Agents，并逐项区分设计重叠、指标协议和待证明贡献。此前列表不是截至当前的统一SOTA排名。
