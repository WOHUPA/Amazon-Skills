# Report Spec

## 协议

`protocol: "amazon-html-report/v1"` 是唯一受支持的输入协议。所有输入必须符合 `assets/report-spec.schema.json`。

## 顶层结构

| 字段 | 说明 |
| --- | --- |
| protocol | 固定 `amazon-html-report/v1` |
| report | 报告元信息（标题、状态、版本、隐私等） |
| sources | 来源列表（类型、角色、覆盖、时点、质量） |
| metrics | 指标列表（值、状态、单位、来源、派生） |
| datasets | 数据集（表格、分布、序列、雷达、引用等） |
| sections | 章节与组件树 |
| limitations | 限制列表（严重级别、来源） |
| render | 渲染配置（布局族、主题、目录开关） |

## 值状态语义

- `OBSERVED`：直接观测值。
- `DERIVED`：派生值，必须带 `derivation.formula`、`derivation.input_refs`、`derivation.calculation_receipt`。
- `MISSING` / `NO_ROW` / `NO_ACCESS` / `COLLECTION_FAILURE`：缺失或不可用，值必须为 `null`，渲染为“缺失”标记。
- `CONFLICT`：来源冲突，值必须为 `null`，渲染为冲突标记。
- `NOT_APPLICABLE` / `NO_BASELINE`：不适用/无基线，值必须为 `null`。
- 禁止把 `null`、失败状态或缺失状态渲染为 `0`。

## 数据模式

- `data_mode: REAL`：真实数据。
- `data_mode: DEMO`：演示数据，页首、结论区和打印版必须持续显示演示标识。

## 报告状态

- `COMPLETE`：正常报告。
- `PARTIAL`：部分数据，须显示部分标记与限制。
- `BLOCKED`：数据质量阻塞，必须渲染数据质量/阻塞说明页。
