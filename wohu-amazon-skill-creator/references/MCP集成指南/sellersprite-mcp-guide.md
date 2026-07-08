# SellerSprite MCP 集成指南

本指南只记录当前 Codex 环境可发现的 SellerSprite 工具。不要在生成 skill 时引用未列出的工具名。

## 可用工具

| 工具 | 用途 | 典型输入 |
| --- | --- | --- |
| `asin_detail` | 查询单个 ASIN 商品详情、类目、价格、评分、卖家、变体和 Listing 质量 | `asin`、`marketplace` |
| `asin_detail_with_coupon_trend` | 查询 ASIN 详情并返回 Coupon 价格趋势 | `asin`、`marketplace` |
| `asin_coupon_trend` | 查询 ASIN 优惠价格信息 | `asin`、`marketplace` |
| `review` | 查询 ASIN 评论标题、内容、评分、时间等 | `asin`、`categoryId`、`marketplace`、`starList` |
| `bsr_prediction` | 根据类目和 BSR 预测日销量和近 30 天销量 | `bsr`、`categoryId`、`marketplace` |
| `product_node` | 查询 Amazon 类目信息 | `keyword` 或 `nodeIdPath`、`marketplace` |
| `keyword_research_trends` | 查询关键词搜索量、购买量、购买率和增长率 | `keyword`、`marketplace` |
| `aba_research_trend` | 查询 ABA 排名和搜索量趋势 | `keyword`、`marketplace` |
| `google_trend` | 查询 Google 搜索趋势，用于站外需求验证 | `keyword`、`marketplace` |

## 适合的业务环节

- 选品开发：ASIN 详情、BSR 预测、类目规模、关键词趋势。
- Listing 优化：ASIN 详情、评论痛点、关键词趋势。
- 差评预警：按星级筛选评论，提炼原因和改进动作。
- 价格监控：Coupon 趋势和最终成交价变化。

## 调用组合示例

### 竞品拆解

1. 对每个竞品 ASIN 调用 `asin_detail`。
2. 如需促销判断，调用 `asin_detail_with_coupon_trend` 或 `asin_coupon_trend`。
3. 如有 BSR 和类目节点，调用 `bsr_prediction` 估算销量。
4. 汇总价格、评分、评论、销量、优惠和 Listing 质量。

### 差评分析

1. 用 `review` 查询 1-3 星评论。
2. 按问题类型归类：质量、尺寸、包装、安装、物流、预期不符。
3. 输出严重程度、证据评论、产品改进、Listing 预期管理建议。

### 关键词趋势验证

1. 用 `keyword_research_trends` 看搜索量、购买量、购买率和增长率。
2. 用 `aba_research_trend` 看 ABA 排名和搜索量趋势。
3. 可用 `google_trend` 做站外需求对照，但不要用它替代 Amazon 站内需求。

## 注意事项

- `marketplace` 使用 SellerSprite 枚举，例如 US、JP、UK、DE、CA。
- `review` 需要 `categoryId`，可先通过类目或 ASIN 信息确认。
- BSR 预测依赖类目节点和 BSR，缺任一项时不要强算。
- 输出竞品结论时要区分“数据事实”和“推断建议”。
