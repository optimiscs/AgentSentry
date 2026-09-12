# 23 部署指南

文档 ID：AS-DOC-23 ｜ 版本：1.1-dev ｜ 更新：2026-09-12  
Owner：A ｜ 状态：`draft` ｜ 独立部署评审：尚未完成

[返回文档导航](../README.md)

## 5090 已验证部署

目录 `/root/autodl-tmp/AgentSentry`；独立解释器 `.venv/bin/python` 3.12.3，依赖以仓库 `requirements-lock.txt` 锁定。源码 editable 安装，CPU 规则检测，预构建 React 静态界面。服务只监听 127.0.0.1:8080，核心安全服务不使用 GPU；公开基准另用已有 vLLM 环境和 Qwen2.5-7B 在 localhost:18080 提供模型推理。

```bash
cd /root/autodl-tmp/AgentSentry
bash scripts/service.sh start
bash scripts/service.sh status
# 优雅停止：
bash scripts/service.sh stop
```

PID/log 位于 `artifacts/service.pid` / `artifacts/service.log`。`runtime-data/runtime.lock` 强制单进程，不启动多个 worker。不要在服务运行时使用会打开同一状态目录的离线 CLI demo；演示使用 UI/API。`service.sh` 是开发进程管理器，不等同于系统服务重启保障。

在自己的电脑执行 `ssh -N -L 127.0.0.1:8080:127.0.0.1:8080 5090`，浏览器访问 <http://127.0.0.1:8080>。操作员令牌在服务器 `runtime-data/operator.token`，Agent 令牌在 `agent.token`，文件权限 600；不能用 localhost 替代认证。每次浏览器刷新重新登录。

## 新环境安装与运行

Python >=3.11，Linux、git、系统 python3、libseccomp；沙箱需要 chroot/setuid/setgid 能力。没有这些能力时，exec.python 明确 BLOCK，普通规则/文件工具可独立测试。

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/pip install --no-deps -e .
make verify
make dev
```

Node 22 只用于 `make frontend`。默认演示初始化会拒绝覆盖非空用户仓库；自动生成 `.ssh/id_rsa` 中的内容是合成 canary，Git 远端是本地专属 bare 仓库。

## 配置与 MCP

AGENTSENTRY_ROOT 指向工程根；AGENTSENTRY_STATE_DIR 指向状态目录；AGENTSENTRY_WORKSPACE 指定受控根；AGENTSENTRY_POLICY 覆盖策略路径。默认将初始策略复制为 `runtime-data/active.aspolicy`，热修改不覆盖源码。AGENTSENTRY_DEMO=0 可关闭演示；真实 HTTP 必须通过 AGENTSENTRY_NETWORK_ALLOWLIST 显式配置域名，不能启用任意 URL。

MCP 客户端先由操作员通过 UI/API 创建任务，取得 session_id。stdio 配置：command 为工程 `.venv/bin/agentsentry`，args 为 `mcp --session <session_id>`，cwd 为工程根；该 façade 连接本机 8080 API，只读取 agent.token。Streamable HTTP 为 `/mcp/`，通过 Authorization: Bearer 请求头认证。两者都不能创建任务或审批。

外部下游 stdio server 仅从 `config/mcp-registrations.json` 读取管理员登记的绝对 command、args、tools 元数据 SHA-256、effects（当前泛型适配只允许 NET_EGRESS；文件/执行类必须新增专用资源适配器）。元数据漂移直接拒绝，默认注册表为空；服务进程必须可信，运行不可信 server 前需独立容器/虚拟机隔离。当前支持 stdio 下游，没有声称任意 HTTP 下游已适配。

## 容器与回滚

仓库提供 Dockerfile/compose.yaml，但 5090 无 Docker，**干净容器验收未执行**。Compose 发布端口仍仅绑定宿主 127.0.0.1，CPU=4、内存8g、只读根、最小所需 capabilities。首次初始化可使用 `docker compose run --rm gateway agentsentry init-demo`，然后 `docker compose up -d`；此命令为待验证路径，不计为本次部署通过。

停服后，用 `scripts/snapshot.py backup --state runtime-data --archive <path>.asbackup --key-file <separate-key-path>` 创建加密冷备份；备份密钥应与归档分开保管。恢复使用 `restore` 子命令并指定空状态目录；不要覆盖活动目录。已测试恢复保留审计且旧 pending 审批失效。恢复后 Git origin 若仍指向旧路径会被拒绝，必须人工校对到新状态目录专属 bare 仓库。备份 TTL 默认运维要求七天，目前需要运维按清单清理，不是自动托管备份服务。

## 验收边界

[测试报告](../05-validation/18-test-benchmark-report.md)是实际证据。外部 Agent 全面旁路限制、可选模型权重、公开基准、离线容器发布包、七天稳定性、独立安全评审仍未完成。单卡 5090 足够当前开发与队列化评测准备；当前应用开发和规则测试不依赖显卡。

## 原生 Hook 配置包（桥接测试通过，真实客户端尚未验收）

操作员先创建并确认任务，向桥接包提供 session_id 和 agent.token 文件路径。运行 `scripts/prepare_client_hooks.py --client codex` 或 `--client claude-code`，并指定 `--output` 新保护目录、`--session-id`、`--token-file`、`--python`。脚本生成 client.json、受保护的桥接脚本和 hooks.json / settings.json，不自动覆盖用户设置。Codex 按自身 Hook 信任流程审核后启用；Claude 按自身设置层合并。

配置包必须放在 Agent 不可写的控制目录。当前通配 Hook 拒绝未支持的原生工具与 MCP；支持范围及主机/路径约束见 [产品接入矩阵](../03-architecture/framework-integration-matrix.md)。原生 API 不执行候选工具；ASK 独立审批后仍需原调用在有界等待内取得一次 claim。等待结束后应重新发起新调用，旧许可不能复用。卸载仅移除本项目的配置条目及保护目录，保留其他 Hook；本文不把尚未运行的真实客户端安装宣称已验证。

## 当前客户端环境限制

5090 中实际执行 Codex 只读沙箱探测返回 bwrap 无权创建 namespace。需要具备受支持隔离能力的运行主机/容器配置；现有网关 chroot/seccomp 成功不代表 Codex 自身沙箱可用。没有关闭沙箱来取得 PASS。

模型现用32768上下文，8K首轮与32K第二轮分别保存。研究效果仍未达标。Codex 既有登录在本地 provider 测试中自动刷新并返回403，因此后续本地测试需独立账户环境；不修改地区或服务访问限制。
