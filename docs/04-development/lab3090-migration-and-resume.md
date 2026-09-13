# Lab3090 迁移与实验恢复

日期：2026-09-13。用户重新授权继续实验，指定双卡 Lab3090、新 Conda 环境及 **Qwen/Qwen3.5-9B**。本轮覆盖此前暂停请求中的“不安排新实验”；5090 旧进程仍需独立核实，不能把失联当作停止。

首轮恢复后已完成 [ASB v3 优化对照](../05-validation/asb-contract-v3-review.md)：两组各40条均有效，防护组开始放行8次正常工具调用；任务完整效用仍未成立。本文“首轮恢复结果”保留 v2 历史数值。

## 环境与模型

- 主机：Lab3090 / B505-Server-09，用户 moxu，工程 `/home/moxu/AgentSentry`。
- 两张 RTX 3090，各 24576 MiB，驱动 535.183.01；两卡实际 CUDA 张量运算已通过。GPU 间拓扑 SYS，无已确认 NVLink。
- 新环境：`/home/moxu/miniconda3/envs/agentsentry-lab3090`，Python 3.11.14。最初复制来源含 15 个跨环境顶层符号链接，安装在 Triton 卸载后报错并回滚；基础环境 Triton 的 322 项记录哈希全部恢复一致，原环境两卡 CUDA 运算复查通过。失败复制保留为诊断，当前改为全新创建环境，再安装 [固定依赖](../../deploy/lab3090/requirements.txt)。系统驱动未改变。
- 用户清理后主目录可用空间实测 121 GiB；安装/下载将占用其中一部分。
- 指定主模型：Qwen/Qwen3.5-9B，原始 BF16，HF revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`。[模型锁定清单](../../deploy/lab3090/model-lock.json)保留文件大小及官方哈希。
- 服务器直连 HF 超时；小文件由本地从固定 HF revision 下载并校验后复制，四个权重从 ModelScope 官方 Qwen 仓库固定版本传输，必须与 HF LFS SHA256 一致。[下载校验程序](../../deploy/lab3090/fetch_model.py)不会执行仓库代码。
- vLLM 0.17.1 包含 Qwen3.5 原生实现，拟配套 torch 2.10.0、Transformers 4.57.6；是否在当前驱动正常运行以实际加载和生成测试为准。[官方部署说明](https://recipes.vllm.ai/Qwen/Qwen3.5-9B)。

## 数据与代码来源

从 GitHub 已上传的 main `108fcf256adcebdb114a65c023eab6bfc22ae162` 建立工程。265 个模型/数据/固定上游文件（约 843 MB）已逐文件验证大小与 SHA256，涉及 PIGuard、MPBench、ASB、InjecAgent。迁移清单及安装、下载日志位于 `artifacts/lab3090-migration-v1`。

PIGuard 完整输入执行器改为显式选择 CPU/GPU，模型路径相对工程解析；原固定模型加载器的字节和校验不变。新执行器固定 FP32、禁用 TF32、seed 0，记录主机、PID、进程启动时间和环境。评分器保留历史 CPU profile，新增独立 portable profile，并拒绝 GPU 冒充旧 CPU 结果、精度变化和部分记录。29 项输入/评分相关检查本地通过。

## 恢复顺序与判定

1. 完成依赖、权重校验及新环境双卡 CUDA 检查。
2. 进行 PIGuard CPU/GPU 数值与分类一致性小样，随后 GPU 0 完整跑 6240 条 MPBench 输入诊断。
3. GPU 1 部署指定 Qwen3.5-9B，限制上下文和并发，验证普通对话、工具调用和结构化响应。优先单卡部署；双卡通信及吞吐优化另建配置测量。
4. 以新模型、新环境、新输出目录恢复 baseline/full 配对模型实验，再检查 ASB 连续 system 修复及规划器效用瓶颈。

本次模型变化后的 ASR/效用不能与 5090 的 27B 运行合并计分，也不能把 PIGuard 输入分类诊断算成内存/工具安全验收。所有原验收缺项保持可见。旧 5090 的 CPU 对照、调优状态见[暂停交接记录](experiment-pause-and-handoff.md)。

## 已完成检查与运行状态

- 新环境 `pip check` 通过，实际版本 torch 2.10.0+cu128 / CUDA runtime 12.8 / vLLM 0.17.1 / Transformers 4.57.6；两卡 BF16 矩阵运算通过。
- 原仓库初始化依赖 `git init -b`，Lab3090 的 Git 2.25.1 不支持该选项。演示夹具改为 `git init` 后显式设置新仓库 HEAD 到 main；不修改已有仓库。工程回归 205 通过、2 跳过、7 subtests 通过；跳过项要求 root/chroot/seccomp，未降低沙箱边界来强行通过。
- 固定 ASB 候选的 11 项模拟链路检查通过；20 条历史 DPI_OPI 失败请求在新模型真实分词器中复现原错误并通过合并后渲染，未改写历史分数。
- PIGuard 的 6 条固定输入 CPU/GPU FP32 小样通过：分类完全一致，最大概率差 `2.384185791015625e-7`，事先容差 `2e-4`。GPU 0 完整诊断已完成 6240/6240，零未知，耗时 134.59 秒。原进程 PID 2337495 / start_ticks 751688272；输出 `artifacts/piguard-mpbench-lab3090-full-context-v1`。
- Qwen3.5-9B 服务 PID 2336226 / start_ticks 751680150，GPU 1 BF16，32768-token、并发上限 2、非思考模式。普通回答、JSON、指定工具与自动工具调用四项均通过。第二实例 PID 2342776 / start_ticks 751730204 使用 GPU 0、端口 18081，四项同样通过。两个实例分别运行 baseline/full，模型、精度、上下文、种子与采样配置相同；首次 JIT 开销不算稳态推理延迟。

主线首方 Python token 克隆审计：68 文件，exact 50-token 覆盖 692/64369 = 1.0751%，规范化 1747/64369 = 2.7140%；覆盖 token 数与上轮相同，比例变化来自分母增加，不作为去重改善或原创性证据。部署辅助文件和冻结候选不属于该扫描范围。


## 首轮恢复结果

ASB 每组 40 条，包含 mixed/DPI_OPI/DPI_MP/OPI_MP 各 10 条；新模型、新硬件、消息协议修复共同定义本次配置。[完整诊断证据](../evidence/lab3090-recovery.json)。

| 指标 | baseline | full |
|---|---:|---:|
| 已记录 / 有效 | 40 / 37 | 40 / 38 |
| 已判定模拟攻击成功 | 9 | 0 |
| 模拟执行 ASR（全分母） | 22.5% | 0% |
| 包含未知结果的 ASR 上界 | 30% | 5% |
| 原生文本 utility / 全部正常工具执行率 | 0% / 0% | 0% / 0% |
| 原生 workflow 失败（未知） | 3 | 2 |
| HTTP system 模板错误 | 0 | 0 |

full 的 40 个计划全部为空，26 次工具候选全部 ASK（TASK_OPERATION_NOT_PLANNED）。因此没有正常任务效用提升的证据，也不能把零已判定攻击执行视为完整成功。两组完整运行都因存在原生 workflow 无效结果返回退出码 1，记录保留，不将退出码改为通过。mixed 子集本身 baseline/full 各 1 条未知，ASR 上界各 10%；上表 5% 是四模式合并结果，不替代 mixed 原生门槛。

PIGuard 完整字段诊断：6240 条全部有效；TP983/FN2258/FP409/TN2590，TPR 30.33%、FPR 13.64%、Macro-F1 0.5422，见[评分证据](../evidence/lab3090-piguard-mpbench.json)。这是第三方检查点的输入分类诊断，尚不足以签收预期检测指标或 AgentSentry 的动作安全效果。

后续质量工作应优先解决空计划与工具契约适配，并建立有有效正常任务完成 oracle 的对照；再安排全量、重复和消融。此次 80 条 ASB 小样与 6240 条输入诊断均已结束，**整体仍为 NOT_ACCEPTED**。两卡模型服务保持可用；本轮没有额外的后台模型评测排队。

## 使用与同步

```bash
ssh -o ClearAllForwardings=yes Lab3090
source /home/moxu/miniconda3/etc/profile.d/conda.sh
conda activate agentsentry-lab3090
cd /home/moxu/AgentSentry
```

两个模型接口只监听服务器回环地址 `127.0.0.1:18080/v1` 与 `127.0.0.1:18081/v1`。启动参数见[GPU 1 实例](../../deploy/lab3090/serving.json)、[GPU 0 实例](../../deploy/lab3090/serving-replica.json)，复用[启动器](../../deploy/lab3090/start_server.py)，其拒绝覆盖已有进程记录、已占用端口或 GPU。

[Lab3090 进度页](../05-validation/lab3090-live-benchmark-progress.md)由已有进度脚本每15秒更新，本轮完成后自动退出。新增输出路径参数使本机结果与5090进度文档独立。原 `sync_server.py` / `pull_evidence.py` 默认目标仍为5090，本轮使用显式 Lab3090 的选择性 rsync；不应把旧同步命令直接当作本机入口。
