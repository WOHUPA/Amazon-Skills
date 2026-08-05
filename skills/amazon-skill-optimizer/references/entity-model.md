# Amazon 业务实体模型

实体审计的目标是证明“数据属于谁、在哪个站点、以什么粒度被计算”。同名字符串不能替代实体键，任何跨链连接都必须有显式映射和时间范围。

## 1. 广告实体链

```text
Marketplace
└── Profile
    └── Campaign
        └── Ad Group
            ├── Target
            │   ├── Keyword Target
            │   ├── Product/ASIN Target
            │   └── Category Target
            └── Search Term（由买家行为产生，不是配置对象）
```

| 实体 | 建议主键/作用域 | 含义 | 强制校验 |
|---|---|---|---|
| Marketplace | `marketplace_id` | 销售与广告规则适用市场 | 必须显式；不得由币种或语言单独推断 |
| Profile | `profile_id + marketplace_id` | Ads 账户在特定市场的执行上下文 | 一个 Profile 的结论不得默认扩展到其他 Profile/站点 |
| Campaign | `campaign_id + profile_id` | 预算、状态、广告产品和竞价策略容器 | 名称不是主键；保留广告产品、状态与时间 |
| Ad Group | `ad_group_id + campaign_id` | 广告、Target/Keyword 的分组上下文 | 不得跨 Campaign 汇总后仍称 Ad Group 级结论 |
| Target | `target_id + ad_group_id` | 配置的投放对象；可为关键词、商品或类目 | 必须保留 target type、match type 和表达式 |
| Keyword | `keyword_id + ad_group_id` | 一类可配置的关键词 Target | 不得用文字值替代 ID；同词可存在于多个组和匹配类型 |
| Search Term | `query_text + profile/campaign/ad_group + time_range` | 买家实际查询或报告返回的查询维度 | 不是配置 ID；必须保留报告粒度、时间和归因窗口 |

### 广告链校验

1. `Campaign.profile_id` 必须指向同一 Marketplace 的 Profile。
2. `AdGroup.campaign_id`、`Target.ad_group_id` 必须可回溯；孤立行标为数据质量 FAIL。
3. Search Term 必须带所属 Profile、Campaign/Ad Group（以报告可提供粒度为准）、时间范围和归因窗口；缺失时只允许聚合观测，不允许生成精确配置动作。
4. 聚合前检查广告产品、币种、时区、归因窗口和实体粒度一致；不一致必须拆组。
5. Target expression 是商品/类目时不得强制解释为 Keyword；Target 是关键词时也不能据此声称出现过同文本 Search Term。

## 2. 商品与履约实体链

```text
Parent ASIN
└── Child ASIN
    └── SKU
        └── FNSKU
            └── Offer
```

说明：这是一条审计用的典型逻辑链，不意味着每个业务都存在 Parent，也不意味着一个 SKU 永远只有一个 FNSKU 或 Offer。真实关系必须从站点、卖家、履约方式和有效期确认。

| 实体 | 建议主键/作用域 | 含义 | 强制校验 |
|---|---|---|---|
| Parent ASIN | `marketplace_id + parent_asin` | 变体关系的非购买父体 | 不得承载 SKU 级库存、价格或广告归因 |
| Child ASIN | `marketplace_id + child_asin` | 可售变体对应的目录商品 | ASIN 只在对应 Marketplace 语境内解释 |
| SKU | `seller/account + marketplace_id + sku` | 卖家自定义库存/Offer 标识 | 同一 ASIN 可有多个 SKU；不得省略卖家/站点作用域 |
| FNSKU | `seller/account + fnsku` | FBA 库存标签与履约识别 | 只在 FBA 语境成立；FBM 不应强造 FNSKU |
| Offer | `seller/account + marketplace_id + sku + effective_time` | 某卖家在站点的价格、库存与履约报价 | 价格和可售状态必须带时间；Offer 不是 ASIN 本体属性 |

### 商品链校验

