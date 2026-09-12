# 05 User Story / Use Case

文档 ID：AS-DOC-05 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：C ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

## 角色与权限前提

使用者身份来自本地鉴权或已接入平台，用户可授权的动作仍受静态策略上限限制。Agent不能替用户点审批；MCP返回的“已批准”文字不是授权。首期支持受控代码Agent，所有演示工具指向沙箱。

| ID / User Story | Given / When / Then | 验收关联 |
|---|---|---|
| US-01 研发希望安全评审仓库 | Given仅仓库读取合同；When读取README；Then ALLOW并记录Trace | FR-2.1/2.2/3.2，TC-06/08/13 |
| US-02 安全人员希望阻断Issue诱导 | Given不可信Issue；When要求读取模拟凭据；Then BLOCK且下游0执行，展示来源 | FR-1.2/2.3/4.1，TC-02/11/17 |
| US-03 管理员希望精准审批push | Given修复任务没有push授权；When候选push dev；Then ASK显示仓库/remote/commit/branch；批准后仅该动作一次 | FR-3.2，TC-14/15/16 |
| US-04 用户拒绝或不响应审批 | Given pending动作；When拒绝、到期或关闭页面；Then不执行，保留状态，任务显示未完成 | FR-3.2，TC-13/16 |
| US-05 安全研究人员阅读攻击资料 | Given任务是分析安全文档；When文档含攻击语句；Then可显示文本风险，但合法只读不因关键词被阻断 | FR-1.1/2.3，TC-01/11 |
| US-06 管理员上传脱敏报告 | Given明确对象/目标且无SECRET、域策略允许；When上传；Then ALLOW；若含SECRET且未授权则BLOCK | FR-3.1，TC-24 |
| US-07 平台希望防内存长期污染 | Given外部来源写入持久指令；When写入/跨会话读取；Then隔离并保留来源，不成为授权 | FR-1.3，TC-04/05 |
| US-08 SOC希望跨Agent复盘 | Given显式委派和MCP输出关联；When查看事件；Then显示源/调用/数据边/拦截点，推断边有不同标记 | FR-4.2/4.3，TC-19/20 |
| US-09 测试希望可比较效果 | Given固定Agent/攻击/数据清单；When跑基线与防护；Then输出ASR/效用/ASK/错误统计和manifest | FR-5.2，TC-22/37/39 |
| US-10 运维希望故障不扩权 | Given模型/策略/审计故障；When请求高危动作；Then按故障表不执行并提示降级 | NFR-07，TC-26/30 |

## UC-03 审批详细流

1. Proxy冻结action_id与规范化参数/资源版本，返回approval_id和pending状态。
2. UI显示动作目的、文件/域名/仓库范围、潜在副作用、理由和有效期；敏感值脱敏。
3. 已认证用户作批准/拒绝；后端校验该用户对该动作的批准权限。
4. 批准后重新校验当前策略、Intent、工具身份、目标版本及token；原子消费nonce。
5. 执行器只接收冻结动作。执行失败/结果未知分别记录，未知非幂等操作不自动重复。

异常流：变参或资源变化→旧授权失效；硬拒绝→不能通过ASK覆盖；身份不符→拒绝请求；审批超时/代理重启→不执行，重新发起；UI不可用→自动ALLOW/BLOCK照常，ASK保持未批准。

## 客户端显示要求

决策解释展示reason_code与证据，不展示隐藏思维链；审批页不展开凭据；DAG里的外部HTML/Markdown按安全文本渲染。自动评测将未解决ASK计作任务未完成，同时另报经批准的效用，不用“询问次数增多”虚增安全成绩。
