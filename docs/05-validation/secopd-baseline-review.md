# SecOPD 强基线与复现条件

核对日期：2026-09-13。状态：**源码已核对，未训练、未运行作者模型，不是本项目成绩。**

SecOPD 让学生模型在受攻击输入上生成回答，再由只看到对应干净输入的教师逐 token 打分，训练学生偏向干净任务的回答。它改变模型权重，与本项目在推理时过滤输入、限制动作的路线不同。[论文 v1](https://arxiv.org/html/2608.21500v1)

作者表 1/2 使用 Qwen3.6-27B：

| 配置 | AgentDojo ASR↓ | 正常任务效用↑ | SEP / PISmith pass@10 ASR↓ |
|---|---:|---:|---:|
| 无防护 | 26.7% | 92.8% | 97.9% |
| Meta-SecAlign | 5.5% | 92.8% | 94.0% |
| GRPO | 0.7% | 82.5% | 61.2% |
| SecOPD | 4.7% | 90.7% | 9.0% |

SecOPD 在这组自适应攻击比较中最强，但 AgentDojo 最低 ASR 属于 GRPO，后者效用损失较大。SecOPD 在 Slack 子集的 ASR 仍为 24.8%。因此必须同时报告效用、攻击强度和各领域结果。[论文表 1、2、6](https://arxiv.org/html/2608.21500v1)

其 AgentDojo 条件是 v1.2.1、949 配对、important_instructions 攻击，加 repeat_user_prompt、input 角色分隔和 thinking。SecOPD/GRPO 上下文上限 32768，而另两组为 16384。本项目目前为 v1.2.2、Qwen3.5-9B、默认主任务提示及不同推理设置；不能直接用论文分数计算本项目距 SOTA 的百分点差。[附录 H](https://arxiv.org/html/2608.21500v1)

## 已审阅的代码与本地资源判断

作者仓库固定为 `571502a2a315c4b8820dd878d4569e2a2222cb88`。已核对[全响应 KL 实现](https://github.com/pppyb/SecOPD/blob/571502a2a315c4b8820dd878d4569e2a2222cb88/training/tinker/overrides/tinker_cookbook/recipes/distillation/pi_defense_full_response_kl.py)：教师给学生实际生成的全部响应 token 评分，包括推理文本；没有按 `</think>` 截取训练范围。没有将作者训练代码复制进产品源码。

[固定训练配置](https://github.com/pppyb/SecOPD/blob/571502a2a315c4b8820dd878d4569e2a2222cb88/training/tinker/configs/qwen36_full_kl.paper.json)为学生/教师 Qwen3.6-27B、LoRA rank 128、学习率 1e-4、输出上限 16384、temperature 1、150 步。官方入口依赖 Tinker；模型导出还有专门的权重映射要求，不能按普通 PEFT 合并流程假定成功。[复现说明](https://github.com/pppyb/SecOPD/blob/571502a2a315c4b8820dd878d4569e2a2222cb88/docs/REPRODUCIBILITY.md)

资源推算：27B 参数仅 BF16 权重约 50 GiB，已经超过双 3090 合计 48 GiB，尚未计缓存或训练状态。原配置不能直接照搬；改为 9B、量化或卸载均需另立实验并重新测效果。此次没有启动云训练、下载 27B 权重或改变现有 Qwen3.5-9B 服务。

对当前优化的约束：先解决已观察到的正常内容误删与推理开销；训练路线保留为独立强基线。后续若移植到 9B，训练材料必须与 benchmark 验收集分离，并与同一初始权重、相同提示和预算的无训练模型比较。论文的训练贡献不作为本项目原创贡献。
