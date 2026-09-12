# 25 SLO 与监控规范

文档 ID：AS-DOC-25 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：A+C ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

## SLI/SLO定义

这些是待实现的度量契约，当前无在线监控或SLO达标数据。SLO度量范围限定受控Agent/Proxy和明确硬件；复杂模型、人工等待、下游工具耗时分开报告。

| 指标 | 分子/分母或计时区间 | 目标/窗口 |
|---|---|---|
| 决策可用性 | 规定deadline内返回可用三态结果的探测数 / 预定探测数；策略BLOCK是正常有效结果 | 连续7天每分钟探测，≥99%；未采集不算成功 |
| Fast P95 | Proxy收到完整候选到决策可用，含队列/归一化/检测/策略/审计入队 | cpu-mvp下P95≤200ms；1/8KiB、并发1/4分别报 |
| Complex P95 | 相同区间，明确标complex，模型和排队计入 | 固定模型/硬件/长度P95≤1.5s；超时不删样本 |
| P0 Trace完整率 | 能关联候选、决策和终态的P0调用 / 独立观测P0调用 | 100%；根parent可null，缺失事件不能从分母删掉 |
| 全受控Trace覆盖 | 有完整必要标识的全部受控调用 / 独立总调用 | ≥99%，小时/日与最终报告 |
| 关键安全失败 | 未授权敏感副作用/旁路/审批重放计数 | 0；任何1次立即停止受影响入口 |
| 审计留存/脱敏 | 按TTL到期删除成功率、泄漏canary计数 | 默认7天；普通日志canary原文0 |

7天99%的等价不可用时间预算约100.8分钟，仅当探测代表实际时间段时才能这样换算；报告仍以实际采样/时长口径为准。任务安全BLOCK不能通过降低健康率迫使系统放行；全部业务都BLOCK也不能算产品成功，必须同时看良性效用和ASK率。

## 指标与标签提案

`agentsentry_decisions_total{decision,effect,mode}`、`agentsentry_decision_latency_seconds{path}`、`agentsentry_dependency_errors_total{component}`、`agentsentry_pending_approvals`、`agentsentry_audit_buffer_utilization`、`agentsentry_trace_gaps_total`、`agentsentry_budget_rejections_total`。标签取有界枚举；不把trace_id、完整URL、用户输入或秘密放进监控标签，避免高基数和泄密。

## 告警与响应

| 触发 | 级别 | 指向 |
|---|---|---|
| 非法副作用、nonce重放成功、秘密日志泄漏任一 | Critical，立即响应 | RB-08 / 事件响应 |
| 策略不可用、审计buffer满 | High，即时保护高危动作 | RB-02/RB-04 |
| 数据盘低于10GiB或项目预算超限 | Warning；暂停新重型下载/实验 | RB-04 |
| 快路径P95连续三个5分钟窗口>200ms；复杂>1.5s | Warning，检查模型/队列/负载 | RB-01 |
| Trace完整率低于相应目标、ASK异常积压 | Warning；同时报独立分母/TTL | RB-03/RB-06 |

监控自身失联记UNKNOWN并告警，不补零；故障注入窗口独立标注，不能静默从可用性结果抹去。业务吞吐与并发上限在W4性能基线后冻结，当前不编造QPS目标。每个告警用合成信号验证能到达指定值守渠道后才标已上线。
