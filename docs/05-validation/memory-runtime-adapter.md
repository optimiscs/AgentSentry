# 记忆评测接入实际存储

2026-09-13。状态：**PRODUCT_MEMORY_STORAGE_TESTS_NOT_AGENT_BENCHMARK**。新增适配器已经调用实际产品 Runtime、策略和加密 SQLite 存储；验证使用固定测试样本，尚未运行 MPBench Agent 或语义裁判，没有新的 ASR、RSR 或任务效用分数。

## 实现与两种配置

[memory_runtime.py](../../benchmarks/memory_runtime.py)为每个案例创建全新的目录、数据库和用户会话。模型可接入的调用面只有 `memory.write` 与 `memory.read`。写入阶段会登记外部来源；切换到后续会话时关闭并重建 Runtime，核对记忆条目持久化一致，清空原外部输入并创建无上下文的新会话。

适配器的私有评测快照包括活跃及隔离记忆；它不作为模型输入。`recall_active` 采用明确的“读取全部活跃记忆”配置，每次读取仍经过产品接口，隔离条目不进入模型观察。它不是原生 Agent 的向量检索器，也没有实现语义裁判或 C1–C4 全部写入通道。

| 配置 | 实际行为 | 适用边界 |
|---|---|---|
| runtime_rules | 当前产品扫描、意图解析和策略均运行；ASK 不自动批准 | 检查现有产品行为，尚未接入研究候选的任务规划与清洗组合 |
| memory_gate_disabled | 只关闭两个记忆工具的策略门控 | 保留参数、归属、加密存储和输出脱敏；是消融对照，不能称为完全无防护的原生 Agent 基线 |

门控关闭实现仅在新建的评测适配器中使用，没有安装到产品 API。现有策略文件不改变，其他文件、执行、联网或委派工具不在该适配器调用面中。这是受信评测程序的工具限制，不代表外部客户端已经获得操作系统级强制隔离。

## 实际验证结果

| 检查 | 实际观察 |
|---|---|
| 普通合法记忆写入 | 当前产品返回 ASK，数据库没有活跃记忆；重建后待批审批过期，仍未写入 |
| 固定注入写入 | 产品返回 BLOCK，条目标记 quarantined；重建后仍隔离，按 ID 读取也被拒绝 |
| 已批准的正常记忆 | 关闭、重建 Runtime 后内容及来源引用保持一致；新会话从空上下文开始 |
| 独立进程读取 | 另一个 Python 进程打开已提交数据库，经产品读取接口返回同一内容哈希 |
| 来源与秘密标签 | 跨会话保留 MEMORY 类型、原来源引用及 SECRET 标签；秘密原文留在加密存储，模型读取结果脱敏 |
| 隔离及幂等 | 不同案例数据库、不同用户之间不能交叉读取；相同写入请求重试不会增加条目 |
| 门控关闭时的边界 | 无效参数仍拒绝，未暴露其他产品工具；没有修改产品默认策略 |

已批准写入属于**显式操作员批准的存储测试**，不计作 Agent 自动完成正常任务。当前意图解析器没有自动授予 MEMORY_WRITE 的路径，因此普通合法写入的 ASK 仍是效用缺口；不能用全部拒绝写入来宣称 benchmark 达标。

Lab3090 最终 **103 项检查全部通过**：17 项记忆适配器检查、9 项模型传输检查、31 项网关检查、46 项组件检查。[逐项测试结果](../../artifacts/lab3090-memory-runtime-v1/test-results.json)、[最终日志](../../artifacts/lab3090-memory-runtime-v1/unit-checks-final-profile.log)

首轮 4 项失败来自门控关闭对照的 Decision 缺少 `matched_policies`，产品按策略错误拒绝执行；补齐字段后原 99 项通过。新增秘密标签检查时发现测试错误地期待读取接口返回秘密原文，而产品本来就会脱敏。随后保留脱敏行为、修正断言，并将配置明确命名为 memory_gate_disabled；最终 103 项通过。初始失败源码与日志均保留，未通过修改产品防护来让测试过关。[各次命令与退出码](../../artifacts/lab3090-memory-runtime-v1/execution.json)

## 默认模式与代码复用

主树 [local_model.py](../../benchmarks/local_model.py)和其传输测试从已冻结的组合候选原样导入，复用结构化输出、请求超时校验与显式 `enable_thinking=false` 默认值。任务与防护思考开关分别处理；相关 HTTP 请求在测试中模拟，没有调用模型服务。[导入哈希](../../artifacts/lab3090-memory-runtime-v1/import-provenance.json)

本轮没有复制一套记忆存储或策略引擎。首方 src、benchmarks、scripts 的 71 个 Python 文件共 69,105 token；50-token 精确/规范化重复覆盖仍为 **796/1845**，与父版本相同，比例约 1.152%/2.670%。比例降低来自分母增加，不代表清除了旧重复或获得跨项目原创性证明。[最终重复审计](../../artifacts/lab3090-memory-runtime-v1/duplication-final.json)

## 复现与下一步

40 个源码、策略和测试文件已封存，[源码包](../../artifacts/lab3090-memory-runtime-v1/source-snapshot.tar.gz)及 [文件哈希](../../artifacts/lab3090-memory-runtime-v1/source-manifest.json)核对通过。使用记录的 Python 3.11.14 和包版本，在新的目录中恢复并执行 [原检查命令](../../artifacts/lab3090-memory-runtime-v1/execution.json)。测试创建独立临时状态，上传产物不包含状态数据库、私钥或运行令牌。[运行环境](../../artifacts/lab3090-memory-runtime-v1/environment.json)、[批次清单](../../artifacts/lab3090-memory-runtime-v1/artifact-manifest.json)

下一步把 [MPBench 分阶段输入](mpbench-lifecycle-preparation.md)、原生 Agent、写入和后续行为证据及语义裁判连接起来，校验人工一致性，分别报告合法记忆保留与错误写入。本适配器不替代原生 C1–C4、真实客户端、完整基准、独立标注、消融、重复和性能门槛。

22:59 北京时间实查原 full1046：baseline 469/1046、输入参考 395/1046，已记录项均有效、零错误；两个原有子进程身份匹配且存活，v5/组合候选的 129/132 文件哈希不变，思考均关闭。[实际进程快照](../../artifacts/lab3090-memory-runtime-v1/parent-progress.json) 两组结束并核对终态后，仍按既定顺序运行组合候选配对。
