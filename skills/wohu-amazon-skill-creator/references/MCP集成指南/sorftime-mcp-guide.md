# Sorftime MCP 集成指南

本指南只记录当前 Codex 环境可发现的 Sorftime 工具。不要在生成 skill 时调用未列出的 Sorftime 能力。

## 可用工具

| 工具 | 用途 | 典型输入 |
| --- | --- | --- |
| `product_ranking_trend_by_keyword` | 查询某 ASIN 在指定关键词下的曝光排名趋势 | `asin`、`keyword`、`amzSite`、`page` |
| `keyword_detail` | 查询亚马逊热搜关键词详情 | `keyword`、`amzSite` |
| `keyword_search_results` | 查询关键词搜索结果自然位产品清单 | `keyword`、`amzSite`、`page` |
| `keyword_trend` | 查询关键词搜索量、搜索排名、CPC 价格趋势 | `keyword`、`amzSite` |
| `favorite_keyword` / `del_favorite_keyword` / `change_favorite_keyword` | 管理亚马逊关键词收藏 | `keyword`、`amzSite`、`dict` |

沃尔玛相关工具存在，但创建亚马逊卖家 skill 时默认不使用，除非用户明确做 Walmart。

## 适合的业务环节

- 关键词广告：排名追踪、关键词趋势、搜索结果竞争页观察。
- Listing 优化：判断目标词下自然位竞品和关键词热度。
- 选品开发：用关键词趋势和搜索结果做市场初筛。
- 日常监控：跟踪核心词排名波动。

## 调用组合示例

### 关键词排名周报

1. 对每个 `ASIN + keyword` 调用 `product_ranking_trend_by_keyword`。
2. 对每个 keyword 调用 `keyword_trend` 判断需求和 CPC 是否变化。
3. 把排名变化 >10 位的词放入危险清单。

### Listing 关键词页检查

1. 用 `keyword_search_results` 拉关键词自然位产品清单。
2. 提取前 20 个竞品的标题、价格、评分等字段。
3. 对比用户 ASIN 的标题和卖点覆盖情况。

## 注意事项

- `amzSite` 使用 Sorftime 枚举，例如 US、GB、DE、FR、CA、JP。
- `page` 默认第一页；需要更多竞品时再翻页。
- Sorftime 当前可发现工具不包含完整评论分析或利润测算；这些场景应结合 SellerSprite 或用户输入。
- 写入收藏类工具属于账号状态修改，默认不在 skill 中自动执行，除非用户明确要求并二次确认。
