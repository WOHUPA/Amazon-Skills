# SIF MCP 数据结构地图

本文档记录当前 SIF MCP `tools/list` 与 `sif_catalog` 暴露的数据结构，用于 `amazon-ads-initialization` Skill 做新品广告初始化数据增强。

采集时间：2026-04-25  
数据源：SIF MCP `tools/list`、`sif_catalog`  
约束：只使用 SIF MCP，不调用 SellerSprite 或其他第三方数据源。

## 1. 当前结论

- 当前 SIF MCP 共暴露 27 个工具。
- 可直接服务新品广告初始化的核心数据包括：
  - ASIN 反查关键词、关键词流量贡献、自然排名、广告依赖度。
  - 关键词搜索量、ABA 排名、Top3 点击/转化集中度、需求生命周期、词根综合需求。
  - 关键词竞争格局、前 20 ASIN 自然/SP/SB/SBV 流量份额、可进入性判断。
  - Listing 自然/广告流量结构、SP/SB/SBV 渠道分布。
  - ASIN 销量、价格、变体销量趋势。
  - ASIN 广告结构、广告曝光趋势、Campaign 贡献、广告历史画像。
- 当前 SIF MCP schema 与描述中没有明确暴露 CPC、bid、广告竞价、点击成本字段。涉及 CPC 时必须使用用户提供值、Amazon 广告后台值，或标注为“数据缺失”，不得伪造。
- 部分广告工具要求在最终回复末尾原文输出工具返回的 `render_footer`，使用这些工具时必须保留。

## 2. 初始化调用策略

初始化场景优先使用轻量调用链。只有当轻量数据不足、结论冲突，或用户明确要求深挖竞品广告结构时，再调用补充工具。

### 2.1 用户提供目标 ASIN 或竞品 ASIN

默认只调用：

1. `market_get_asin_keyword_signals`
   - 用途：反查 ASIN 的主要流量词、自然排名稳定性、关键词健康状态、付费依赖。
   - 用于 Skill：生成核心词、长尾词、竞品截流词、初始否词候选。
2. `ops_get_listing_traffic_overview`
   - 用途：看 Listing 自然流量与广告流量占比，以及 SP、SP 推荐、SB、SBV 渠道贡献。
   - 用于 Skill：判断新品初始化应偏 SP 自动拓词，还是偏手动精准卡位。

结论冲突或需要预算承受能力判断时再调用：

3. `ops_get_asin_sales_list` 或 `ops_get_asin_sales_trend`
   - 用途：获取价格、近 30 天销量、当月销量、变体销量趋势。
   - 用于 Skill：判断预算承受能力、生命周期、是否适合激进放量。

用户明确要求分析竞品广告结构，或轻量数据无法判断红海程度时再调用：

4. `ads_get_asin_ad_structure`
   - 用途：查看历史累计 SP/SB/SBV Campaign 数量。
   - 用于 Skill：判断竞品广告复杂度和市场红海程度。
5. `ads_get_asin_ad_traffic_trend`
   - 用途：查看 SP/SB/SBV 广告曝光趋势和主力渠道。
   - 用于 Skill：判断竞品主要广告打法。

### 2.2 用户提供关键词

默认只调用：

1. `market_get_keyword_history`
   - 用途：获取搜索量、ABA 排名、Top3 点击集中度、Top3 转化集中度。
   - 用于 Skill：判断蓝海/红海、是否适合新品主攻。
2. `market_get_keyword_competition`
   - 用途：判断关键词竞争格局、前 20 ASIN 流量份额、可进入性、推荐广告重点。
   - 用于 Skill：决定蓝海/红海、主攻词、候选验证词和排除词。

需要判断季节性、启动时机或需求是否分散到长尾词时再调用：

3. `market_get_keyword_demand`
   - 用途：判断关键词生命周期、趋势方向、季节性、距峰值周数、行动时机。
   - 用于 Skill：判断是否现在启动、是否需要控制初始化预算。
4. `market_get_keyword_root_trend`
   - 用途：对比精确词搜索量与词根综合搜索量，判断需求是否分散到长尾词。
   - 用于 Skill：决定 SP 自动与长尾手动词的比例。

### 2.3 用户提供 Campaign 或 Ad Group 信息

默认不作为新品初始化必调数据，只有用户明确给出广告结构 ID 或要求拆解竞品广告时调用：

