# 组件契约

## 选择原则

组件按数据特征选择，不按“页面看起来丰富”选择。组件库支持全部十组必备能力；一份报告只渲染有有效数据的组件。缺失、冲突或不可用数据不得生成空图、假占比或装饰性评分。

| 数据特征 | `type` | 固定视觉组合 |
|---|---|---|
| 核心指标 | `kpi_cards` | KPI Cards |
| 分布/占比 | `distribution` | 饼/环形图 + Progress Bar |
| 趋势 | `line_chart` | 折线图 |
| 排名/TOP N | `data_table` | Data Table |
| 多维度对比 | `radar_comparison` | 雷达图 + Comparison Grid |
| 原始文本证据 | `quote_cards` | Quote Cards |
| 关键词/话题 | `keyword_topics` | Tag Cloud + Data Table |
| 结论/建议 | `summary_insights` | Summary Box + Insight List |
| 四维度综合研判 | `swot_grid` | SWOT Grid |
| 图片视觉证据 | `evidence_image_grid` / `evidence_compare` | Evidence Image Grid / Compare |

另支持 `narrative` 和 `checklist`，用于知识正文与操作清单；它们不能冒充数据组件。

## 公共字段

每个组件必须有 `type`，可有非空 `title` 和显式 `component_id`。缺少 `component_id` 时渲染器按 `section_id + 顺序号` 生成确定性唯一 ID；显式提供时必须全局唯一。所有文本按普通文本转义；任何字段都不能承载 HTML、SVG 或 JavaScript。

## 专属字段

### `kpi_cards`

`metric_ids[]` 引用已声明指标。只显示值状态有效的指标；缺失指标可显示明确缺失状态，但不得显示为 0。组件不得自动组成固定“三等分卡片”。

### `distribution`

需要 `dataset_id`、`label_key`、`value_key`，可选 `chart=donut|pie`。同一有效分布同时生成饼/环形图和语义化 Progress Bar 列表。Progress Bar 只表示真实占比或完成度；负值、总和不可解释或缺失分母时不得绘制占比图。

### `line_chart`

需要 `dataset_id`、`x_key` 和 `series[]`；每条 series 有 `key` 与可选 `label`。缺失点断开，不插值成事实；真实零保留；负数按完整数值域绘制。

### `data_table`

需要 `dataset_id`，可选 `column_keys[]` 与正整数 `top_n`。表格必须有 caption、列头 `scope=col`、键盘可横向滚动，并保留排序/排名的上游顺序。渲染器以表头和整列全部已格式化单元格的可见文本为输入：中文及 Unicode 全角字符计 1 个视觉单位，半角英文、数字和符号计 0.5，组合符与控制字符计 0；隐藏的来源说明不参与计宽。整列最大值 `≤10` 时按内容收紧并保持单行，`>10` 时按 `min(48, max(16, 4 × ceil((最大视觉单位 + 2) / 4)))em` 分档设置展示宽度；超过 48em 容量的内容在 48em 列内正常换行，不截断、不省略、不隐藏原值。5 列以上或 4 列且存在加宽列时采用内容密集宽表，14 列以上采用密集表。序号、编号、排名、排行、名次及对应英文标识列在所有值不超过 6 个视觉单位时继续紧凑展示。相同列级审核也用于图表数据摘要、雷达 Comparison Grid、关键词表和来源附录；渲染器不重新计算排名。

### `radar_comparison`

需要 `dataset_id`、`axis_key` 与 `series[]`。同一数据生成雷达图和 Comparison Grid。尺度必须由有效数据定义；缺失轴不补零，轴或系列不足时跳过图表并保留可读对比数据。

### `quote_cards`

`quotes[]` 每项包含 `text`、`source_ref`，可选 `author`、`rating`、`sentiment`。引文保持上游原文，不因模板标点规则改写；作者等可能识别个人的信息必须先由上游脱敏。

### `keyword_topics`

需要 `dataset_id`、`keyword_key`、`weight_key`，可选 `column_keys[]`。同一数据生成 Tag Cloud 与 Data Table。权重只控制字号范围，不推导情绪、重要性或业务优先级。

### `summary_insights`

包含 `summary` 与 `insights[]`。Insight 可为纯文本，或 `{title, detail?, severity?, source_refs?}`。渲染器只展示上游结论；不补写建议、不提高结论强度。`DEMO` 报告的该区域必须重复演示标识。

### `swot_grid`

固定 `strengths`、`weaknesses`、`opportunities`、`threats` 四组。每项可为字符串或 `{text, source_refs?}`。空维度保持明确“无有效数据”或跳过整个组件，不用模型臆造补齐四格。

### `evidence_image_grid`

`images[]` 每项包含 `src`、`alt`，可选 `caption`、`source_ref`。只接受本地 PNG/JPEG/WebP 或对应 data URI；渲染时内嵌到单文件 HTML。单张上限 5 MiB，合计上限 20 MiB。

### `evidence_compare`

固定 `left` 与 `right` 两张证据图，各含 `src`、`alt` 和可选 caption/source_ref；可选 `left_label`、`right_label`。比较只表达并排证据，不生成“改前/改后”因果结论。

### `narrative`

`paragraphs[]` 为普通文本段落。禁用 Markdown/HTML 解析，不允许远程链接自动展开。

### `checklist`

`items[]` 包含 `label`、`status=done|pending|blocked|warning` 与可选 `detail`。状态必须来自上游事实；渲染器不自动关闭任务。

## SVG 与无障碍

图表由渲染器根据 dataset 确定性生成内联 SVG；输入不得含 SVG。每张图必须含可访问标题、描述和文本数据摘要。颜色不能是唯一编码，打印版必须保持可辨识。JavaScript 被禁用时，正文、表格、摘要和图表数据摘要仍完整可读。
