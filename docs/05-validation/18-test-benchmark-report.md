# 18 测试与 Benchmark 报告

文档 ID：AS-DOC-18 ｜ 版本：1.1-dev ｜ 更新：2026-09-12  
Owner：C ｜ 状态：`active_record` ｜ 独立复核：尚未完成

[返回文档导航](../README.md)

## 已运行结果

Python 自动化测试：160 通过、0 失败、0 跳过；pytest 退出码 0。语句覆盖率 80.86%，分支覆盖率 69.05%。覆盖率只描述该测试运行，不替代安全正确性或发布签收。

[逐测试证据](../evidence/runtime-tests.json) · [覆盖率汇总](../evidence/coverage-summary.json) · [源码文件指纹](../evidence/source-manifest.json) · [运行摘要](../evidence/runtime-report.json)

包含三态实际副作用、审批并发/过期/取消/资源替换/版本漂移、未知结果不重试、SECRET 可信域外发、Memory 隔离、父子权限交集、MCP 真实 stdio 与 HTTP JSON-RPC、元数据漂移、沙箱宿主读/联网/fork 阻断、Git 对象变化、API 身份/Origin/验证错误脱敏、冷备份与恢复；原生 Hook 的只决策/审批/单次 claim/客户端回报、真实 HTTP 与进程桥接。

两个提醒来自 FastAPI/Starlette 测试客户端的上游弃用接口，未被隐藏为测试失败。默认神经模型关闭；没有推断或填充模型效果指标。

## 黄金功能回归

[20 条逐案例记录](../evidence/golden-report.json)：20/20 通过。样例参与开发，AL​LOW/ASK/BLOCK 与独立执行账本核对；不将该结果报告为独立 test 的 F1/ASR。

## CPU 本地网关性能

[性能原始报告](../evidence/perf-cpu.json)；4 CPU affinity、8 GiB 虚拟地址空间上限、禁用 GPU，ASCII 1/8 KiB，含扫描/归一化/决策/审计/文件工具及有界并发锁等待，不含 HTTP、模型、上游 Agent 或人工等待。共享主机资源不是独占容器验收。

| 输入 | 并发 | 正式样本 | P95 ms | 错误 | 本配置阈值 |
|---|---|---|---|---|---|
| 1024 B | 1 | 1000 | 10.54 | 0 | PASS |
| 1024 B | 4 | 1000 | 77.64 | 0 | PASS |
| 8192 B | 1 | 1000 | 17.30 | 0 | PASS |
| 8192 B | 4 | 1000 | 172.84 | 0 | PASS |

每档另有 200 次预热。[首轮未达标记录](../evidence/perf-cpu-before.json)保留，优化使用事件序号索引、上下文头部查询和等价 ASCII 规范化快速路径。

## 尚未完成的验收

- AgentDojo / InjecAgent 的全配置达标验收；ASB / MSB / Memory、AI-Infra-Guard 全量回归和四项消融。
- 独立分组标注 test 的检测 Macro-F1、三态 Macro-F1、良性效用与 ASR；当前只有指标计算器合同测试。
- 可选本地神经模型权重的正确性/性能、复杂语义路径 P95。
- 外部宿主 Agent 的独立强制隔离、干净 Docker/离线安装验证、七天稳定性及独立安全评审。

总判定：开发版可运行；正式发布验收未通过。未运行项目记 NOT_RUN，不记 0 或 PASS。完整设计主题覆盖及当前缺口见 [test-cases.json](test-cases.json)；生产可用性/效果目标仍按原 PRD 保留。

## 运行服务与界面验收补充

[真实 MCP 双传输证据](../evidence/live-mcp.json)与 [浏览器验收记录](../evidence/ui-verification.json)单列于 pytest 之外，以各自记录时间为准。服务在 5090 的 127.0.0.1:8080 运行，通过 SSH 隧道访问；界面已检查审批前完整参数、批准/拒绝、来源图与实测报告。

## 公开基准实际运行

[公开 Benchmark 实测与验收](public-benchmark-report.md)单独记录真实模型结果与未通过项；不得把本页工程回归通过率当作研究效果验收。
