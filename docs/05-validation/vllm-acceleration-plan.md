# vLLM 服务加速与验证计划

更新：2026-09-12。当前已使用 **vLLM 0.27.1 + 单卡5090 + 27B NVFP4**，localhost:18080提供模型接口。当前没有可报告的调优加速倍数。

已核对的活动参数为32K上下文、最多2条并行序列、每批2048 token、显存预算92%、`--enforce-eager`，前缀缓存未启用。最近一段服务日志的总生成吞吐约30.6–32.6 token/s，这是滚动观测，不能代替受控性能实验。一次显存快照为30288/32607 MiB，不能据此直接增加显存预算。

`--enforce-eager`跳过编译和CUDA Graph，缩短启动但可能降低稳定运行时的性能，见[vLLM官方调优说明](https://docs.vllm.ai/en/latest/configuration/optimization/)。[前缀缓存](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/)复用重复提示的预填充计算，不直接加速后续逐token解码。当前混合结构模型在已安装vLLM源码中默认不启用前缀缓存，必须显式测试兼容性。

| 试验 | 编译/CUDA Graph | 前缀缓存 | 并行序列上限 | 每批token上限 |
|---|---|---|---:|---:|
| eager-s2 | 关闭 | 关闭 | 2 | 2048 |
| graph-s2 | 启用默认优化 | 关闭 | 2 | 2048 |
| graph-apc-s2 | 启用默认优化 | 开启 | 2 | 2048 |
| graph-apc-s4 | 启用默认优化 | 开启 | 4 | 4096 |

四组使用同一权重、量化、上下文上限、解析器和本地接口。先等待当前v4四作业配对及task-plan-v1的16例小样结束，并核验完成记录、进程启动时间、服务器命令和空闲指标。已有评测不能中途改变服务参数。

执行器首先检查短回答、JSON值、强制工具调用的完整参数，以及共享前缀但不同后缀的两条回答；失败保留原始响应并停止该配置的性能测量。然后运行已安装vLLM官方bench命令：每组16条随机请求，1024输入/256输出token，固定输出长度，客户端并发2和4，各做首次工作负载及相同请求重放。两档并发分别用seed0/1，各配置相同；初始正确性检查用于预热，不宣称缓存绝对为空。

记录吞吐、TTFT、TPOT、端到端P95、错误、运行期峰值显存和启动耗时。16条请求仅适合初筛，P95不能作为生产SLO证据；需再使用真实Agent工作负载验证。脚本离线失败路径检查11项通过，包括PID复用、错误进程组、依赖未完成、服务器繁忙、启动/输出/性能失败，以及恢复失败的显式状态。以上测试没有调用模型或停止活动服务。

调优任务结束或失败后尝试恢复原配置，保留新进程身份和状态；不自动把最快小样配置用于正式验收。任何最终配置变更均需建立新的完整质量配对清单。它可以缩短推理与评测时间，但不能直接修复当前25.77pp的正常效用损失。

当前执行状态见[实时报告](vllm-tuning-report.md)，完整配置见[机器计划](../evidence/vllm-current-and-tuning-plan.json)。执行器位于工程 `artifacts/run_vllm_tuning_after_benchmarks.py`，所有性能工件保存到 `artifacts/vllm-tuning-v1`。

## 2026-09-13修复与交接

首轮四配置各5项正确性检查通过，但性能命令的random-range-ratio=1.0允许零长度输入，均在发送前失败。原服务已恢复。按[官方CLI语义](https://docs.vllm.ai/en/stable/cli/bench/serve/)，新v2改为0.0固定长度；10项脚本检查及实际tokenizer采样通过，启动后已取得eager并发2首次/重放约30.51/30.55输出token/s。新代码为scripts/run_vllm_tuning_v2.py，工件目录artifacts/vllm-tuning-v2。尚无完整配置配对或加速倍数结论。用户随后要求上传并暂停，SSH拒绝连接时暂停未确认，详见[交接记录](../04-development/experiment-pause-and-handoff.md)。
