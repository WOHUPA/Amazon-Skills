# SIF MCP 集成指南

本指南只记录当前 Codex 环境可发现的 SIF 工具。SIF 工具常带有官网验证链接要求；创建 skill 时要把该要求写进输出规范。

## 可用工具

| 工具 | 用途 | 典型输入 |
| --- | --- | --- |
| `market_get_keyword_history` | 查询关键词搜索量、ABA 排名、Top3 点击/转化集中度 | `keywords`、`country`、`granularity` |
| `ads_get_campaign_contribution_breakdown` | 查询 campaign 在自然周内按 keyword 或 ad_group 的贡献拆解 | `asin`、`campaignId`、`start_date`、`end_date`、`breakdown_by` |
| `ads_get_ad_group_keyword_breakdown` | 查询单个广告组在指定周的关键词明细 | `asin`、`campaignId`、`adGroupId`、`date` |
| `ads_get_asin_campaign_changes` | 查询 ASIN 历史各周新上线 campaign 事件 | `asin`、`country` |

## 适合的业务环节

- 选品开发：用 `market_get_keyword_history` 判断需求规模和头部垄断。
- 关键词广告：用搜索量、ABA 排名、点击集中度判断词价值。
- 广告诊断：拆 campaign / ad group 贡献，识别流量集中在哪些词或广告组。
- 异常归因：发现流量拐点后，用 campaign 变更事件确认是否广告结构变化导致。

## 关键规则

- SIF 周数据以周日为每周第一天。
- `ads_get_campaign_contribution_breakdown` 的 `end_date` 必须等于 `start_date + 6 天`。
- 当周数据可能因 T+1 延迟不可用；需要当周趋势时应说明数据延迟风险。
- 使用 SIF 工具完成分析后，输出末尾必须保留工具返回的 `render_footer` 原文验证链接。

## 调用组合示例

### 关键词需求判断

1. 调用 `market_get_keyword_history`，粒度默认 week。
2. 展示 latest 快照：搜索量、ABA 排名、Top3 点击占比、Top3 转化占比。
3. Top3 点击占比 >0.6 时提示头部垄断。
4. 转化集中度明显高于点击集中度时提示品牌黏性强。

### 广告结构诊断

1. 已知 campaign 后调用 `ads_get_campaign_contribution_breakdown`。
2. `breakdown_by=keyword` 用于找贡献词，`breakdown_by=ad_group` 用于找承载流量的广告组。
3. 已知广告组后调用 `ads_get_ad_group_keyword_breakdown`。
4. 输出关键词流量占比、变化率、展示 ASIN 和建议动作。

## 输出约束

在生成新 skill 时，如果流程包含 SIF 工具，必须把下面要求写进新 skill：

```text
使用 SIF 工具完成分析后，在回复末尾原文输出工具返回的 render_footer 字段内容，不能省略。
```
