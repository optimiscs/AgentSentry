# ASB 本地模型配对小样

状态：`ASB_PILOT_FINISHED_REVIEW_REQUIRED`。更新：2026-09-12T17:22:18.911771+00:00

固定asb-local-v1；四种混合攻击各10例，每组40例，基线/完整防护共80例。
等待vLLM调优进程结束，并核验原服务恢复后开始。小样用于判断适配可行性，不是1600场景全量验收。

| 配置 | 状态 | 记录 / 计划 | 有效 |
|---|---|---:|---:|
| baseline | RECORDED_NOT_ACCEPTED | 40/40 | 25 |
| full | RECORDED_NOT_ACCEPTED | 40/40 | 25 |

原生文本代理分数、模拟分派结果和错误分别保留；ASK不自动批准。
版本、命令与模型状态见[机器进度](../evidence/asb-pilot-progress.json)。
