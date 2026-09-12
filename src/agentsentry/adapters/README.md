# adapters

当前模块已纳入开发版实现。provenance 的运行逻辑集中在 gateway/runtime.py 与 trace/store.py；其他模块直接包含其职责代码。

[总体设计](../../../docs/03-architecture/10-system-design-rfc.md) · [实际测试报告](../../../docs/05-validation/18-test-benchmark-report.md) · [实现边界](../../../docs/adr/adr-007.md)

修改安全相关逻辑时同时更新对应 TC/RTM，运行 make verify。自动化覆盖不替代公开效果评测和独立安全签收。
