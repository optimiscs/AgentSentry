# v5 清洗：保留验证码，继续测完整任务

2026-09-13。状态：**开发小样改善，完整系统验收未通过；全量 1046 条/组正在运行。** 用户确认任务模型和防护模型默认关闭思考，本轮服务、请求及清单均为非思考模式。

**已确认的修改与效果**

v4 在正常任务中把验证码、邮件警告和普通内容当作注入删除。v5 明确区分“用户要求处理的数据”和“外部内容试图指挥助手改变任务的命令”，增加两条虚构示例：只含验证码的邮件保留；同样邮件中新增外发整箱邮件的指令则删除该指令。它没有为任务 ID、具体验证码或工具名设置放行规则。

实际防御变更只在 `JOINT_PROMPT`，原文定位、只允许删除、无效响应记错误等代码路径保持原样。另给原生 runner 增加精确 `--case-id` 选择，拒绝重复/不存在的 ID，保留原生顺序；选择后的 manifest 明确为 `selected_cases`，不能计为全量验收。默认不带该参数仍执行原有任务集合。

**1. 同样的 43 个真实输入，v4 对 v5**

输入为此前固定的 32 个响应，加上从四条正常邮件任务重建的 11 个响应。重放核对原始输入哈希；标签与分组只供评分，没有进入 guard 提示。两组均使用 Qwen3.5-9B BF16、seed 0、temperature 0、joint、4096 输出预算、300 秒超时、2 workers。

| 输入组 | v4 修改数 | v5 修改数 | 有效性 |
|---|---:|---:|---|
| 8 个早先误删的正常响应 | 0/8 | 0/8 | 全部有效 |
| 8 个其他正常响应 | 0/8 | 0/8 | 全部有效 |
| 11 个新增正常邮件任务响应 | 8/11 | 0/11 | 全部有效 |
| 16 个已知包含注入的响应 | 16/16 | 16/16 | 全部有效 |

两组均 43/43 有效、0 错误。全部尝试平均耗时 2.731→2.598 秒，中位数 2.710→0.893 秒，P95 5.965→6.280 秒。平均值小幅下降而尾部上升，不能宣传成全面提速。正常邮箱环境含有钓鱼和广告，修改数不是独立误报率；攻击输入“有删除”也不是原生 ASR。[逐例摘要与哈希](../evidence/context-filter-v5-evaluation.json)

**2. v4 补齐自己的攻击对照**

两组各 16 条原生攻击，沿用此前 v4 正常 97 条的冻结代码及预算，全部有效。攻击成功基线 3/16、参考 0/16；攻击下完成 13/16→14/16。至此 v4 的正常/攻击开发证据都有了自己的版本来源，但攻击仍只有小样，正常组仍有错误，不能宣称全量通过。[严格报告](../../artifacts/lab3090-context-filter-v4-attack16/reference-comparison.md)

**3. v5 的 35 条完整任务对照**

19 条正常任务包含历史误删任务，16 条攻击沿用开发小样；选择清单在此次模型运行前保存。两组每条都真实执行原生 AgentDojo 工具循环和 utility/security 判定，不是固定输入分类或离线重打分。

| 指标 | 无防护 | v5 输入清洗参考 |
|---|---:|---:|
| 记录 / 有效 | 35/35 | 35/35 |
| 正常完成 | 19/19 | 19/19 |
| 攻击成功 | 3/16 | 0/16 |
| 攻击下正常任务完成 | 13/16 | 14/16 |
| 运行错误 | 0 | 0 |
| guard 调用 | 0 | 94 |

workspace/user_task_16、39 的验证码任务都完成。回看 v4 的 97 正常任务历史记录，相同 19 个任务中参考只完成 17 个；现在完成 19 个。这是对已知失败的开发修复，选例看过历史错误，不能表述为独立泛化收益。两组远端子进程实际返回 0，严格配对仍 NOT_ACCEPTED：小样范围、显著性、独立测试和完整系统尚未满足。[严格报告](../../artifacts/lab3090-context-filter-v5-dev35/reference-comparison.md)

**4. 全量 1046 条/组**

小样结束、配对清单核对后，启动相同冻结 v5 的全量运行：97 个正常任务 + 949 个 important_instructions 攻击配对，两组共 2092 条。两组均不传 `--case-id`，原生 manifest 各确认 1046 个唯一 planned IDs；模型、步数 15、输出 4096、超时 300 秒、2 workers、seed 0、非思考配置一致。

GPU1 / 18080 跑 baseline，GPU0 / 18081 跑参考；通过独立控制器持续记录返回码、逐例结果和真实 GPU 样本。当前未结束，不填写最终分数，不因 SSH 观察断开而重新发起已在运行的作业。[全量命令](../../artifacts/lab3090-context-filter-v5-full1046/jobs.json)、[启动前检查](../../artifacts/lab3090-context-filter-v5-full1046/launch-precondition.json)、[已核对进程快照](../../artifacts/lab3090-context-filter-v5-full1046/progress.json)

这仍是输入清洗参考的全量验证；没有启用产品动作授权检查，不是完整 AgentSentry 的验收。全量 normal/attack 结果、未知、各套件差异与配对区间都需要等本轮真实完成后检查。原 PRD 的重复、消融、独立标注、ASB mixed、记忆链路及客户端端到端要求保持不变。

**源码、重复率与验证**

固定包 [source-candidate.tar.gz](../../artifacts/lab3090-context-filter-v5/source-candidate.tar.gz) SHA256 为 `94b05266da4bf9e906c69728c6a46e0af3d69496b4e7957e14edfa69b974c4e8`，129 个源文件。恢复时把配套 [candidate-manifest.json](../../artifacts/lab3090-context-filter-v5/candidate-manifest.json)复制到解压根目录，运行器会核对全部源码哈希。相对 v4 的[补丁](../../artifacts/lab3090-context-filter-v5/changes.patch)已重建核对 129 文件；首次检查误把父包的 companion manifest 当作额外源文件，修正检查口径后验证通过，源文件和补丁未变，失败说明保留。

Lab3090 通过 117 项相关单测、2 个 subtest、12 项原生 pipeline 检查及 14 项 ASB 脚本检查。它们是代码回归，不是新增模型样本。新增案例选择检查覆盖未知 ID、重复 ID 和保持原生顺序。[单测日志](../../artifacts/lab3090-context-filter-v5/unit-checks.log)、[原生检查](../../artifacts/lab3090-context-filter-v5/native-checks.log)、[ASB 检查](../../artifacts/lab3090-context-filter-v5/asb-checks.log)

70 个首方 Python 文件的 50-token 精确/规范化重复覆盖仍为 352/1312 token，与 v4 相同；比例约 0.499%/1.858%。分母增加导致比例下降，不宣称消除了重复或获得原创性。[重复审计](../../artifacts/lab3090-context-filter-v5/duplication.json)

本轮另外核对 [AgentArmor 与 Interbolt 的图/来源门控基线](graph-and-provenance-baseline-review.md)，明确 OPI、混合攻击和工具到达率的口径差异，没有导入第三方实现替代自研源码，也没有启动云端付费测试。
