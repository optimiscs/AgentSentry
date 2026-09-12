# AgentSentry 控制台

React 19 + TypeScript；四个视图：事件、完整参数预览/审批、来源图、实测报告。所有证据作为文本渲染，未使用 dangerouslySetInnerHTML；CSP 拒绝外部脚本。令牌仅存在页面内存。

Node 22：`npm ci --prefix dashboard`，`npm run build --prefix dashboard`；产物写入 Python 包的 api/static 并随源码同步。API 同源，开发服务器只有本地代理；实测部署使用 FastAPI 静态服务。审批前可查询完整脱敏参数，hash 绑定原始参数。

[部署与接入](../docs/07-operations/23-deployment-guide.md) · [测试报告](../docs/05-validation/18-test-benchmark-report.md)