- `ads_get_asin_campaign_contribution_overview`
- `ads_get_campaign_structure`
- `ads_get_campaign_contribution_breakdown`
- `ads_get_campaign_traffic_trend`
- `ads_get_ad_group_traffic_trend`
- `ads_get_ad_group_keyword_breakdown`

## 3. 数据结构清单

### 3.1 场景应用

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `analyze_traffic_anomaly` | 流量异常根因诊断、Mermaid 流程图、行动建议 | 只用于流量下滑诊断，不用于新品初始化 | 否 |

### 3.2 运营数据：流量

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `ops_get_asin_traffic_trend` | `dates[]`、`scores[]`、`channelBreakdown[]`，含 natural、ad、sp、recSp、sb、sbv | 判断 ASIN 流量趋势、广告依赖、渠道结构 | 可选 |
| `ops_get_asin_traffic_trend_detail` | `list[]`，含 keyword、totalScore、naturalScore、adScore、naturalRank、spRank、sbRank | 关键词级反查，提取自然词和广告词候选 | 补充，有 ASIN 且需要关键词明细时 |
| `ops_get_listing_traffic_overview` | `overview`、`adChannelBreakdown`、`recSourceDistribution[]` | 判断自然/广告占比、SP/SB/SBV 渠道权重 | 默认，有 ASIN 时 |
| `ops_get_listing_traffic_structure` | `list[]`，含 totalScore、nfs、ads、sps、recs、sbs、sbvs | 对比变体流量结构，选择主推变体 | 可选 |

### 3.3 运营数据：销量

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `ops_get_asin_sales_trend` | `list[]`，含 asin、dimension、months[].date、months[].sales | 判断销量趋势、季节性、生命周期 | 补充，有预算或生命周期冲突时 |
| `ops_get_asin_sales_list` | `list[]`，含 asin、price、color、size、boughtInPastMonth、boughtInMonth、monthlyTrend[] | 获取价格、近 30 天销量、当月销量、变体排行 | 补充，有预算或变体选择需求时 |

### 3.4 反查关键词

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `ops_get_listing_keyword_distribution` | `list[]`，含 total、natural、ad、sp、rec、brand、vedio | 判断变体覆盖词数、自然词/广告词数量结构 | 可选 |
| `market_get_asin_keyword_signals` | `primary_signals`、`secondary_signals`、`top_keywords[]`，含关键词健康状态、排名演变、付费依赖、SP campaign 关联 | 反查竞品核心流量词、识别主攻词/风险词/付费依赖词 | 默认，有 ASIN 时 |

### 3.5 查关键词：需求

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `market_get_keyword_demand` | `profiles[]`，含 search_volume、trend、seasonality、diagnosis、interpretation、weeks_to_peak | 判断需求生命周期、是否当下适合启动 | 补充，需要季节性或启动时机判断时 |
| `market_get_keyword_history` | `keywords[]`，含 volumes[]、ranks[]、top3_click_shares[]、top3_conversion_shares[]、latest | 判断搜索量、ABA 排名、头部点击/转化集中度 | 默认，有关键词时 |
| `market_get_keyword_root_trend` | keyword_search_volumes[]、ext_search_volumes[]、latest.coverage_ratio | 判断精确词覆盖率、长尾需求空间 | 补充，需要长尾空间判断时 |

### 3.6 查关键词：竞争

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `market_get_keyword_competition` | `competition_position`、`concentration_profile`、`top_asins[]`、`market_context`、`system_state`、`demand_structure`、`supply_profile` | 判断关键词可进入性、蓝海/红海、SP/SB/SBV 投放重点、竞品 ASIN 定向候选 | 默认，有关键词时 |

### 3.7 查广告：ASIN 层

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `ads_get_asin_ad_structure` | `ad_types[]`、`total_campaign_count` | 判断竞品广告复杂度和广告类型覆盖 | 补充，轻量数据无法判断红海程度时 |
| `ads_get_asin_ad_traffic_trend` | `trend[]`、`trend_analysis`，含 SP/SB/SBV 曝光趋势和 dominant_channel | 判断竞品主力广告渠道 | 补充，用户要求竞品广告结构时 |
| `ads_get_asin_ad_feature_profile` | 指定窗口广告特征画像 | 判断近 30 天广告集中度、渠道结构和投放稳定性 | 可选 |
| `ads_get_asin_ad_historical_feature_profile` | 长期投放节奏、Campaign 集中度、渠道组合、增长轨迹 | 判断竞品长期广告成熟度 | 可选 |
| `ads_get_asin_ad_window_feature_profile` | 窗口期广告特征画像 | 判断指定时间窗口内广告结构变化 | 可选 |
| `ads_get_asin_campaign_contribution_overview` | `campaigns[]`，含 campaign_id、ad_type、contribution_score、share、tier | 识别竞品主力 Campaign 类型 | 深度分析时调用 |
| `ads_get_asin_campaign_changes` | `campaign_changes[]`，含 date、ad_type、campaign_id | 判断竞品是否近期新增 Campaign | 深度分析时调用 |

