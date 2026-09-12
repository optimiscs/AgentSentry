# AgentSentry · 意链盾

面向工具型 Agent 的执行前安全网关。当前版本 `0.1.0.dev1` 已在 5090 上运行：上下文扫描 → Intent/Action 对齐 → ALLOW / ASK / BLOCK → 受限执行 → 脱敏审计与来源图。

[工程文档导航](docs/README.md) · [实际测试报告](docs/05-validation/18-test-benchmark-report.md) · [公开 Benchmark 验收](docs/05-validation/public-benchmark-report.md) · [开发记录](docs/04-development/15-implementation-record-dev-log.md) · [需求追踪](docs/01-requirements/06-requirement-traceability-matrix.md)

2026-09-13 仓库交接：已按用户要求准备代码和精选中间产物，[产物索引](artifacts/README.md)记录范围与哈希。[实验暂停交接](docs/04-development/experiment-pause-and-handoff.md)记录最后确认的进程状态；SSH 不可达时不能据此声称远端实验已停止。

## 当前能力

- 规则检测支持用户输入、Web、文档、Issue、MCP 描述/响应和 Memory；保留 Unicode 证据坐标，支持批量扫描。
- 五类动作归一化、确定性 DSL、权限上限、单次 HMAC 审批；资源、参数或策略改变使原审批失效。
- 文件工具限定仓库；Git push 仅指向隔离本地 bare 仓库；Python 运行于 chroot + UID 65534 + seccomp + 资源限额中。
- Codex/Claude Code 原生 Hook 决策/单次许可/回报与配置包生成器；已测桥接协议，真实产品客户端尚未验收。
- 真实 MCP stdio 适配与 Streamable HTTP 入口；注册工具元数据按 SHA-256 校验，描述不授予权限。
- SQLite 持久化、加密私有参数、七天留存、Memory 隔离、明确区分数据引用与上下文关联的 Trace 图。
- React 控制台提供事件、完整动作预览与审批、来源关系和报告；身份令牌仅保存在页面内存中。

## 在 5090 使用

工程目录：`/root/autodl-tmp/AgentSentry`。核心使用工程独立 `.venv`；公开评测使用 artifacts/benchmark-venv，模型复用已有权重与 vLLM 环境，不修改其他项目代码或依赖。

```bash
ssh 5090
cd /root/autodl-tmp/AgentSentry
bash scripts/service.sh status
# 需要启动时：bash scripts/service.sh start
```

本地建立访问隧道：

```bash
ssh -N -L 127.0.0.1:8080:127.0.0.1:8080 5090
```

打开 <http://127.0.0.1:8080>。登录令牌位于服务器 `runtime-data/operator.token`（权限 600）；Agent 使用单独的 `agent.token`，不能创建授权任务、批准动作或修改策略。不要把令牌提交到版本库或截图中。

## 开发与文档同步

```bash
make test         # 单元、集成、真实 MCP、安全和沙箱测试
make eval-smoke   # 20 条开发黄金功能回归，不是公开基准
make perf-cpu     # 4 档 CPU 本地网关性能，每档 200 预热 + 1000 正式请求
make contracts    # 导出 OpenAPI 与 JSON Schema
make progress     # 从实际测试工件更新报告、RTM 和测试状态
make docs-check   # 检查 30 类文档、引用与映射，不运行业务测试
make verify       # 顺序执行测试、黄金回归、合同导出、进度同步和文档校验
```

前端在 Node 22 环境执行 `npm ci --prefix dashboard` 与 `npm run build --prefix dashboard`。服务器只需预构建静态文件。开发者从本地镜像运行 `python3 scripts/sync_server.py`，以内容哈希同步到 5090；发现服务器意外修改时拒绝覆盖。服务器生成的证据通过 `python3 scripts/pull_evidence.py` 回收，发现未同步的本地改动也会停止。日常完整循环可执行 `bash scripts/dev_cycle.sh`：构建 → 同步 → 5090 验证 → 回收文档 → 再次同步；不会自动重启运行服务。

## 当前验收边界

这是可运行的受控开发版，尚未完成 PRD 的全部效果与发布验收。最新 InjecAgent 27B v4 每组1054条已记录，基线996条有效、防护1002条有效；防护观察到的模拟攻击执行成功为0，但52条未知对应4.93%的保守上界。AgentDojo正常任务成功84/97→59/97，存在明显效用损失；ASB适配小样两组各40条、各25条有效。F1、完整消融、正式接入、Docker干净部署与七天稳定性仍未完成，详见公开报告与[ASB小样评审](docs/05-validation/asb-pilot-review.md)。

默认 HTTP 收件端点是隔离模拟账本，Git 远端是本地 bare 仓库。只有网关内工具及受限 Python 的执行边界经过测试；拥有宿主文件或网络权限的外部 Agent 可以绕开代理，不能宣称它们自动得到强制隔离。注册的 stdio MCP **进程本身属于可信计算基**，其输出和描述仍是不可信数据。详见 [实际部署指南](docs/07-operations/23-deployment-guide.md) 与 [实现决策](docs/adr/adr-007.md)。

## 公开评测与独立标注

运行器、配对验收与复现命令见 [benchmarks](benchmarks/README.md)。5090 的 `artifacts/annotation-packet-v2` 提供 982 条未标注候选（100 个任务组、dev450/test候选532）；仍需独立标注、近重复/模板分组检查和仲裁，不能直接作为隐藏 test 或 F1 结果。
