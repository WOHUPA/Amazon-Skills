# Layout Families

## 布局族

| 布局族 | 适用报告类型 | 版式特征 |
| --- | --- | --- |
| performance | ads_analysis、amazon_ads_analysis | KPI 前置、趋势与分布并列、搜索词表 |
| insight | voc、amazon_voc_analysis、mcp_comparison、amazon_tool_comparison、competitor_analysis、keyword_analysis | 洞察摘要、引用卡片、雷达对比 |
| operations | operations_weekly、amazon_operations_weekly_review、operations_sop、daily_operations、amazon_daily_operations、action_plan、inventory、profitability | 叙述、检查清单、SWOT、决策支持 |
| knowledge | knowledge_base、amazon_seller_knowledge_base、policy_analysis、methodology、retrospective | 知识章节、方法论、限制说明 |

## 自动映射

- `render.family = auto` 时按 `report.report_type` 映射到上述布局族。
- 未识别的 `report_type` 且 `family=auto`：Schema 校验失败。
- `report_type = custom` 必须显式指定非 `auto` 的布局族。
- 显式 `family`（performance/insight/operations/knowledge）直接采用，不与 `report_type` 二次校验。
