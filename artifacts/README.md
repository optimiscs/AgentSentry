# 精选中间产物

本目录只提交[repository-manifest.json](repository-manifest.json)列出的精选文件；原有`.gitignore`继续忽略其他运行产物。清单包含每个文件的SHA-256和大小。

- `benchmarks/*/*/{manifest,metrics}.json`：本地已回收的场景清单、配置、统计和状态。包含历史及小样，须按各自scope解读。
- `benchmarks/frozen-*/source.tar.gz`及environment.json：相应运行使用的第一方源码和环境记录。
- `development/*/source-candidate.tar.gz`、候选清单和补丁：隔离研究版本的源码。`asb-protocol-v2`只通过部分工程检查，没有新模型结果。
- vLLM运行计划、固定执行器、采样预检和PID身份：记录如何运行与核验进程；PID文件是历史证据，不能直接据其对当前进程发送信号。
- PIGuard评分报告、原评分源码与协议回归：保留分窗诊断及其评分口径；完整上下文新运行没有可提交的最终分数。
- 重复审计与task-plan小样验收报告：记录可复现工程统计及失败结论。

这些文件不包含模型权重、第三方完整数据集、虚拟环境、运行数据库、私钥/访问令牌和完整会话逐例原文。最新远端部分原始结果因SSH不可达尚未回收。指标和清单不能替代完整逐例记录，当前benchmark仍未验收。

需要查看某个候选全部源码时，先核对清单中的归档哈希，再解压到新的空目录；不要覆盖已有开发目录。例如：

```bash
mkdir -p /tmp/agentsentry-task-plan-review
tar -xzf artifacts/development/task-plan-v1/source-candidate.tar.gz \
  -C /tmp/agentsentry-task-plan-review
```

这不会启动服务或实验。服务器专用路径和已冻结的模型配置需要在相应环境中复现，不能把它们当成任意机器通用的启动命令。暂停请求的确认状态见[交接记录](../docs/04-development/experiment-pause-and-handoff.md)。
