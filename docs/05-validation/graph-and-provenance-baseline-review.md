# 图分析与来源门控：补充基线核查

2026-09-13。以下是作者公开结果与代码审阅，没有调用云模型、安装执行第三方框架或取得本项目复现成绩。

**AgentArmor：不能把“图 + 类型检查”当作本项目独有贡献。**

AgentArmor v3 将运行轨迹构造成程序依赖图，以 GPT-4o-mini 推断控制/数据依赖，再检查安全属性；它也依赖工具注册元数据。因此模型推断依赖关系的准确性属于方法的信任假设，不能仅凭最后一步采用类型检查就当作无条件安全证明。[论文方法](https://arxiv.org/html/2508.01249v3#S5)

| 作者表 II 的设置 | 无防护 ASR → 防护 ASR | 防护下任务效用：有攻击 / 无攻击 |
|---|---:|---:|
| AgentDojo，GPT-4o-mini，多种攻击合计 | 17% → 3% | 48% / 72% |
| AgentDojo，GPT-4o，多种攻击合计 | 28% → 4% | 48% / 72% |
| ASB，仅 OPI，GPT-4o-mini | 41% → 0% | 56% / 56% |
| ASB，仅 OPI，GPT-4o | 73% → 0% | 67% / 67% |

表中“无攻击”是防护下的正常效用，不能误标为无防护效用。ASB 的 Combined 是 OPI 范围中的攻击策略，不等同于本项目的 DPI/OPI/MP 混合设置。论文还假设能检查内部运行轨迹；仅有产品 Hook 工具事件时，需要另外说明可观察性。不能把这些跨模型、跨范围分数转录成本项目或 mixed 目标的差距。[实验设置与表 II](https://arxiv.org/html/2508.01249v3#S6)

**Interbolt：执行门控也会损失正常任务，纯答案污染仍可能绕过工具检查。**

作者发布 GPT-4o-mini-2024-07-18、AgentDojo suite v1.2.2、important_instructions、Interbolt 0.2.0 的两次重复。注意 CSV 的 AgentDojo 安装包版本为 0.1.35，与 suite v1.2.2 是两种版本口径。[作者 README](https://github.com/deconvolute-labs/interbolt-agentdojo/blob/43e2b5fa3e7b41b7e26f7c04cc8f371ab98aa875/README.md)

| 作者结果摘录 | 无防护正常完成 → 门控后完成 | 无防护攻击成功 → 门控后攻击成功 |
|---|---:|---:|
| banking / strict / repeat 0 | 9/16 → 6/16 | 71/144 → 0/144 |
| banking / targeted / repeat 0 | 9/16 → 7/16 | 71/144 → 0/144 |
| travel / strict / repeat 0 | 13/20 → 7/20 | 39/140 → 9/140 |
| travel / targeted / repeat 0 | 13/20 → 6/20 | 39/140 → 11/140 |

“到达受控工具的攻击全部被阻止”与“整体 ASR 为零”不同；旅行剩余攻击的目标可以是最终回答中的一句话。本项目也必须保留原生整体 ASR，不能只挑发生工具调用的攻击计分。[发布 CSV](https://github.com/deconvolute-labs/interbolt-agentdojo/blob/43e2b5fa3e7b41b7e26f7c04cc8f371ab98aa875/runs/published/results.csv)

banking targeted 策略把账户余额等结构化源标可信，将文件和交易历史标不可信；污染会话中的转账等操作被拦截。该策略允许不含 recipient 的预约交易编辑。我们的判断：不改收款人仍可能改变金额、日期，因此不能把这条放行条件直接当作完整任务授权规则。需要在单独基线中保留作者设定，再另测范围外攻击，不能为了复现零 ASR 而削弱本项目参数约束。[固定策略源码](https://github.com/deconvolute-labs/interbolt-agentdojo/blob/43e2b5fa3e7b41b7e26f7c04cc8f371ab98aa875/policies/banking/targeted.yaml)

**对后续实现的直接约束**

- 输入层继续区分待处理数据和改变任务的指令，尤其保留用户要求的验证码、邮件和网页正文；修改效果必须通过完整任务再验证。
- 动作层必须约束收款人、金额、发送内容等实际授权，不能把“来源可信”“没有修改某个字段”直接等同于用户授权。
- 数据依赖分析、模型语义审核、显式策略都是已知路线。需要以同模型消融、正常任务效用和绕过实验说明具体改进；代码重复率低不构成算法新颖证据。
- AgentArmor 的 OPI 成绩、Interbolt 的受控工具阻止率和本项目 mixed/完整 ASR 各自保留分母，不建立混合排行榜。

Interbolt 仅下载六个审阅文件，固定提交 `43e2b5fa3e7b41b7e26f7c04cc8f371ab98aa875`；[源码来源与 SHA256](../../artifacts/upstream/interbolt-agentdojo-research-20260913/manifest.json)。没有复制其实现进入首方 src。Git 传输失败后改用 GitHub API 定位提交、固定 raw 文件下载，未执行下载内容。其他比较继续参考 [SecOPD](secopd-baseline-review.md)、[既有研究比较](research-baselines-2026-09-12.md)和[当前真实评估](evaluation-history-and-code-changes.md)。

版本库保存[含许可证的审阅源码包](../../artifacts/upstream/interbolt-agentdojo-research-20260913/reviewed-source.tar.gz)及[字节校验](../../artifacts/upstream/interbolt-agentdojo-research-20260913/archive-check.json)。上游 CSV 的 CRLF 和策略注释末尾空格原样保留在包内，避免 Git 文本转换改变已登记的源码哈希；没有为通过首方空白检查而修改作者原文。
