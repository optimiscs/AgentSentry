# MSB 源码协议与判定器核查

更新：2026-09-12。状态：**PROTOCOL_INVENTORY_ONLY_NO_MCP_TOOLS_EXECUTED**。[作者仓库](https://github.com/dongsenzhang/MSB)固定提交 `c1d6a70171e4d2c44c87a2ae909d13df00c6aa8d`，源码包SHA `d829ce0f914ac7d740544534e018fe5cae1baf3d3d210355d0767f1817a0eb9c`。没有执行上游安装脚本、模型或MCP工具。

## 固定版本的实际场景

按已审阅main.py的原生循环与工具存在过滤，索引一个模型的2000个场景。当前源码有10个领域、64条任务，其中图像生成2条；[论文v2](https://arxiv.org/html/2510.15994v2)表7写65条、图像生成3条。采用实际清单，不补造任务。

| 原生类型 | 每模型场景数 |
|---|---:|
| prompt_injection / false_error / simulated_user / prompt_injection-simulated_user / prompt_injection-false_error | 各300 |
| name_overlap / preference_manipulation / out_of_scope_parameter / tool_transfer / preference_manipulation-out_of_scope_parameter / preference_manipulation-simulated_user | 各80 |
| search_term_deception | 20 |

清单所需源码文件均存在，但外部服务尚未验证。33份服务器配置中4份含环境变量配置，13份依赖`@latest`包，11份有绝对路径占位符，1份参数内有预置Authorization值；报告只保留名称、布尔标志和哈希，不加载这些值。setup.py会改写配置并把补丁移动进LangChain安装目录，未运行该脚本。

55个攻击变体Python文件中静态发现267个带tool装饰器的函数定义，包含重复变体，不能等同于已验证论文中的405个远程工具。接入前需固定依赖/工具版本，设置临时工作区与合成目标，再检查真实MCP分派和环境变化。

## 已执行的评分反例

固定哈希后，仅加载两段原生评分函数与所需常量，在临时目录创建合成日志/空文件。四项检查均得到以下真实结果，没有模型或工具执行：

| 合成输入 | 原生判定 | 尚未证明的行为 |
|---|---|---|
| 参数日志中模型名为空字符串，冒号后有空格 | attack_success=true | 非空参数已外发 |
| 预期输出路径存在一个空文件 | attack_success=true | 指定攻击内容已写入 |
| 日志只有正常工具提议 | user_task_success=true | 工具已执行并完成任务 |
| 日志缺少完成标记 | 不生成评分行 | 失败/超时已纳入分母 |

另发现5组原生输出文件名碰撞，均涉及检索场景第0/1任务，日志名本身没有碰撞。后续使用每场景独立工作目录，保留原生代理分数，并单列非空参数分派、准确文件变化及未知结果上界。不能直接用原生过滤后的CSV签收完整验收。

[机器清单](../evidence/msb-protocol-inventory.json)保存场景、配置及源码指纹；[评分证据](../evidence/msb-evaluator-audit.json)保存反例。MSB模型效果、污点TPR、canary外泄和黄金DAG仍未完成。
