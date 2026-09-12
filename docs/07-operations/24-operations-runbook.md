# 24 运维手册

文档 ID：AS-DOC-24 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：A+C ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

## 运维前提

当前业务尚未部署，监控指标和告警是待实现契约。故障处理首先保护执行边界，然后恢复服务；不要关闭硬策略、扩大权限或重放结果未知的写操作。Owner A负责运行，B负责策略/审批，C负责审计和评测。

| Runbook ID / 信号 | 首次检查 | 处置 | 恢复条件 |
|---|---|---|---|
| RB-01 模型不可用/高延迟 | model版本、队列、GPU显存、最近发布 | 保留CPU硬策略；暂停新重型评测；未决高危ASK/BLOCK，不silent ALLOW | 固定负载复测恢复且降级标志清除 |
| RB-02 策略解析/服务异常 | 当前/last-known-good hash和错误 | 回滚已验证策略；没有可用策略时高危默认拒绝 | TC-12/25/26通过，版本可追溯 |
| RB-03 ASK积压/用户投诉 | 身份/权限、TTL、重复action、审批服务 | 展示未完成原因；到期不执行，不给全局批准 | 精确动作成功且nonce重放测试通过 |
| RB-04 审计失败/磁盘紧张 | 数据盘余量、buffer、SQLite可写、保留任务 | BLOCK照常；buffer满停止新的高危ALLOW；按本项目TTL处理已到期数据 | 审计可写且缺口明确，队列受控；不能删其他项目 |
| RB-05 误BLOCK/效用下降 | policy/Intent/模型最近变化、分组错误 | 回滚满足硬不变量的known-good；dev上复核良性反例 | 良性损失/ASK与安全Gate同时满足 |
| RB-06 Trace缺边/乱序 | 独立工具计数、event_id、parent和来源 | 修复幂等/顺序/关联；无法核实边标未知，不自动补造因果 | 黄金图和P0覆盖通过 |
| RB-07 下游超时/重复副作用 | action状态、执行器回执、幂等键 | 暂停重试，先查实际是否执行；unknown人工对账 | 状态明确，不出现双次执行 |
| RB-08 发现外泄/绕过 | 影响session/入口、模拟或真实sink结果 | 立即隔离受影响动作/目的，保存脱敏证据，启动事件响应 | 根因/修复/负向复测及安全负责人确认 |

## 安全诊断命令

```bash
cd /root/autodl-tmp/AgentSentry
python3 scripts/doctor.py
nvidia-smi
df -h /root/autodl-tmp
```

不要打印完整环境变量、请求头、SSH目录或凭据来排障；按trace_id查脱敏证据。当前开发服务以 bash scripts/service.sh status/start/stop 管理，详见 [Deployment Guide](23-deployment-guide.md)。重启会使未消费审批失效；unknown 结果需要核对执行账本与真实文件，不能自动重试。

## 值守和维护

W7起每个工作日检查磁盘/留存、当前版本、模型队列、审批积压、错误与Trace覆盖；发布前检查备份恢复。处置记录时间、操作者、动作、影响、恢复证据及关联DL/INC。三人团队只提供赛事计划内值守，不承诺企业24×7服务。