1. Parent/Child 关系必须来自可追溯目录证据；没有变体时允许 Child ASIN 作为独立商品。
2. SKU 到 ASIN 的映射必须带卖家、站点和有效期；不得跨账号或站点复用。
3. FNSKU 仅用于适用的 FBA 库存；同一 SKU 因标签/库存池变化可能产生不同历史映射。
4. Offer 指标（价格、库存、配送方式）不得上卷为 Parent ASIN 固有事实；上卷时必须注明聚合规则与覆盖。
5. 任何补货、成本、退货或库存结论至少落到 SKU/FNSKU 合适粒度；只有 ASIN 时必须降级。

## 3. 两条链的显式连接

| 连接目的 | 允许的连接 | 必需证据 | 禁止的捷径 |
|---|---|---|---|
| 广告到商品 | advertised/targeted ASIN → Child ASIN；广告对象映射 → SKU | 报表字段定义、Marketplace、Profile、时间范围、ASIN↔SKU 映射 | 用 Campaign 名称猜 SKU；把 Target ASIN 当 advertised ASIN |
| 广告到 Offer | advertised Child ASIN → 卖家 SKU → 有效 Offer | 卖家/站点作用域、映射有效期、Offer 时间 | 用 ASIN 级销量直接推定某 SKU 的价格或库存 |
| Search Term 到关键词 | Query text ↔ configured Keyword/Target | 同一 Profile/组、匹配类型、报告时间 | 文本相同即视为同一实体；反向推断曝光一定来自该词 |
| 销量到库存 | 订单/销量粒度 → SKU/FNSKU 库存 | 同站点、同窗口、取消/退货口径、履约模型 | Parent ASIN 销量直接作为某一 FNSKU 需求 |

若映射是一对多或多对多，必须输出映射表和分摊规则。没有可验证分摊规则时标 `PARTIAL`，不得生成 SKU、Target 或预算级精确动作。

## 4. 常见混淆与检测

| 混淆 | 正确区别 | 检测方法 | 失败处理 |
|---|---|---|---|
| Keyword vs Search Term | Keyword 是配置对象；Search Term 是买家查询/报告维度 | 检查是否有 `keyword_id/match_type` 与 `query_text/time_range`；查报告字段字典 | Hard Gate；拆分实体并重算 |
| Target vs Keyword | Target 是上位配置对象；Keyword 只是其中一种类型 | 检查 `target_type` 与 expression；商品/类目 Target 不得出现 keyword 专属断言 | Hard Gate；恢复 target type |
| ASIN vs SKU | ASIN 是目录商品；SKU 是特定卖家的库存/Offer 标识 | 检查卖家/站点作用域和映射表；同 ASIN 是否出现多个 SKU | Hard Gate；禁止库存/成本级精确结论 |
| Parent vs Child ASIN | Parent 组织变体，Child 才通常对应可售变体 | 检查 variation relationship 与可购买性；指标是否错误落到 Parent | Hard Gate；回落到 Child/SKU |
| SKU vs FNSKU | SKU 是卖家标识；FNSKU 是 FBA 履约标签 | 检查 fulfillment model 与标签映射 | WARN 或 FAIL；补足履约上下文 |
| Product Target vs advertised ASIN | 前者是被定向对象，后者是被推广商品 | 检查报表字段名与广告产品文档 | Hard Gate；不得用对手 ASIN 指标代表自身商品 |
| Profile vs Seller account | Profile 是 Ads 市场上下文，不等同整个卖家账号 | 检查 profile marketplace 与授权范围 | BLOCK 跨 Profile/站点写入或推断 |
| 空值 vs 零 | 空值可能是无行、无权限、延迟或不适用；零是已观测数值 | 检查导出状态、行数、coverage 和字段可用性 | 空值标缺失，不参与零值计算 |

## 5. Evidence 绑定规则

- 实体主张必须填写 `entity_type` 与 `entity_id`；ID 需要在输出中脱敏时，仍应保留稳定的本地别名和安全映射。
- 金额或比率主张同时绑定 Marketplace、时间范围、币种、单位、税基及适用的归因窗口。
- Parent 聚合、跨 Campaign 聚合或跨站点汇总必须记录 coverage、聚合规则和 limitations。
- 发现孤立实体、作用域冲突、多对多无分摊或字段语义未知时，先输出数据质量问题，再决定 `ASK / DEGRADE / BLOCK`。
- 实体混淆属于不可被评分抵消的 Hard Gate；修复后必须重跑数值和行为评测。
