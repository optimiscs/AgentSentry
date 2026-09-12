# 03 可行性调研 / Tech Spike

文档 ID：AS-DOC-03 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：A+B ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

## 可行性结论与已验证事实

从任务拆分和模型规模判断，单卡5090可以支撑本项目MVP开发及7B/8B主Agent的分批评测；这不是实际推理吞吐或算法达标证明。此次SSH已核验RTX5090、32607MiB显存、25 CPU配额、90GiB内存限制。GPU检查时仅使用2MiB，驱动595.71.05。数据盘余量约91GiB，系统盘约1.95GiB。

证据为[环境快照](../evidence/environment-current.json)。早期0.5CPU/2GiB/无GPU状态已变化，旧快照仅作历史。默认Python3.10.12、Node12.22.9；Docker与uv未在PATH发现。以上是初次只读快照；后续已完成独立核心/评测依赖安装、MCP/审批/图回归与 Qwen7B 本地模型加载，容器镜像仍未验收。

## Spike清单

| ID | 问题/实验 | 时间盒 | 通过标准 | 当前结论/失败后方案 |
|---|---|---|---|---|
| SP-01 | SSH/cgroup/GPU/磁盘只读探测 | 0.5日/A | 身份、配额、显卡与工作盘可辨识 | 已执行；资源可用于开发，资源状态需复测 |
| SP-02 | 独立Python3.11、MCP SDK stdio/HTTP最小调用 | 1日/A | initialize/tools/list/tools/call与取消正确；stdout无调试污染 | 已验证 stdio/HTTP 实际调用，详见 live-mcp 证据；完整产品取消/旁路另验 |
| SP-03 | Proxy暂停调用后BLOCK | 1日/A+B | 实际工具执行计数为0，旁路无凭据/网络能力 | 已验证网关 BLOCK 零转发和受限 Python 隔离；外部宿主旁路未验收 |
| SP-04 | 一个7B/8B Agent的短/中上下文工具使用 | 1日/A | 无OOM、有正常任务完成记录、记录tokens/s与峰值显存 | Qwen2.5-7B / vLLM0.27.1 已实际推理；初次8K/1024预算出现超限/截断，ASR/效用未达标 |
| SP-05 | 小分类器CPU注入扫描 | 1日/A | 输出字段可追溯，报告1/8KiB输入P95与中文误判 | 未执行；比较规则+更小模型，不预先承诺200ms |
| SP-06 | Intent与动作合同 | 1日/B | 三模板正反样例，UNKNOWN不扩权，可信任务之外不能授权 | 模板/静态上限及负向约束已回归；跨领域良性任务过度 ASK，待增强 |
| SP-07 | 审批一次性消费与变参 | 1日/B | 并发同nonce仅一次执行，版本变化失效 | 网关与原生 Hook 单次消费/并发/变参已测试；真实产品客户端仍待验收 |
| SP-08 | 黄金图与审计泄密 | 1日/C | 源/必要边/sink可核对，导出无canary原文 | 20 条开发黄金回归通过；隐蔽独立 test 与推断关联仍待验收 |
| SP-09 | 基准许可/版本/smoke | 2日/C | AgentDojo/InjecAgent/ASB原生输出；确认MSB/MPBench来源 | AgentDojo/InjecAgent 已取源并运行；ASB 已取源未运行，MSB/Memory 未完成 |
| SP-10 | Docker daemon/Compose可用性 | 0.5日/A | 干净主机可启动最小镜像 | 未执行；当前只有未发现CLI的证据，需可用验收主机 |

SP-02至SP-10计入已有工作包和缓冲，不作为额外人日重复叠加。各Spike记录假设、版本/命令、原始输出、耗时、成功/失败、后续ADR。只有复现成功后才能把“可行”升级为“已验证”。

## 显存与计算安排

主Agent先采用7B/8B量级，B复用模型服务或更小的Intent模型；检测器优先CPU；公开基准排队，性能验收独占资源。8B BF16仅权重理想估算约16GB，实际还需KV cache和框架开销；不能承诺任意上下文/并发可容纳。模型权重获取、量化、许可证及Blackwell兼容推理栈都需SP-04实测。

CPU-only P0验收单独限制为4vCPU/8GiB并禁用GPU与外部模型API。当前大容器的成功不自动证明CPU最小配置达标。Compose的能力也不能由普通Python进程启动成功推导。

## 本地模型与公开评测实测补充

使用服务器已有 Qwen2.5-7B-Instruct 四个 BF16 权重分片，模型解释器位于独立现有 vLLM 环境；不修改该共享环境依赖。FlashInfer sampler 初次报 CUDA 工具链兼容错误，改用 Torch sampler 后启动成功。模型只监听 localhost:18080，安全网关仍为 CPU localhost:8080；ASB 原生 mixed 的云嵌入/拒绝判定路径未直接运行。具体模型/依赖/源码哈希在 artifacts/benchmarks/frozen-qwen7b-v1，指标以 [公开报告](../05-validation/public-benchmark-report.md) 为准。

## 2026-09-12 · 更强本地模型探测

服务器既有 Inferact 命名空间的27B NVFP4权重已在单卡5090运行，配置架构为Qwen3_5ForConditionalGeneration。使用既有vLLM0.27.1、CUTLASS线性内核、语言模型模式，关闭thinking，未改变共享依赖。权重加载占23.31GiB；8K纯文本与原生工具调用两项探测通过，32K服务也已启动。精确路径、7个safetensors哈希、启动命令及源码冻结于artifacts/benchmarks/frozen-qwen27b-v4，不将该目录名当作官方模型身份或SOTA证明。

12条InjecAgent小样在基线/防护均为12条有效、ASR为0。相对下降在零基线时未定义，不能据此认为防护已达到相对改善门槛。需继续完整配对、正常任务与攻击效果评测。
