# TRIDENT Sentinel
竞品分析报告

企业大模型与智能体自动化安全测评平台

研究截止日期：2026 年 9 月 8 日  |  面向团队决策、产品设计与竞赛论证

## 执行摘要

**定位结论：你们进入的是“企业 AI 应用自动化红队与持续安全验证”市场，而不是一块只被静态题库占据的空白市场。** 最直接的工作流对标是 Promptfoo Enterprise 与 Giskard；国内必须比较腾讯 AI-Infra-Guard、阿里云 AI Red Teaming 和百度大模型安全评测；大型企业方案还应考察 Prisma AIRS、Cisco AI Defense 及 Confident AI。

动态生成、多轮攻击、业务定制、报告和回归已经有成熟公开实现。Promptfoo 甚至提供提示词加固及复测；Giskard 可把漏洞转成回归场景；Confident AI 已提供调用链节点级风险定位。因此，“有闭环”“能定位”“会生成修复建议”均不能单独作为强差异。

结论依据：[Promptfoo 修复工作流](https://www.promptfoo.dev/docs/enterprise/remediation-reports/)；[Giskard 扫描结果与回归](https://docs.giskard.ai/hub/ui/scan/review-scan-results)；[Confident AI 链路诊断](https://www.confident-ai.com/docs/red-teaming/trace-level-detections)

**建议主张：用可度量的三维攻击覆盖、贴合企业策略的安全与误拒联合评测、可核验的修复效果，以及可交付的离线部署与审计能力来竞争。** 上述方向是本报告提出的产品选择，不是已经验证的独占优势。

### 证据与阅读边界

本报告把用户提供的 Sentinel 描述视为拟建设能力，不据此认定功能已经上线。竞品功能优先依据官方产品页、技术文档及开源仓库；“待核验”不等于“没有”。未登录付费控制台、未开展同条件实测，也不把厂商自报性能视为独立结果。

演示入口按公开视频、官方图文界面、在线控制台、开源本地部署区分。YouTube 条目已找到，但未在本环境完整播放；文档截图与历史视频不保证等同于当前线上版本。百度与火山部分资料只有功能示意或可索引文档，不包装成完整实操 Demo。

### 报告重点

竞争分层与十二家竞品档案 → 能力和交付边界 → 差异化与验证方案 → 商业落地建议 → 可点击的 Demo 目录。


---

## 01 / 竞争范围与对标顺序

比较单位应是“具体产品版本＋交付方式”，不是公司品牌。开源库、商业平台、运行时防护和研究基准可能属于同一生态，但不能把它们的功能无条件合并成一个产品。

| 层级 | 竞品 | 对 Sentinel 的主要压力 |
| --- | --- | --- |
| 工作流直接竞品 | Promptfoo Enterprise；Giskard Hub | 接入、造题、攻击、判定、问题管理、回归的一体化工作流 |
| 企业安全套件 | Prisma AIRS；Cisco AI Defense；Check Point / Lakera Red | 将 AI 验证与既有安全管理、运行时防护及企业采购结合 |
| 国内产品与开源替代 | 腾讯 AI-Infra-Guard；阿里云 AI Red Teaming；百度大模型安全评测 | 本地工程参考、云端低接入门槛、中文风险测评与报告 |
| 评测与可观测性平台 | Confident AI / DeepTeam；Scale SGP | 将安全检测接入链路、人工评价、数据集及版本管理 |
| 云生态内置能力 | Microsoft Foundry AI Red Teaming Agent | 客户在已有 AI 开发平台内完成红队，不另购独立平台 |
| 国内持续跟踪 | 火山引擎大模型安全测评 | 公开目录覆盖资产、题库、测试与报告；部分细节需进一步演示核验 |

上述分层是按公开功能做出的竞争判断，并非市场份额、收入或实际采购排名。各项能力的依据和可访问材料见后续档案。

### 优先投入研究的五家

**Promptfoo：** 检查完整功能同质化风险。**Giskard：** 学习失败证据与回归场景的产品闭环。**Confident AI：** 检查“调用链定位”是否已经撞车。**腾讯 A.I.G：** 衡量客户自建开源平台的工程门槛。**阿里云：** 分析国内接入、交付边界与计费方式。

### 对比时必须拆开的五组概念

支持私有模型，不等于平台完全离线；保存聊天记录，不等于整个 Agent 环境可复现；提供修复建议，不等于补丁已部署且有效；拥有很多攻击名称，不等于覆盖很多独立风险；测试用户权限，不等于平台本身具备权限审计。

### 不应混进同一排名的对象

TRIDENT、FORTRESS 这样的研究方法或基准更适合讨论技术来源和评测方法；企业平台才适合比较权限、工作流、部署和持续验证。CyberGym 等真实漏洞能力评测也不应与文本/智能体应用安全红队按同一产品指标排名。

方法边界依据：[TRIDENT 原论文](https://aclanthology.org/2025.acl-long.733/)；[FORTRESS 官方说明](https://labs.scale.com/leaderboard/fortress)


---

## 02 / 直接竞品：Promptfoo 与 Giskard

### 2.1 Promptfoo Enterprise：功能重合度最高的对标之一

**公开能力。** 面向业务目的生成测试，覆盖提示词、RAG 数据访问和工具/应用边界；提供测试报告、CI 工作流及企业治理。企业版支持本地化交付、角色与团队管理。其修复报告可把漏洞对应到提示词、输入输出过滤、配置及架构建议，并通过 Harden Prompt 生成加固提示词、复测后由用户部署。

**竞争含义。** Sentinel 的“自动生成—测试—证据—建议—回归—私有化”组合，已经与其企业版直接重叠。不能以社区版缺少某项治理功能，推断其整个产品都缺少。

**建议应对。** 不比策略名称数量；在相同目标、预算和判题标准下比较“独立有效漏洞/成本”，并证明中文行业策略、误拒控制或离线交付中的具体收益。生成提示词与自动上线是两回事，Sentinel 同样应保留审批和回滚。

依据：[企业版本与部署](https://www.promptfoo.dev/docs/enterprise/)；[红队产品能力](https://www.promptfoo.dev/red-teaming/)；[修复报告与加固界面](https://www.promptfoo.dev/docs/enterprise/remediation-reports/)

Demo：[官方实机视频](https://www.youtube.com/watch?v=e7MlDhfN22s)；[Dashboard 原图](https://www.promptfoo.dev/assets/images/promptfoo-dashboard-6ed26392d614661cc84a11d85c865ff5.png)

观看重点：目标与业务目的配置 → 扫描报告 → 漏洞详情 → 修复建议 → 加固提示词复测。视频为已找到的演示入口，未逐帧验证当前版本。

### 2.2 Giskard Hub：失败进入持续验证的产品参考

**公开能力。** 按业务上下文动态进行多轮攻击；可结合知识材料生成场景。结果页展示风险类别、攻击尝试、目标输入输出和判断依据，并支持标记误报、发送到数据集和创建任务。官方也把过拒与其他质量失败列为评测内容。

**竞争含义。** “不是只测安全，还测过拒”“发现漏洞后加进回归集”都不能作为 Sentinel 的独占特点。其交互值得学习：一条失败应能直接进入可追踪的复测场景，而不是停在一次性报告里。

**建议应对。** 将差异落在业务策略约束、对照诊断的可靠性与修复验证，而不是再做一套相似的风险看板。公开材料证明了场景化回归，但完整知识库和工具状态是否可冻结重放，需要实际演示核验。

依据：[连续红队产品](https://www.giskard.ai/products/continuous-red-teaming)；[结果页与场景转换](https://docs.giskard.ai/hub/ui/scan/review-scan-results)；[官方质量能力自述](https://www.giskard.ai/knowledge/best-ai-agent-red-teaming-tools-in-2026-understanding-features-functions-and-solutions)

Demo：[完整 UI 文档](https://docs.giskard.ai/hub/ui)；[扫描结果原图](https://docs.giskard.ai/_static/images/hub/scan/scan-results.png)；[官方演示视频入口](https://www.youtube.com/watch?v=T9w7wuVZjfc)


---

## 03 / 企业安全套件：Prisma AIRS 与 Cisco

### 3.1 Prisma AIRS AI Red Teaming：模型、应用和 Agent 的统一扫描

**公开能力。** Palo Alto Networks 的官方入门文档列出模型、应用和智能体目标，支持目标画像与接口配置；扫描模式区分攻击库扫描、动态 Agent 扫描、自定义提示词集合。流程覆盖扫描、风险报告、攻击序列及框架映射，产品页提供动态多轮和业务定制说明。

**竞争含义。** 企业需要的不只是一台攻击生成器，还需要目标资产、访问方式、业务约束、风险分级和可复查证据。Sentinel 所列的“系统提示词、RAG、工具调用”必须对应具体接入点，不能只在目标下拉框写三种名称。

**边界。** 官方文档列有许可要求。可连接私有目标不能推出整个平台支持完全离线；本次未取得后者的完整部署证据，也未核验独立的误拒评测工作流。

**建议应对。** 借鉴目标画像与扫描模式的区分：已知攻击回归、自适应问题发现、用户自定义策略测试，不应混为一个结果口径。

依据 / Demo：[产品页与内嵌演示](https://www.paloaltonetworks.com/ai-security/ai-red-teaming)；[含界面步骤的入门文档](https://docs.paloaltonetworks.com/ai-runtime-security/ai-red-teaming/identify-ai-system-risks-with-ai-red-teaming/get-started-with-prisma-airs-ai-red-teaming)

访问条件：产品页和图文公开；真实扫描需要相应许可与环境。页内动画不等于完整可操作沙盒。

### 3.2 Cisco AI Defense / Explorer：自适应攻击已经产品化

**公开能力。** Explorer 官方演示按目标、测试深度、攻击目标、运行和报告组织流程；支持自然语言定义目标，并用自适应多轮方式攻击目标系统。AI Defense 产品范围更广，还涉及发现、验证及运行时防护。

**竞争含义。** “根据企业业务策略演化攻击”本身已有产品先例。Explorer 是验证入口，不能把 AI Defense 全套安全功能都当作这个入口默认拥有的能力，也不能反向用入口的简化功能概括整套产品。

**建议应对。** 首期不与大型安全套件比功能宽度，选择有明确数据边界的行业场景，证明更易接入、更可复查的测试与修复流程。离线部署、额度和授权范围应以实际方案确认。

依据：[官方 Explorer 操作演示](https://blogs.cisco.com/ai/ai-defense-explorer-lab)；[AI Defense 产品范围](https://www.cisco.com/site/us/en/products/security/ai-defense/index.html)

Demo：[在线 Explorer 入口](https://explorer.aidefense.cisco.com/)；[官方 Validation 视频，约 9 分钟](https://community.cisco.com/t5/security-videos/success-capsules-cisco-ai-defense-validation/ba-p/5560298)

观看重点：测试深度设置、自然语言业务目标、扫描结果解释。在线入口可访问，但并不意味着无需账号、无限免费或所有区域均可使用。


---

## 04 / 国内替代：腾讯 A.I.G 与阿里云

### 4.1 腾讯 AI-Infra-Guard：最值得本地体验的开源工程基线

**公开能力。** 官方仓库提供 Web UI 与本地部署，覆盖模型越狱、Agent、MCP、Skill 及 AI 基础设施扫描，并公布多轮攻击能力。README 包含系统及插件管理动图，适合直接研究前端信息架构和扫描任务流程。

**明确边界。** 仓库警告当前缺少认证机制，主要面向个人和企业内网，不能直接暴露在公网。因此，开源可部署不等于已经达到企业生产环境的身份、隔离与审计要求。

**竞争含义。** 客户可能用它自建基础能力，Sentinel 需要交付比“套一层 Web UI”更强的价值：身份鉴别、租户隔离、凭据管理、证据权限、人工确认与缺陷工单、可验证回归。开源代码无许可费不等于没有模型调用、集成和维护成本。

依据：[官方仓库、能力和认证警告](https://github.com/Tencent/AI-Infra-Guard)；[使用文档](https://tencent.github.io/AI-Infra-Guard/)

Demo：[系统界面动图](https://github.com/Tencent/AI-Infra-Guard/blob/main/img/aig.gif)；[插件管理动图](https://github.com/Tencent/AI-Infra-Guard/blob/main/img/plugin-gif.gif)

访问条件：仓库和动图公开；系统需自行部署。部署后 localhost 地址不是公网体验站。

### 4.2 阿里云 AI Red Teaming：国内云交付与计费标杆

**公开能力。** Agent 安全中心下的功能支持模型与智能体评估，文档列出公网和企业内网目标接入、报告查看以及命中数据导出。报告包含风险分布、攻击手法、恶意意图、问题案例与建议。

**明确边界。** 内网接入由企业侧测试机执行调用后回传结果，要求能够访问外网；这不是整个平台完全离线。文档同时指出尚不自动处理或同步至风险清单。此处可作为 Sentinel 的交付与工单闭环对照，而非泛称“对方不支持私有化”。

**计费信息。** 当前中文官方文档标示成功完成的扫描为 1,000 元/次，且有付费实例前提；中断或未完成不扣该次费用。该数字是核验时文档标价，不等于最终合同总价或所有地域价格。

依据：[官方接入、结果、限制与计费文档](https://help.aliyun.com/zh/asc/user-guide/ai-red-teaming)

Demo：[安全中心控制台入口](https://yundun.console.aliyun.com/)

访问条件：操作文档公开；真实扫描需账号和相应服务。重点核验内网出站要求、报告导出、风险工单是否自动同步。


---

## 05 / 国内云与开发生态：百度、Microsoft

### 5.1 百度大模型安全评测：不是静态题库产品

**公开能力。** 官方介绍包含按风险构造数据、自动改写与攻击增强、定制业务数据、自动问答与标注、理由说明、数据看板、报告及建议；也列出行业定制和智能体相关风险场景。

**竞争含义。** “自动生成符合行业的攻击题＋自动测评＋报告”在国内已有直接对照。不能把百度描述为只提供固定敏感问答，也不宜拿厂商自报题量、准确率直接证明性能高低。

**待核验。** 本次未找到专门完整展示该安全评测控制台的可靠官方公开视频；官方产品页有功能示意，但不等同于完整操作录像。对模型本身的安全测评与企业 RAG/工具链端到端接入能力，应在演示中分别确认。

**建议应对。** 用一条真实企业业务流程，展示正常请求、恶意请求和工具越权风险如何被共同评估，以及修复后正常服务是否仍然有效。不要只比“数据集规模”。

依据 / Demo：[官方产品页与功能示意](https://cloud.baidu.com/product/AIGCSEC/benchmark.html)；[安全评测产品文档](https://cloud.baidu.com/doc/AIGC_SEC/s/lmn8dany0)

### 5.2 Microsoft Foundry AI Red Teaming Agent：平台内置替代

**公开能力。** 利用 PyRIT 组织攻击转换与执行，并提供多轮或间接攻击以及面向 Agent 的风险评估。Foundry 概念文档区分不同风险类型、目标和运行方式，而不是所有能力都使用相同限制。

**明确边界。** 部分 Agent 风险类别目前限定云端、英语或单轮，并可能使用模拟工具；不能据此说整个产品不支持多轮。云端报告还会对有害攻击输入进行删减，这涉及原始证据留存与展示的取舍。

**竞争含义。** 客户可能在已有开发平台内完成评测，而不是另购工具。Sentinel 应强调跨平台、中文业务和可控证据治理，但不能把开源 PyRIT 与 Foundry 云服务都称为“不能私有化”的同一产品。

依据：[当前功能与限制](https://learn.microsoft.com/en-us/azure/foundry/concepts/ai-red-teaming-agent)

Demo：[Microsoft 官方实机演示](https://learn.microsoft.com/en-us/shows/ai-show/ai-red-teaming-agent-in-azure-ai-foundry)

视频日期为 2025-05-05：08:48 Demo；11:16 攻击策略；13:07 扫描结果；15:05 Judge。适合参考流程，不代表 2026 年控制台所有布局。


---

## 06 / 链路与修复：Confident AI、Lakera

### 6.1 Confident AI / DeepTeam：不能忽视的诊断竞品

**公开能力。** 商业平台提供无代码风险评估、报告和自定义框架，开源 DeepTeam 是代码侧入口。完成埋点并用测试标识关联后，Trace-Level Detections 可检查调用树中各节点的输入输出，标记风险位置。

**关键细节。** 风险分为已到达用户、已被下游缓解、仅尝试但未突破。界面可从调用树打开节点并查看漏洞类型、攻击方向与判定理由。这与 Sentinel 所说的“完整攻击证据和薄弱环节定位”高度重叠。

**边界与应对。** 节点级诊断是 Enterprise 能力，不能把免费 DeepTeam 等同于完整商业平台。其归因依赖评价模型对链路的判断，也不是天然的因果证明。Sentinel 更有价值的目标是通过受控修改和复测，证明哪个修复消除了风险，而不是只用另一个 Judge 给节点贴标签。

依据：[红队版本说明](https://www.confident-ai.com/docs/red-teaming/introduction)；[节点级检测文档](https://www.confident-ai.com/docs/red-teaming/trace-level-detections)

Demo：[含完整界面的无代码评估教程](https://www.confident-ai.com/docs/red-teaming/no-code-assessments/quickstart)；[产品账号入口](https://app.confident-ai.com/)；[DeepTeam 仓库](https://github.com/confident-ai/deepteam)

### 6.2 Check Point AI Red Teaming / Lakera Red：已有重放与复测闭环

**公开能力。** 官方红队文档覆盖模型和智能体风险，包括间接上下文攻击。修复文档明确要求复放原始对话、检查相近变体、再次扫描，并通过 Compare 查看变化；另有 CI/CD 接入说明。

**竞争含义。** 不能宣称“竞品只生成一次报告，而 Sentinel 能复测”。其修复工作流说明正好可以作为验收对照：修复后原攻击是否失败？相似变体是否仍成功？是否产生新问题？

**边界与应对。** Lakera 的防护产品与红队产品不是一回事；不能用 Guard 的部署能力证明 Red 完全离线，也不能把防护 Playground 当成红队平台 Demo。Sentinel 可探索保存更完整的业务状态、证明修复不损害正常功能，但收益需要实验支持。

依据：[红队产品文档](https://docs.lakera.ai/red)；[修复与重放验证](https://docs.lakera.ai/docs/red/remediation)；[CI/CD 文档](https://docs.lakera.ai/docs/red/sdk-how-tos/run-scans-in-ci-cd)

Demo：[结果解读](https://docs.lakera.ai/docs/red/interpreting-results)；[产品页与预约演示](https://www.lakera.ai/lakera-red)

访问条件：上述技术文档公开；未找到可充分确认的完整公开控制台演示视频，实际产品需预约或账号。


---

## 07 / 相邻竞品：Scale 与火山引擎

### 7.1 Scale SGP / FORTRESS：平台和基准应拆开看

**SGP 的产品参考价值。** 官方 UI 导览展示应用版本、逐样本评估结果、评价规则、数据集、人工评价以及训练数据等页面。它更适合研究“评价—审核—数据管理”这一段，不宜仅凭该界面就认定它拥有与 Sentinel 相同的动态红队体系。

**FORTRESS 的方法参考价值。** 官方基准使用对应的恶意与正常请求、针对实例的评分规则，同时测风险和过拒。它说明“恶意题配正常题”“同时看安全与帮助”已有前序工作，但排行榜不是企业红队控制台。

**建议应对。** 学习标准答案/预期行为、模型输出、评价和人工复核的同屏呈现；对相近业务任务建立对照时，重点证明对照质量、诊断增益和修复价值，而不是仅声称组织成对就是创新。

依据 / Demo：[SGP 官方 UI 导览与截图](https://docs.gp.scale.com/docs/intro-to-the-sgp-ui)；[FORTRESS 方法与交互排行榜](https://labs.scale.com/leaderboard/fortress)

访问条件：图文与排行榜公开；SGP 实际系统需账号。排行榜只用于理解评测方法，不作为平台产品 Demo。

### 7.2 火山引擎大模型安全测评：国内采购对照，证据仍需补全

**已公开的入口。** 官方文档目录包括资产检测、结果与报告、风险题库等，FAQ 索引说明多轮攻击技术被内置到检测规则库。可作为国内产品的持续跟踪对象。

**证据限制。** 本次浏览环境未能完整提取部分动态页面正文，因此不把其最新控制台、完整离线部署、修复自动化或所有工具链覆盖写成已核验事实。也没有找到足以确认的完整专用官方实操视频。

**建议应对。** 用相同采购清单要求演示：目标接入类型、测试深度、完整对话证据、误报标注、版本对比、出站依赖以及报告格式。不要把“公开信息较少”当作产品较弱。

资料入口：[快速入门](https://www.volcengine.com/docs/87039/2005258)；[常见问题](https://www.volcengine.com/docs/87039/2023897)；[风险题库文档](https://www.volcengine.com/docs/87039/2023896)

### 研究来源与产品能力的最后一道边界

TRIDENT 原论文的三维是词汇表达、恶意意图和越狱策略，主要贡献在红队数据合成及相关安全训练实验。“恶意意图多样性”不自动推出正常/模糊/恶意三类对照或可靠误拒评估，更不自动推出多轮 Agent、RAG 接入、权限审计、企业合规报告等功能。上述工程能力需要分别实现与验收。

依据：[TRIDENT：ACL 2025 原文页面](https://aclanthology.org/2025.acl-long.733/)


---

## 08 / 能力矩阵与真实交付边界

标记说明：明确＝公开文档有相应说明；部分＝只确认部分范围或有具体限制；待核＝本次证据不足。矩阵不代表实测性能；“明确”也不等于无限制或默认免费。

| 产品 | 动态/多轮 | 业务定制 | RAG/工具风险 | 修复/复测 | 关键说明 |
| --- | --- | --- | --- | --- | --- |
| Promptfoo 企业版 | 明确 | 明确 | 明确 | 明确 | 含提示词加固、治理与私有交付 |
| Giskard Hub | 明确 | 明确 | 明确 | 明确 | 失败转场景；公开包含质量与过拒 |
| Prisma AIRS | 明确 | 明确 | 明确 | 部分 | 动态 Agent、攻击库、自定义集分开 |
| Cisco Explorer | 明确 | 明确 | 部分 | 部分 | 勿与 AI Defense 全套防护混同 |
| 腾讯 A.I.G | 明确 | 部分 | 明确 | 部分 | 公开版缺认证，需补生产治理 |
| 阿里云 | 部分 | 部分 | 部分 | 部分 | 内网结果回云；无自动处置/风险同步 |
| 百度 | 部分 | 明确 | 部分 | 部分 | 造题、增强和报告明确；端到端需演示 |
| Microsoft Foundry | 明确 | 明确 | 明确 | 部分 | 各风险类别受支持范围不同 |
| Confident AI | 明确 | 明确 | 明确 | 部分 | 具备节点级风险检测；不是因果证明 |
| Check Point / Lakera | 明确 | 明确 | 明确 | 明确 | 有原对话复放、变体复测、CI 文档 |

矩阵依据为第 2—6 章各产品官方资料。“修复/复测”指建议或复测工作流，不代表平台会自动修改客户生产系统。Giskard 的“RAG/工具风险”也不等于已确认任意工具状态可快照。

### 哪些差异已经能用文件证据说明？

| 对象 | 本次可确认的边界 | Sentinel 应如何回应 |
| --- | --- | --- |
| 腾讯 A.I.G | 公开仓库明确缺少认证 | 给出实际可验收的身份、隔离、审计方案 |
| 阿里云 | 内网接入依赖出站；未自动同步风险清单 | 验证真正离线部署与完整问题工单闭环 |
| Microsoft Foundry | 部分 Agent 风险有语言/运行方式限制；云端证据删减 | 按风险类别比较中文覆盖和受控原始证据留存 |
| Promptfoo / Giskard | 很多拟卖点已有公开实现 | 只有同条件测试和交付证据才能支持差异 |

边界依据：[腾讯仓库警告](https://github.com/Tencent/AI-Infra-Guard)；[阿里云限制](https://help.aliyun.com/zh/asc/user-guide/ai-red-teaming)；[Foundry 当前范围](https://learn.microsoft.com/en-us/azure/foundry/concepts/ai-red-teaming-agent)


---

## 09 / Sentinel 的差异化应怎样证明？

### 9.1 三维多样化：从论文标签变成覆盖收益

建议记录每个样本的业务策略、风险点、词汇变换、恶意目标与越狱策略，并保留父样本和变换来源。核心比较不是“生成更多句子”，而是相同调用预算下多发现多少独立、有效且有业务价值的问题。新表述但同一失败机制不应反复计成新漏洞。

推荐对照：固定题库、普通大模型造题、单维变换、三维组合。固定攻击目标、预算、Judge 和抽样复核方式。论文来源可以支持设计动机，不能替代 Sentinel 自身实验。

### 9.2 安全与误拒：必须有独立的正常业务任务集

恶意样本再多，也无法单独得到有意义的误拒绝率。应先定义正常请求的允许边界及预期帮助，再评估“危险帮助是否放行”与“合法业务是否被错误挡住”。模糊目的、双用途任务应按请求内容判定，不能默认拒绝。

成对或成组任务可帮助诊断：只改表达时处理应大致稳定，改变关键用途或权限时处理可以合理改变。但这不是新的空白概念；要证明其比逐条判分多发现了什么问题，并控制标签质量。

### 9.3 可重放证据：不能只保存 Prompt 和 Response

推荐证据包包含：模型与接口版本、系统提示词版本、生成参数、会话与身份权限、知识库快照或检索片段、工具输入输出及模拟状态、评价规则与 Judge 版本、人工复核记录和运行标识。为含敏感信息的原始记录设置访问控制、脱敏与保存期限。

要区分“原攻击重放”“原工具结果冻结重放”和“在新环境重新执行”。外部服务和随机模型往往无法保证逐字相同，因此报告应展示多次执行的复现比例和变化原因，而不是承诺任何任务 100% 重放。

### 9.4 修复验证：从建议文本走到可审核的效果证明

修复对象可能是系统提示词、检索权限、工具授权、输入输出策略或工作流，而不只是微调模型。每条建议应指向负责人和配置版本，批准后在原失败案例、相近未见变体及正常业务集上复测。只有修复降低风险且未明显损害正常服务，才可标记“验证通过”。

Promptfoo 已有加固与复测，Lakera 已有原对话和变体重测，Confident AI 已有链路节点诊断。因此更有价值的差异是“修复验证更可靠、复现范围更明确、正常业务损伤更低”，而非声称首次建立闭环。

已有能力对照：[Promptfoo 修复基线](https://www.promptfoo.dev/docs/enterprise/remediation-reports/)；[Lakera 复测基线](https://docs.lakera.ai/docs/red/remediation)；[Confident AI 诊断基线](https://www.confident-ai.com/docs/red-teaming/trace-level-detections)


---

## 10 / 竞争验证实验与验收指标

以下是建议的首轮 PoC 设计，不是已完成实验，也不是行业标准。先用受控测试环境，不接管真实转账、删库或其他高风险生产操作。

### 实验对象与公平条件

选三类目标：纯模型助手、带企业知识库的 RAG 助手、带只读或模拟工具的 Agent。至少比较 Sentinel、Promptfoo、一个开源红队基线，以及固定题库。商业闭源产品未能取得账号时，明确留空，不用模拟数据代替。

固定同一模型/应用版本、企业策略、测试预算、并发和轮次上限。按业务任务或根样本划分发现集、修复集和独立测试集，不能让最终测试集的改写进入修复训练或攻击优化。固定回归与动态探索互补，不应把静态测试本身当作过时。

| 指标 | 建议口径 | 要避免的误导 |
| --- | --- | --- |
| 攻击成功率 | 有效攻击中违反预先确定业务/安全规则的比例 | 不同目标、预算和 Judge 的 ASR 不可直接比较 |
| 有效发现效率 | 经确认且去重的失败机制数 ÷ 测试成本 | 反复命中同一漏洞不等于覆盖更广 |
| 误拒绝率 | 允许请求中被错误拒绝的数量 ÷ 允许请求总量 | 只用恶意样本得不到误拒率 |
| 正常业务成功率 | 合法测试中达到预期服务目标的比例 | 拒绝减少不一定意味着帮助质量提高 |
| 风险覆盖 | 实际测试的适用策略单元 ÷ 预定义适用单元 | 分母是业务风险目录，不是厂商插件数 |
| 误报与判分可靠性 | 人工复核一致率、误报率及不确定案例处理 | Judge 同意自己生成的标签不是独立验证 |
| 证据复现率 | 固定范围重放中重复出现同一风险的比例 | 区分冻结工具结果和重新执行外部工具 |
| 修复泛化与副作用 | 原失败减少、未见变体风险、正常任务变化 | 只重测原攻击通过不能证明完成修复 |

### 建议的交付门槛

每项新增优势都应对应可重跑的配置、原始证据和人工抽样。样本量较小时给出不确定性范围，不凭一两条成功案例宣传收益。发现阶段可以自适应增加难例，但正式比较必须保留不参与发现和修复的测试任务。


---

## 11 / 商业切入、版本与采购问题

### 11.1 从单一业务切口切入，不同时覆盖所有行业

建议首期选择用户已列行业中的一个知识型助手场景，例如金融客服知识问答或电信内部知识助手，先支持模型、知识检索与只读工具。避免同时承诺所有医疗建议、政务决策和高权限 Agent 场景。选择依据应是可获取的客户测试环境、授权与高质量标注能力，而非笼统行业规模判断。

### 11.2 版本边界应围绕企业交付，而不是攻击题数量

| 阶段 | 建议交付 | 暂不承诺 |
| --- | --- | --- |
| P0：可核验的评测闭环 | 目标配置、业务策略、三维生成、执行日志、安全/误拒评分、人工复核、报告、固定回归 | 完整自动根因分析、自动部署修复、所有行业通用 |
| P1：Agent 与企业治理 | 检索/工具链证据、可定义的重放、提示词和策略修复验证、角色审计、工单与 CI | 任意外部系统逐字复现、未经批准的高权限操作 |
| P2：行业资产与交付扩展 | 行业策略包、离线生成与 Judge、历史风险画像、更多版本和集成适配 | 用一次项目结果宣称跨行业普遍收益 |

历史风险画像应基于固定策略版本、标准化指标和持续测量；不同项目使用不同风险目录时，不能简单把分数画在一张行业排行榜上。

### 11.3 总成本比较与价格锚点

腾讯等开源替代的主要成本在模型调用、计算资源、接入与维护；商业版还可能增加许可、支持和治理成本。阿里云官方给出单次成功扫描标价，但仍有前置实例费用。未拿到正式报价的厂商，不编造每月费用或成本优势。

费用结构依据：[阿里云当前计费说明](https://help.aliyun.com/zh/asc/user-guide/ai-red-teaming)；[Promptfoo 版本对比](https://www.promptfoo.dev/docs/enterprise/)；[腾讯开源交付说明](https://github.com/Tencent/AI-Infra-Guard)

### 11.4 演示和采购必须问清楚

要求供应商实际展示：完全离线时哪些模块仍调用外部服务；是否覆盖整段工具链而非最终回答；原始证据能否受控导出；回归是复放原例还是重新随机扫描；修复后是否同时测正常业务；平台自身是否有身份、权限、审计和凭据隔离。

“合规报告”在产品描述中应准确写为风险发现与标准条目映射、整改证据整理。平台报告不应被包装成监管认可、法律意见或无条件通过认证的承诺；正式用途需依具体标准、版本和审核主体核验。


---

## 附录 A / Demo 导航：优先观看的六家

所有链接为官方产品、文档、账号入口或官方仓库。视频和页面可用性、访问地区及账号权限会变化；“公开入口”不表示可以匿名执行付费扫描。

### 01  Promptfoo

实机视频＋真实界面图文

打开：[端到端演示视频](https://www.youtube.com/watch?v=e7MlDhfN22s)；[Dashboard 原图](https://www.promptfoo.dev/assets/images/promptfoo-dashboard-6ed26392d614661cc84a11d85c865ff5.png)；[修复与 Harden Prompt 界面](https://www.promptfoo.dev/docs/enterprise/remediation-reports/)

先看业务目标配置，再看漏洞报告如何跳转修复与复测；把社区功能与企业授权区分开。

### 02  Giskard

UI 手册＋结果截图＋视频入口

打开：[完整 UI 文档](https://docs.giskard.ai/hub/ui)；[扫描结果详情](https://docs.giskard.ai/hub/ui/scan/review-scan-results)；[官方演示视频入口](https://www.youtube.com/watch?v=T9w7wuVZjfc)

看攻击尝试、输入输出、Judge 理由、误报标记、Send to dataset 与任务管理；失败怎样变成回归场景。

### 03  Confident AI

含截图的无代码教程＋链路节点界面

打开：[无代码安全评估 Quickstart](https://www.confident-ai.com/docs/red-teaming/no-code-assessments/quickstart)；[Trace-Level Detections 界面](https://www.confident-ai.com/docs/red-teaming/trace-level-detections)；[应用入口](https://app.confident-ai.com/)

看目标连接、框架选择、报告、节点风险，以及已发生/已缓解/仅尝试的区别。实际红队需 Enterprise。

### 04  腾讯 AI-Infra-Guard

开源仓库＋界面动图＋可本地部署

打开：[官方项目与部署说明](https://github.com/Tencent/AI-Infra-Guard)；[主界面动图](https://github.com/Tencent/AI-Infra-Guard/blob/main/img/aig.gif)；[插件界面动图](https://github.com/Tencent/AI-Infra-Guard/blob/main/img/plugin-gif.gif)

看扫描入口、插件/数据资产和任务结果。公开版本认证警告应纳入企业部署评审。

### 05  Microsoft Foundry

官方带章节实机视频＋当前文档

打开：[官方实机演示](https://learn.microsoft.com/en-us/shows/ai-show/ai-red-teaming-agent-in-azure-ai-foundry)；[当前能力与限制](https://learn.microsoft.com/en-us/azure/foundry/concepts/ai-red-teaming-agent)

2025 年视频：08:48 演示、11:16 策略、13:07 结果、15:05 Judge；按当前文档确认实际能力。

### 06  Cisco AI Defense Explorer

官方流程演示＋线上入口＋短视频

打开：[Explorer Lab 图文演示](https://blogs.cisco.com/ai/ai-defense-explorer-lab)；[Explorer 产品入口](https://explorer.aidefense.cisco.com/)；[Validation 官方视频](https://community.cisco.com/t5/security-videos/success-capsules-cisco-ai-defense-validation/ba-p/5560298)

看目标、深度、自然语言攻击目标、动态测试和报告。视频约 9 分钟；使用额度与授权另行确认。


---

## 附录 B / Demo 导航：企业套件与国内云

### 07  Prisma AIRS AI Red Teaming

产品内嵌演示＋官方界面操作文档

打开：[红队产品页](https://www.paloaltonetworks.com/ai-security/ai-red-teaming)；[配置到报告的操作文档](https://docs.paloaltonetworks.com/ai-runtime-security/ai-red-teaming/identify-ai-system-risks-with-ai-red-teaming/get-started-with-prisma-airs-ai-red-teaming)

看目标画像、三种扫描模式及报告证据。正式运行有许可要求；内嵌动画不是公开沙盒。

### 08  阿里云 AI Red Teaming

操作文档＋账号控制台

打开：[完整接入与报告说明](https://help.aliyun.com/zh/asc/user-guide/ai-red-teaming)；[安全中心控制台](https://yundun.console.aliyun.com/)

看内网测试脚本、结果回传、命中数据导出、风险清单同步边界以及成功扫描计费。未确认完整公开实操视频。

### 09  百度大模型安全评测

产品功能示意＋官方文档

打开：[产品页](https://cloud.baidu.com/product/AIGCSEC/benchmark.html)；[功能文档](https://cloud.baidu.com/doc/AIGC_SEC/s/lmn8dany0)

看数据生成、攻击增强、标注和报告。公开材料不能替代完整控制台演示；不把通用百度 Demo Day 当该产品 Demo。

### 10  Check Point / Lakera Red

技术文档＋预约产品演示

打开：[红队文档](https://docs.lakera.ai/red)；[结果解释](https://docs.lakera.ai/docs/red/interpreting-results)；[原攻击重放与修复复测](https://docs.lakera.ai/docs/red/remediation)；[产品与预约入口](https://www.lakera.ai/lakera-red)

看对话证据、原例与变体重测、Compare。Guard Playground 不是 Red 的系统演示。

### 11  Scale SGP / FORTRESS

UI 图文导览＋交互基准页面

打开：[SGP UI Walkthrough](https://docs.gp.scale.com/docs/intro-to-the-sgp-ui)；[FORTRESS 方法与排行榜](https://labs.scale.com/leaderboard/fortress)

SGP 看逐样本结果、Rubric、人工审核和数据集；FORTRESS 看恶意/正常配对。两个入口用途不同。

### 12  火山引擎大模型安全测评

官方入门、FAQ 与题库文档

打开：[快速入门](https://www.volcengine.com/docs/87039/2005258)；[FAQ](https://www.volcengine.com/docs/87039/2023897)；[风险题库](https://www.volcengine.com/docs/87039/2023896)

本环境仅部分文档可完整读取。应在浏览器或商务演示核验最新界面与部署细节，暂不认定有完整公开视频。


---

## 附录 C / 产品表达与 UI 验收建议

### 建议对外表达

TRIDENT Sentinel 面向企业大模型与智能体应用，基于三维多样化红队方法构建业务策略驱动的自动化测试。平台联合评估危险帮助、错误拒绝与应用边界违规，保留可审计的攻击证据，并将风险发现连接到经人工确认的修复与独立回归验证。产品的差异化目标，是在有限测试预算下提高有效风险发现效率，同时减少安全加固对正常业务的损伤。

这段表述中的“差异化目标”应在取得实验与交付证据后再改为结果性承诺。若权限审计、CI/CD、离线部署仍未实现，应在方案或路演中标注为规划能力，而不是描述为客户已可使用。

### 建议的七个核心页面

| 页面 | 核心信息与操作 | 主要参考 |
| --- | --- | --- |
| 资产与业务策略 | 模型/应用/Agent、权限、允许边界、提示词与知识库版本 | Prisma AIRS、Promptfoo |
| 创建测试 | 风险范围、三维生成配置、预算、策略、Judge 与正常对照集 | Promptfoo、Cisco Explorer |
| 运行与风险概览 | 任务状态、严重度、风险类型、成本和覆盖分母 | Giskard、腾讯 A.I.G |
| 攻击证据与调用链 | 完整会话、检索片段、工具输入输出、节点检测及权限 | Giskard、Confident AI |
| 人工确认与问题管理 | 误报、不确定性、责任人、修复版本、工单与证据导出 | Giskard、Promptfoo |
| 修复验证 | 提示词/权限/工作流变更、审批、原例与未见变体复测 | Promptfoo、Lakera |
| 回归与报告 | 安全、误拒、正常业务成功率、复现率及标准条目映射 | Microsoft、Scale；指标自行定义 |

### 最终判断

**最不应做的，是把竞品画成静态题库，然后把所有现成功能归为 Sentinel 创新。最值得做的，是拿出别人也能复测的证据，说明你们在某类业务、某种部署边界或某个评价难点上，确实发现得更有效、修复得更可靠。**

建议先让团队按附录 A 依次研究 Promptfoo、Giskard、Confident AI 和腾讯 A.I.G，再以阿里云、百度的交付方式校准国内客户的采购预期。对公开信息尚不充分的项，保留演示核验问题，不自行补全。