### 3.8 查广告：Campaign / Ad Group 层

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `ads_get_campaign_structure` | Campaign 下广告组结构 | 需要 campaignId 才能使用 | 否 |
| `ads_get_campaign_traffic_trend` | Campaign 生命周期流量趋势、广告组创建事件 | 需要 campaignId 才能使用 | 否 |
| `ads_get_campaign_contribution_breakdown` | 按 keyword 或 ad_group 拆分 Campaign 贡献 | 需要 campaignId 才能使用 | 否 |
| `ads_get_ad_group_traffic_trend` | Ad Group 历史流量趋势 | 需要 adGroupId 才能使用 | 否 |
| `ads_get_ad_group_keyword_breakdown` | `keywords[]`，含 trafficShareWithinAdGroup、displayAsins[] | 拆解广告组内关键词贡献 | 否 |

### 3.9 工具目录与连通性

| 工具 | 核心返回 | 初始化用途 | 调用层级 |
|---|---|---|---|
| `sif_catalog` | SIF 工具分类目录 | 查看可用能力，不参与业务判断 | 否 |
| `ping` | 连通性检查 | 检查 MCP 是否可用 | 否 |

## 4. 对 Skill 的字段映射

| 初始化判断 | 优先 SIF 字段 | 规则用法 |
|---|---|---|
| 蓝海 / 红海 | `market_get_keyword_history.latest.top3_click_share`、`top3_conversion_share`、`market_get_keyword_competition.concentration_profile.level`、`system_state`、`ads_get_asin_ad_structure.total_campaign_count` | 低集中度、广告结构简单偏蓝海；高集中度、多广告类型覆盖、头部稳定偏红海 |
| 关键词需求强弱 | `market_get_keyword_history.latest.volume`、`latest.rank`、`market_get_keyword_demand.current.search_volume` | 搜索量和 ABA 排名决定是否作为主攻词或候选验证词 |
| 关键词生命周期 | `market_get_keyword_demand.trend`、`seasonality`、`weeks_to_peak`、`interpretation` | 旺季前加速，衰退或窗口关闭时降低预算 |
| 长尾词策略 | `market_get_keyword_root_trend.latest.coverage_ratio`、`ext_search_volume` | 覆盖率低时提高 SP 自动和长尾手动比例 |
| 竞品截流 | `market_get_keyword_competition.top_asins[]`、`market_get_asin_keyword_signals.top_keywords[]` | 选择前 20 ASIN 或关键词强相关 ASIN 做 ASIN 定向候选 |
| 广告类型权重 | `ops_get_listing_traffic_overview.adChannelBreakdown`、`ads_get_asin_ad_traffic_trend.trend_analysis.dominant_channel` | 竞品只靠 SP 时优先 SP；SB/SBV 活跃时提示品牌内容门槛 |
| 预算承受能力 | `ops_get_asin_sales_list.price`、`boughtInPastMonth`、`boughtInMonth`、`ops_get_asin_sales_trend.months[].sales` | 销量稳定且价格带足够时可提高测试预算；销量弱时保守测试 |
| 变体选择 | `ops_get_listing_traffic_structure.list[]`、`ops_get_listing_keyword_distribution.list[]`、`ops_get_asin_sales_list.list[]` | 优先选择销量、流量、关键词覆盖更强的变体作为广告入口 |
| CPC / 竞价 | 当前 SIF schema 未提供 | 只能使用用户输入、后台建议竞价或 SOP 默认比例；必须标注数据来源 |

## 5. 使用边界

- 不把 SIF 曝光分数等同于真实销量、真实点击或真实广告花费。
- 不把 SIF 中的广告流量得分等同于 Amazon Ads 后台的 spend、CPC、CTR、CVR、ACOS。
- 不使用未在工具返回中出现的字段进行确定性判断。
- 使用广告类工具时，如果工具返回 `render_footer`，最终回复必须保留原文。
- 没有 ASIN 或关键词时，回退到纯 SOP 规则模式，并明确标注“缺少 SIF 查询入参”。
