AgentDojo 评测环境与两个 Qwen3.5-9B 推理服务分开管理。

- 推理环境：`/home/moxu/miniconda3/envs/agentsentry-lab3090`。
- 评测环境：`/home/moxu/miniconda3/envs/agentsentry-bench-lab3090`，Python 3.11.14。
- [评测包锁定文件](benchmark-lock.txt)来自实际安装结果；AgentDojo 固定源码提交为 `089ed468cf3ed0322acc66b0211f26d9d90dbf60`，包版本 0.1.35。

新机器可先建立 Python 3.11 环境，再安装锁定依赖及已经核验的源码：

```bash
conda create -n agentsentry-bench-lab3090 python=3.11 pip
conda run -n agentsentry-bench-lab3090 python -m pip install -r deploy/lab3090/benchmark-lock.txt
conda run -n agentsentry-bench-lab3090 python -m pip install --no-deps -e artifacts/upstream/agentdojo-089ed468cf3e -e .
conda run -n agentsentry-bench-lab3090 python -m pip check
```

以上假设工程和固定上游源码已经就位。研究候选运行时必须按对应 `jobs.json` 设置候选的 `PYTHONPATH`；不能用主线包冒充候选。模型只通过本机 HTTP 端口调用，不在此环境安装模型权重或 vLLM。

本次在模型环境中进行的依赖解析只是 dry-run，因 `websockets==17.1` 与 AgentDojo 依赖冲突而终止。随后以本机缓存的 Conda 基础包新建独立评测环境，不复制 pip 包软链接。推理环境安装前后包列表完全一致。

实际 Conda 包清单、安装报告、`pip check`、两份环境包列表及 97 个原生正常任务/工具目录预检记录，保留在 `artifacts/lab3090-agentdojo-v1`。这套环境的检查结果不等于模型任务或安全验收通过。
