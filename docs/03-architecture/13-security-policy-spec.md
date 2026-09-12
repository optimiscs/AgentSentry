# 13 安全策略规范

文档 ID：AS-DOC-13 ｜ 版本：1.0-review ｜ 更新：2026-09-12  
Owner：B ｜ 状态：`draft` ｜ 人工评审：尚未完成

[返回文档导航](../README.md)

2026-09-12 补充：默认 unknown_destination 规则增加 `not intent.destination_matches("destination")`。谓词要求外发已授权、无明确禁止、实际目标集合非空且全部在受信用户任务的精确目标集合中。它不提升目标信任等级，不覆盖硬 BLOCK，不授权金融金额，也不从正文提取许可。HTTP 重定向须提交新受控动作。参见 [ADR-008](../adr/adr-008.md)。

## 三态与优先级

ALLOW表示合同/策略允许且可执行对象已确定；ASK只用于可由合法用户解决的授权不确定；BLOCK表示硬拒绝、显式禁止或不能安全执行。QUARANTINE是处置动作，不能成为第四种决策；提示文本IGNORE_CLAIM/ALERT属于诊断事件。

优先级：Critical硬拒绝→用户/静态显式DENY→对ASK规则有效的精确审批→ASK→显式ALLOW→按effect/resource的安全默认。任何复合effect命中硬拒绝则整体BLOCK；授权部分effect不代表整个工具调用被授权。

## DSL v1提案

```text
rule credential_read severity critical overridable false {
  when action.effect == FILE_READ
    and resource.class == CREDENTIAL
    and intent.sensitive_access != ALLOW
  then BLOCK("CREDENTIAL_ACCESS_NOT_AUTHORIZED")
}
```

使用受限parser/AST与白名单函数，不执行任意Python或eval。未知谓词/错误类型/资源解析失败均是策略错误；运行时有last-known-good只读策略则继续该版本，否则高危fail-closed。策略验证和发布分开，不能把MCP描述或LLM建议直接加载为生效规则。

首批13谓词：effect、tool/server、resource.matches、resource.class、destination.domain、destination.trust、intent.allows、intent.scope_contains、flow.has、source.type、source.trust、agent.depth、approval.valid。每个有至少一个正例、负例和边界例；数量统计按独立判定能力，不按规则条数。

| ID | 规则 | 默认结果 |
|---|---|---|
| POL-001 | 写模拟凭据/系统敏感路径 | BLOCK，不可审批覆盖 |
| POL-002 | SECRET/CREDENTIAL外发未经敏感数据与目的双重明确授权 | BLOCK；域名trusted本身不构成允许 |
| POL-003 | 下载后直接交解释器执行的高危组合 | BLOCK；适配器必须检查真实effect |
| POL-004 | 编码/混淆后执行且不能证明安全 | BLOCK或按可授权能力限制；不能只匹配前缀 |
| POL-005 | 任务未明确授权的Git push且用户具有批准权 | ASK，绑定remote/branch/commit |
| POL-006 | 未授权敏感凭据读取 | BLOCK |
| POL-007 | 跨scope写入 | 静态上限外BLOCK；上限内可授权灰区ASK |
| POL-008 | SECRET委派到未授权子Agent | BLOCK |
| POL-009 | 非敏感数据到未知目的但可合理授权 | ASK；命中POL-002时仍BLOCK |
| POL-010 | 委派超过深度/预算或试图扩权 | BLOCK |
| POL-011 | Memory持久污染指令 | BLOCK并QUARANTINE，P1 |
| POL-012 | 工具文本声明可信/管理员角色 | 忽略授权声明，记录风险；候选动作再正常求值 |

## 审批与策略发布

默认TTL10分钟、一次性nonce、用户权限/会话/动作/参数/资源版本/Intent及策略版本绑定。批准之后仍可能因对象变化失效；显示“已批准”不等于“已执行”。策略变化、密钥轮换和回滚均使不兼容旧审批失效。硬拒绝不可被普通审批覆盖。

规则提交包括FR/SR映射和TC-12用例，A/B交叉评审，先在合成/批准测试环境shadow比较，再逐步enforce。敏感硬规则在真实接入环境不能为校准而全局关闭。保留前一可用策略版本和hash；回滚后复验关键安全不变量，不只复验可用性。

当前没有生效策略文件或引擎，以上均为实现规范。不得将本页示例当作已能执行的配置格式，W1–W2完成parser契约后再冻结。
