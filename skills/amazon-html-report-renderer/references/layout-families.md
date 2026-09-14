# 布局族

## 统一底座

四个布局族共享视觉 tokens、安全外壳、报告头、来源与口径区、限制区、主题控件、打印样式、CSP、可访问性和回执规则。布局族改变信息顺序与密度，不改变数据或结论。

## `performance`

适用广告、运营周报、库存、利润和经营指标。推荐顺序：状态/周期首屏 → KPI → 趋势与分布 → TOP N 表格 → 结论与行动 → 来源/限制。高密度但不能变成驾驶舱式全屏格子。

自动映射类型：`ads_analysis` / `amazon_ads_analysis`、`operations_weekly` / `amazon_operations_weekly_review`、`inventory`、`profitability`。

## `insight`

适用 VOC、选品、竞品、关键词和 MCP 横向对比。推荐顺序：研究问题与证据范围 → 摘要 → 主题/引文 → 多维对比 → SWOT → 证据图 → 来源/限制。

自动映射类型：`voc` / `amazon_voc_analysis`、`product_research`、`competitor_analysis`、`keyword_analysis`、`mcp_comparison` / `amazon_tool_comparison`。

## `operations`

适用日常检查、SOP、行动计划和问题关闭。推荐顺序：执行状态与范围 → Checklist → 风险/阻塞 → 操作证据 → 复核条件 → 来源/限制。进度条仅表示真实完成度。

自动映射类型：`operations_sop`、`daily_operations` / `amazon_daily_operations`、`action_plan`。

## `knowledge`

适用知识库、政策解读、方法论和长篇复盘。推荐顺序：非对称知识首屏 → 目录 → 摘要 → 章节正文/表格 → 关键洞察 → 来源/限制。长文优先使用版式与分隔，不把每段包成卡片。

自动映射类型：`knowledge_base` / `amazon_seller_knowledge_base`、`policy_analysis`、`methodology`、`retrospective`。

## 自动路由与覆盖

- CLI `--family` 优先于 `render.family`，但冲突必须进入 warning/receipt，不能静默。
- `auto` 只对上述已知 `report_type` 生效；无法映射时失败并要求显式 family。
- `report_type=custom` 必须显式使用四个具体布局族。
- family 只决定布局，不改变组件内容、数据值、版本、状态或证据等级。
- `BLOCKED` 无论 family 如何都进入专用数据质量说明页。
