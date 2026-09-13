# 归因防护的成本审计与强基线补查

2026-09-13。状态：**CPU_TOKENIZER_AUDIT_ONLY**。本轮没有调用推理服务、加载模型权重或执行动作，没有新的 ASR、归因分数或延迟成绩。任务模型与防护模型默认关闭思考。

## 论文中实际可比的内容

CausalArmor 在高权限决策前比较原任务与工具返回内容的逐项移除影响，再定向清洗。其归一化判据为 `ΔS/|Y| > ΔU/|Y| − τ`。论文的批处理减少顺序调用，整体计算及峰值内存仍随片段数增长。它采用代理模型和清洗模型，我们的 Qwen 配置属于改编候选。[原论文 §3–4、附录 D](https://arxiv.org/html/2602.07918v1)

下面只摘取同一论文、Claude-4-Sonnet、AgentDojo v1.2.2 的 Important Instructions 列。BU 是正常任务效用，UA 是攻击下任务效用；延迟列为相对无防护的倍数。[原论文表 3](https://arxiv.org/html/2602.07918v1)

| 方法 | BU | 正常延迟 | UA | 攻击延迟 | ASR |
|---|---:|---:|---:|---:|---:|
| 无防护 | 89.44% | 1.00× | 83.98% | 1.00× | 2.32% |
| PromptArmor | 74.23% | 2.20× | 74.08% | 2.44× | 0% |
| CausalArmor | 82.47% | 1.27× | 83.67% | 1.54× | 0% |

由表中数据计算，CausalArmor 的正常效用损失为 **6.97 个百分点**，超过本项目 5 个百分点门槛。它值得作为强对照，但不能据此承诺解决我们的效用问题；这些论文数字也不是 Qwen3.5-9B 的实测结果。本次未核实作者官方实现地址，未将第三方同名仓库当作作者实现或导入代码。

MemSecBench 提供另一个协议参考：310 条关联案例、48 个上下文，分别检查写入持久化、后续召回及影响、外部后果与选择性修复；修复需保留正常记忆。本项目可借鉴这些证据边界，避免把输入分类或写入成功算成完整记忆攻击成功。它不替代既定 MPBench/Memory 验收，也不是其防护 SOTA 排行。[MemSecBench 原论文](https://arxiv.org/html/2607.27080v1)

## 本地真实轨迹的成本

输入是已完成的 v5 开发集 baseline：19 条正常任务、16 条攻击，共 35 条全部有效。使用冻结 v5 源码、固定 AgentDojo 与 Qwen tokenizer，逐条还原实际对话模板；**114 次 actor 请求的 prompt token 数均与原 vLLM usage 一致**。对每个带有先前工具观察的非只读工具决策，保留已发生的同一 assistant 输出，构建完整上下文、清空原用户正文、分别清空各工具正文的评分输入。角色及工具关联结构保留；这是显式适配，不宣称与作者删除实现完全相同。

| CPU 审计项 | 真实结果 |
|---|---:|
| 有效轨迹 / 总轨迹 | 35 / 35 |
| 已核对的 actor 请求 | 114 |
| 符合条件的决策点 | 26，分布于 20 条轨迹 |
| 评分上下文数 | 137 |
| 所有评分上下文 token 总数 | 430,799 |
| 同样 26 个决策仅评分完整上下文的 token 总数 | 92,348 |
| 相对上述单次评分的 token 倍数 | 4.665× |
| 最长评分上下文 | 12,941 token |
| 超过 32,768 上限 | 0 |
| 单个决策最多上下文数 | 11 |

每组移除变体的目标 token 后缀完全一致。4.665× 比较的是额外评分输入量，**不是原 agent 总成本、运行时间或 FLOPs 倍数**。CPU tokenizer 耗时 2.13 秒不包含推理，不能签收 1.5 秒复杂路径要求。按每两份输入静态分组会得到 77 组，这只是算术计数，不能当作 vLLM 实际调度次数。[逐决策 token 与哈希](../../artifacts/lab3090-causal-budget-v1/budget.json)

15 条轨迹没有上述检查点；这不等于它们没有攻击或全部只读。事后关联原结果，3 条已成功的 baseline 攻击均存在检查点，但“有地方检查”不等于“能识别攻击”。当前审计没有计算概率，也没有验证纯回答污染、多片段分散攻击或新动作重生成。

## 实现、检查与复现

新增 [audit_causal_proxy_budget.py](../../scripts/audit_causal_proxy_budget.py)，复用上游消息转换、工具定义及本项目只读工具目录。它拒绝源码/清单不符、案例缺失、模板长度不符及移除后目标变化；不向渲染过程传入裁判目标或标签。[8 项检查](../../tests/test_causal_proxy_budget.py)在 Lab3090 通过，真实轨迹运行返回码 0。

首次尝试因 benchmark 环境没有 Transformers 而退出，错误日志保留。随后使用既有模型环境的 tokenizer，追加既有 benchmark 环境作为缺失依赖的只读查找路径；未安装依赖、修改环境或启动模型。模块版本、来源与哈希见 [runtime-provenance.json](../../artifacts/lab3090-causal-budget-v1/runtime-provenance.json)，实际命令与退出码见 [execution.json](../../artifacts/lab3090-causal-budget-v1/execution.json)。

仅读取活动 vLLM 的 OpenAPI schema，发现 `/v1/completions` 暴露 token ID 输入、`echo`、`prompt_logprobs` 等字段。这仅是接口检查，尚未验证真实请求能否正确返回目标 token 的概率；没有发送评分请求。[接口证据](../../artifacts/lab3090-causal-budget-v1/serving-scoring-schema.json)

首方 Python 审计范围为主树 src、benchmarks、scripts；tests、上游及生成文件按既定口径排除。与提交 `0bb37c9` 的 68 文件相比，现有 69 文件、66,496 token；50-token 精确/规范化重复覆盖均保持 **692/1747**，当前比例 1.041%/2.627%。比例下降来自新增分母，没有消除旧重复，也不是跨项目查重率或原创性证明。该口径与组合候选的文件集合不同，不能混用。[重复审计](../../artifacts/lab3090-causal-budget-v1/duplication.json)

原始 35 条模拟基准输入、模型输出及许可保存在 [input-traces.tar.gz](../../artifacts/lab3090-causal-budget-v1/input-traces.tar.gz)，逐文件哈希与旧运行一致，见 [input-provenance.json](../../artifacts/lab3090-causal-budget-v1/input-provenance.json)。复现还需恢复既有 [v5 冻结源码与固定模型环境](context-filter-v5-review.md)；本轮未改写它们或已冻结的 [组合候选](composed-guard-v1-review.md)。

## 执行顺序

22:17 北京时间实查：baseline 349/1046、输入参考 287/1046，已记录项均有效、零错误；两个原有子进程身份匹配且仍运行。v5 的 129 文件和组合候选的 132 文件哈希全部保持一致，两组思考均关闭。[带时间的进程与源码快照](../../artifacts/lab3090-causal-budget-v1/parent-progress.json)

先完成正在运行的两组 full1046 并检查真实终态，再运行已准备的组合候选 35 条配对。归因方法尚未进入模型评估队列；后续在空闲服务上验证评分正确性、预算与失败处理，才决定是否建立独立冻结候选。开发样本不能用于声称隐藏集效果。完整基准、同配置强对照、效用、独立标注、消融、重复、真实客户端与固定资源性能要求继续保留。
