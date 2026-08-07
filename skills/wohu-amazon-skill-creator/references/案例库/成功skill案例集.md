# 成功 Skill 案例集

这些案例用于给新 skill 提供结构参考。不要整段复制；根据用户业务目标、工具可用性和输出落点改写。

## 1. 关键词排名周报 skill

- 场景：每周追踪核心词自然排名和搜索需求变化。
- 工具：SIF `market_get_keyword_history`，Sorftime `product_ranking_trend_by_keyword`。
- 输入：站点、ASIN 清单、核心词清单、周日期。
- 输出：Markdown 周报 + 异常清单 + 可选飞书摘要。
- 核心规则：排名下滑 >10 位标危险；连续 2 周下滑升级人工介入。

## 2. 广告异常预警 skill

- 场景：每日或每周检查广告活动是否失控。
- 工具：SIF `ads_get_campaign_contribution_breakdown`、`ads_get_ad_group_keyword_breakdown`。
- 输入：ASIN、campaign ID、ad group ID、自然周起止日期。
- 输出：异常 campaign/ad group 清单、问题关键词、建议动作。
- 核心规则：ACoS 超阈值、CTR/CVR 低于阈值、流量集中在低转化词时进入异常清单。

## 3. 选品可行性分析 skill

- 场景：新品开发前评估市场容量、竞争强度和利润空间。
- 工具：SellerSprite `asin_detail`、`bsr_prediction`、`keyword_research_trends`，SIF `market_get_keyword_history`，Sorftime `keyword_search_results`。
- 输入：类目关键词、目标站点、竞品 ASIN、成本结构。
- 输出：Go / No-Go / Watchlist 结论、利润测算、风险清单。
- 核心规则：净利率 <15% 默认 No-Go；Top3 点击占比 >0.6 标记头部垄断。

## 4. Listing 优化建议 skill

- 场景：优化现有 Listing 的标题、五点、图片和 A+。
- 工具：SellerSprite `asin_detail`、`review`，Sorftime `keyword_detail`，SIF `market_get_keyword_history`。
- 输入：ASIN、现有文案、核心关键词、竞品 ASIN。
- 输出：优化建议清单、改写后的标题/五点、图片脚本、合规风险。
- 核心规则：关键词分层后再埋词；差评高频问题必须转为文案或产品改进建议。

## 5. 库存补货计算 skill

- 场景：按销量预测补货量和时间节点。
- 工具：当前无专用库存 MCP 时，使用用户粘贴、Excel/CSV 或领星导出数据。
- 输入：ASIN、当前库存、在途、日均销量、生产周期、头程、目标安全库存。
- 输出：建议补货量、最晚下单日、断货风险、资金占用提醒。
- 核心规则：可售天数 <14 天标危险；14-30 天预警；30-60 天健康。

## 6. 差评预警与分析 skill

- 场景：监控新增差评并归因，形成改进建议。
- 工具：SellerSprite `review`，可结合 `asin_detail` 看评分和 Listing 信息。
- 输入：ASIN、站点、星级范围、时间范围、类目节点。
- 输出：差评清单、原因分类、严重程度、产品/Listing/客服改进建议。
- 核心规则：差评率 >10% 标危险；重复出现的尺寸、材质、安装、包装问题优先处理。

## 复用方式

创建新 skill 时，从最接近的案例抽取：

1. 触发话术。
2. 输入字段。
3. MCP 组合。
4. 判断规则。
5. 输出模板。

