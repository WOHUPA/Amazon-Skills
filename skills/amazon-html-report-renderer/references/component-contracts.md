# Component Contracts

## 组件契约

每个组件只接收契约定义的结构化字段。所有正文文本（标题、数值、标签、引用、图表坐标）都必须经过 HTML 转义；组件不得输出 raw HTML 或 raw JavaScript。

### 1. kpi_cards

- `metric_ids`: 至少 1 个，引用 `metrics[].metric_id`。
- 渲染为 KPI 卡片组，自动布局；不支持首屏之外的图标与花哨装饰。

### 2. distribution

- `dataset_id` 指向 `kind=distribution` 的数据集。
- `label_key` / `value_key` 指向数据集列。
- 渲染为确定性 SVG 环形图/饼图，随 `<svg>` 提供 `<title>` 与 `<desc>`。

### 3. line_chart

- `dataset_id` 指向 `kind=series` 的数据集。
- `x_key` 为横轴列；`series[]` 为一条或多条折线。
- 渲染为确定性内联 SVG 折线图，无外部图表库。

### 4. data_table

- `dataset_id` 指向 `kind=tabular` 数据集。
- `column_keys` 指定展示列；`top_n` 截断行数（可选）。
- 按设计系统的表格规则渲染（列宽审核、宽表/密集表、打印自适应）。

### 5. radar_comparison

- `dataset_id` 指向 `kind=radar` 数据集。
- `axis_key` 为各轴标签列；`series[]` 为参与对比的系列。
- 渲染为确定性内联 SVG 雷达图，附 `<title>` / `<desc>`。

### 6. quote_cards

- `quotes[]` 每条含 `text` 与 `source_ref`。
- 渲染为引用卡片；文本必须 HTML 转义，含引号的原文完整保留。

### 7. keyword_topics

- `dataset_id` 指向 `kind=keywords` 数据集。
- `keyword_key` / `weight_key` 指定关键词列与权重列。
- 渲染为话题表与标签云；列宽按统一可见宽度算法审核。

### 8. summary_insights

- `summary` 一段话；`insights[]` 为洞察条目（字符串或带 severity 的对象）。
- 渲染为结论区，可带严重级别徽标。

### 9. swot_grid

- `strengths` / `weaknesses` / `opportunities` / `threats` 四组条目。
- 渲染为四象限网格；条目支持文本或对象（含 `source_refs`）。

### 10. evidence_image_grid

- `images[]` 每条含 `src`（本地图片路径或 data URI）与 `alt`。
- 仅允许 PNG/JPEG/WebP；单张 ≤ 5 MiB、合计 ≤ 20 MiB；禁止远程 URL 与 SVG。

### 11. evidence_compare

- `left` / `right` 两张证据图对比；`left_label` / `right_label` 为标签。
- 并排布局，保留 alt 文本。

### 12. narrative

- `paragraphs[]` 纯文本段落。
- 渲染为叙述区块，文本转义。

### 13. checklist

- `items[]` 每条含 `label` 与 `status`（done/pending/blocked/warning）。
- 渲染为带状态符号的检查清单。

## 附加约束

- 空组件、空图、无有效数据组件一律不渲染；`{{`/`{%` 残留视为渲染失败。
- 每个组件可带 `component_id` 与 `title`，title 不改变语义结构。
- 组件类型未知时 Schema 校验直接失败。
