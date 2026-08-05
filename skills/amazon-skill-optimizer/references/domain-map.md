# Amazon Domain Pack 路由

本文件用于审计“另一个 Amazon Skill”是否具备正确的业务边界、输入契约、证据链和失败降级；它不直接执行选品、广告、Listing 等业务任务。

## 总则

- 主链固定为：`需求 → 可发现性 → 点击 → 转化 → 履约 → 口碑/复购 → 贡献利润与现金`。
- 合规是 Hard Gate，不得被总分抵消；库存、资金与产能是约束；广告是放大器，不得脱离 Listing、价格、评论、库存与贡献利润单独诊断。
- 一次仅加载 1–2 个命中域。超过两个域时按风险与主链顺序分批，保留跨域依赖。
- 冲突优先级：站点规则 > 类目规则 > 生命周期规则 > 通用默认。跨站点规则不得静默套用。
- `stable`：已抽象进本 Skill 的稳定框架；`private-runtime`：仅在用户明确要求且有权限时查询私库，绝不固化账号标识或精确阈值；`official-live`：政策、费率、资格、界面行为等执行前必须查询适用站点的当前官方来源。
- GBrain 是创建期知识来源和可选运行时证据源，不是本 Skill 的强制运行依赖。引用格式为 `source_id::slug`。

## D01 市场研究与选品

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 关键词机会、类目机会、竞品研究、细分市场 Go/No-Go、候选池筛选 |
| 核心业务对象 | Marketplace、类目、搜索意图、需求信号、竞品、目标客户、价格带、单位经济 |
| 必需输入 | `country, target_customer, price_band, business_objective, account_data_or_public_data`，以及全域必填字段 |
| 关键决策链 | 定义市场与客户 → 多源验证需求 → 竞争结构与进入门槛 → 供应/合规可行性 → 保守单位经济 → Go/No-Go 与待验证项 |
| 常见失败 | 只看搜索量；把第三方估算当销量事实；忽略供应、合规或利润；跨站点复用结论 |
| 推荐方法 | 需求-竞争-利润-风险模型、JTBD/VOC、假设驱动、敏感性分析、Stage-Gate |
| 不适用方法 | 无证据的 SWOT；只有单一加权总分的“自动选品”；缺分布数据的伪蒙特卡洛 |
| 数据源要求 | 至少两类独立需求/竞争证据；市场数据必须带站点、时间、覆盖与置信度；估算必须标第三方 |
| 安全与合规门槛 | 高风险品类、受限商品、IP 或认证未核验时不得给无条件 Go |
| Golden Set | 强需求但利润/合规失败的反例；多站点数据泄漏反例；完整 Go/No-Go 正例 |
| 相邻域边界 | 产品规格进入 D02；供应成本进入 D03；价格策略进入 D08 |
| 站点注意 | US 只是默认测试站；税费、消费者语言、认证与竞争结构必须按站点重建 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/市场需求`；`private-runtime`: `seller-brain::products/选品方法`；`official-live`: 当前类目限制与公开市场页面 |

## D02 产品开发与差异化

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 产品定义、需求转规格、竞品差异化、样品验证、Stage-Gate |
| 核心业务对象 | 产品类型、目标客户、使用场景、痛点、属性、规格、证据、风险与验收标准 |
| 必需输入 | `product_type, target_customer, business_objective, constraints, account_data_or_public_data` |
| 关键决策链 | VOC/JTBD → 痛点根因 → 属性/规格 → 样品与测试 → 可证明卖点 → 上市与迭代门槛 |
| 常见失败 | 痛点未转可测规格；差异化没有客户价值；卖点早于证据；一次样品即宣告验证 |
| 推荐方法 | JTBD、VOC 聚类、Kano、QFD、5 Whys、FMEA、Stage-Gate |
| 不适用方法 | 只做功能清单；未经样品/测试的“创新评分”；用评论频次替代因果验证 |
| 数据源要求 | 原始 VOC 可追溯，规格有测试方法与验收阈值，结论区分观测、推断与验证 |
| 安全与合规门槛 | 材料、安全、性能和健康宣称无适用证据时 BLOCK |
| Golden Set | 痛点→属性→规格→测试→证据闭环正例；高频痛点误因果反例 |
| 相邻域边界 | 市场吸引力归 D01；采购与成本归 D03；表达与 SEO 归 D04/D05 |
| 站点注意 | 标准、尺寸、插头、语言、标签和声明要求按销售站点与目的国核验 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/产品定义`；`private-runtime`: `seller-brain::sops/产品开发`；`official-live`: 当前产品安全与标签规则 |

## D03 供应链、采购与单位经济

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 供应商评估、采购决策、Landed Cost、贡献利润、交期/产能风险 |
| 核心业务对象 | 供应商、MOQ、BOM、包装、交期、运费、关税、费用、退货损失、现金 |
| 必需输入 | `fulfillment_model, currency, tax_basis, constraints, price_band` |
| 关键决策链 | 需求区间 → 供应能力/质量 → 完整 Landed Cost → 贡献利润 → 现金与风险 → 采购门槛 |
| 常见失败 | 漏项成本；混币种/税基；缺失值当零；用最低报价替代总风险 |
| 推荐方法 | Landed Cost、贡献毛利、敏感性分析、FMEA、情景规划、供应约束分析 |
| 不适用方法 | 自动换汇但无汇率时间；只比单价；用毛利率替代现金可行性 |
| 数据源要求 | 所有金额带币种、税基、单位、时间；报价与费率有来源；未知项显式缺失 |
| 安全与合规门槛 | 关键成本口径不一致或供应合规证据缺失时不得给精确利润/采购结论 |
| Golden Set | 完整成本复算正例；混币种、漏税、缺失当零反例 |
| 相邻域边界 | 需求归 D01；产品规格归 D02；补货与周转归 D09；促销利润归 D08 |
| 站点注意 | 关税、VAT/GST、FBA 费用和包装标签均按站点及生效日实时核验 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/库存供应`；`private-runtime`: `seller-brain::supply-constraints/供应链降本`；`official-live`: 当前税费、关税与平台费用 |

## D04 Listing、SEO、Rufus 与 COSMO 内容理解

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 标题/五点/描述、关键词映射、搜索意图覆盖、Listing 审计 |
| 核心业务对象 | Query、Keyword、Search Term、属性、事实、卖点、证据、Locale |
| 必需输入 | `locale, product_type, target_customer, business_objective, account_data_or_public_data` |
| 关键决策链 | 意图与词层级 → 产品事实/适配 → 差异化证据 → 内容结构 → 可读性/合规 → 索引与转化验证 |
| 常见失败 | 堆词牺牲可读性；宣称超出证据；Keyword 与 Search Term 混淆；把 Rufus/COSMO 推测当规则 |
| 推荐方法 | 搜索意图分层、评论痛点→属性→卖点→证据链、IPO 契约、对抗测试 |
| 不适用方法 | 只套 AIDA；按词频机械复读；把模型生成内容当产品事实 |
| 数据源要求 | 产品事实优先第一方资料；关键词证据带站点/时间；每项强宣称可追溯 |
| 安全与合规门槛 | 医疗、性能、环保、比较级或认证宣称缺证据时 BLOCK 或删除 |
| Golden Set | 可读且有证据的内容正例；堆词、虚构卖点、跨语言规则泄漏反例 |
| 相邻域边界 | 产品定义归 D02；图片/视频归 D05；广告搜索词归 D07 |
| 站点注意 | 字段长度、禁限词、语言和搜索行为按站点实时核验；Rufus/COSMO 仅作待验证机制 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/listing内容`；`private-runtime`: `seller-brain::keywords/关键词分层`；`official-live`: 当前 Listing 指南与搜索体验 |

## D05 主图、视频、A+ 与视觉沟通

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 主图规划、七图脚本、视频分镜、A+ 信息架构、视觉审计 |
| 核心业务对象 | 产品事实、使用场景、视觉层级、图片/视频槽位、声明、可访问性 |
| 必需输入 | `locale, product_type, target_customer, business_objective, constraints` |
| 关键决策链 | 识别任务 → 事实与证据 → 首屏识别 → 差异/适配沟通 → 风险消除 → 移动端可读性 → 验证 |
| 常见失败 | 视觉承诺超出产品证据；主图不合规；所有图重复卖点；文字在移动端不可读 |
| 推荐方法 | 信息层级、JTBD 场景、证据链、Pre-mortem、Golden Set 视觉断言 |
| 不适用方法 | 只追求“高级感”；无事实约束的生成图；把审美评分替代合规/识别测试 |
| 数据源要求 | 真实产品图/尺寸/包装/证书；每个视觉声明绑定证据；生成内容标记来源 |
| 安全与合规门槛 | 误导尺寸、配件、效果、人物使用或认证；主图/A+ 禁限元素未核验时不得发布 |
| Golden Set | 槽位职责清晰正例；多送配件、尺寸错觉、虚构效果反例 |
| 相邻域边界 | 文案与关键词归 D04；产品事实归 D02；品牌/IP 归 D11 |
| 站点注意 | 图片、视频、A+ 资格与规范属于 `official-live`，不得固化旧尺寸或资格 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/质量体验`；`private-runtime`: `seller-brain::sops/voc入库`；`official-live`: 当前创意素材与 A+ 规范 |

## D06 新品冷启动与增长

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 上市准备度、30/60/90 天计划、增长瓶颈定位、阶段门禁 |
| 核心业务对象 | 生命周期、Retail Readiness、流量、转化、评价、库存、预算、贡献利润 |
| 必需输入 | `seller_model, fulfillment_model, business_objective, data_time_window, account_data_or_public_data` |
| 关键决策链 | Readiness → 基线 → 最窄约束 → 小步实验 → 阶段门槛 → 扩量/修复/停止 |
| 常见失败 | 未准备就投流；固定天数模板无阶段证据；只看订单不看利润/库存；同时改变多变量 |
| 推荐方法 | Stage-Gate、TOC、OODA/PDCA、Retail Readiness、基线比较 |
| 不适用方法 | 固定“第几天必做”阈值；无限预算换排名；把相关性当增量效果 |
| 数据源要求 | 阶段、基线、实验窗口、库存和贡献利润齐备；账号数据缺失时只给结构性审计 |
| 安全与合规门槛 | 库存、Listing、价格、评价或合规未就绪时不得建议激进放量 |
| Golden Set | Readiness 未通过却放量反例；按约束迭代的正例 |
| 相邻域边界 | 广告执行归 D07；价格促销归 D08；库存约束归 D09 |
| 站点注意 | 新品计划、资格和评价获取方式按站点当前规则核验 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/经营节奏`；`private-runtime`: `seller-brain::decisions/回报周期`；`official-live`: 当前计划资格与平台规则 |

## D07 Amazon Ads

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | SP/SB/SD 诊断、搜索词复盘、竞价预算、归因、增量放量 |
| 核心业务对象 | Profile、Campaign、Ad Group、Target/Keyword、Search Term、Placement、Attributed Sales |
| 必需输入 | `currency, attribution_window, business_objective, data_time_window, account_data_or_public_data` |
| 关键决策链 | Readiness → 流量角色 → 曝光/CPC → CTR → CVR → 订单归因 → TACoS/贡献利润 → 增量动作 |
| 常见失败 | 只看 ACoS；Keyword/Search Term/Target 混淆；归因窗口不一致；空报表当零；无库存仍放量 |
| 推荐方法 | 漏斗断点、Break-even ACoS/TACoS、边际收益、因果图/反事实、OODA |
| 不适用方法 | 私库固定竞价阈值全局化；用广告归因销量等同增量销量；忽略自然销售与生命周期 |
| 数据源要求 | 优先授权第一方报表；字段、站点、时区、币种、归因窗口和下载时间必须保留 |
| 安全与合规门槛 | V1 不执行调价、否词、预算或状态写入；缺归因/币种/实体映射时 BLOCK 精确动作 |
| Golden Set | 完整漏斗与利润诊断正例；仅按 ACoS、实体错配、归因冲突反例 |
| 相邻域边界 | Listing 转化根因归 D04；促销价格归 D08；库存约束归 D09 |
| 站点注意 | 广告产品、字段、归因和资格可能变化，执行建议必须 `official-live` |
| 知识标记与来源 | `stable`: `amazon-general::concepts/广告流量`；`private-runtime`: `seller-brain::sources/digests/亚马逊广告摘要`；`official-live`: 当前 Ads Console/官方报表定义 |

## D08 定价、Coupon、Deal 与促销

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 价格带、促销利润、Coupon/Deal 可行性、价格实验 |
| 核心业务对象 | Offer、售价、参考价、折扣、平台费、税、广告、退货、贡献利润 |
| 必需输入 | `price_band, currency, tax_basis, business_objective, data_time_window` |
| 关键决策链 | 客户价值/价格带 → 完整成本 → 参考价与资格 → 情景利润 → 试验 → 长期价格认知 |
| 常见失败 | 折扣前利润口径不全；混含税/未税；把促销销量当长期需求；使用过期资格 |
| 推荐方法 | 贡献毛利、敏感性分析、情景规划、期望值、Stage-Gate |
| 不适用方法 | 只跟竞品最低价；无对照的“促销有效”；用销售额替代贡献利润 |
| 数据源要求 | 价格、费用、税、时间窗和归因一致；资格与参考价来自当前官方或账号证据 |
| 安全与合规门槛 | 价格/税基/费用缺失不得给伪精确利润；V1 不创建促销 |
| Golden Set | 促销后贡献利润正例；参考价过期、混税、只看销量反例 |
| 相邻域边界 | 基础成本归 D03；广告归因归 D07；Offer/库存归 D09 |
| 站点注意 | 参考价、Coupon/Deal 资格、费用与消费者法属于 `official-live` |
| 知识标记与来源 | `stable`: `amazon-general::concepts/定价利润`；`private-runtime`: `seller-brain::campaigns/放量成本`；`official-live`: 当前促销资格、费用与价格政策 |

## D09 库存、FBA、补货与现金周转

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 补货、缺货风险、库龄、FBA 费用、周转与现金计划 |
| 核心业务对象 | SKU/FNSKU、库存位置、需求区间、交期、服务水平、库龄、现金 |
| 必需输入 | `fulfillment_model, data_time_window, currency, constraints, account_data_or_public_data` |
| 关键决策链 | 需求区间 → 完整交期 → 安全库存/服务水平 → 补货点 → 仓储费用/库龄 → 现金压力 |
| 常见失败 | 单点预测；忽略生产/运输/入仓全交期；库存数量与可售混淆；广告放量不看库存 |
| 推荐方法 | 补货点、安全库存、ABC-XYZ、库存周转、现金转换周期、情景规划 |
| 不适用方法 | 固定覆盖天数全类目化；缺服务水平的伪精确安全库存；以销售额替代需求 |
| 数据源要求 | SKU 级库存、在途、销量窗口、交期分解和币种；未知供应时间不得补零 |
| 安全与合规门槛 | 实体映射或库存状态不清时不得输出实际补货量；V1 不建货件 |
| Golden Set | 区间补货正例；Parent ASIN 当 SKU、交期漏项、空库存导出当零反例 |
| 相邻域边界 | 采购与成本归 D03；放量归 D06/D07；退货损失归 D10 |
| 站点注意 | FBA 容量、费用、仓储和配送限制按站点与生效日实时核验 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/库存供应`；`private-runtime`: `seller-brain::supply-constraints/库存放量`；`official-live`: 当前 FBA 容量与费用规则 |

## D10 评论、退货、VOC 与售后

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 评论聚类、退货根因、VOC 入库、质量改进、售后闭环 |
| 核心业务对象 | Review、Feedback、Return Reason、Contact、SKU/批次、属性、根因 |
| 必需输入 | `product_type, locale, data_time_window, account_data_or_public_data, risk_tier` |
| 关键决策链 | 脱敏采集 → 主题/场景聚类 → SKU/批次/Listing/退货交叉验证 → 根因 → 产品/内容/服务动作 → 复测 |
| 常见失败 | 只统计词频；混淆产品评论与卖家反馈；样本偏差不披露；引用个人信息 |
| 推荐方法 | VOC/JTBD、5 Whys/Ishikawa、Pareto、因果图、QFD、Human-in-the-loop |
| 不适用方法 | 单条评论决定改款；情感分数替代根因；推断用户身份或敏感属性 |
| 数据源要求 | 来源、语言、时间、SKU/变体和采样范围；原文最小化存储并脱敏 |
| 安全与合规门槛 | 不生成操纵评论、诱导评价或联系评论者的方案；PII 必须删除或掩码 |
| Golden Set | 多源根因闭环正例；词频即因果、父子混样、PII 泄露反例 |
| 相邻域边界 | 产品修复归 D02；内容修复归 D04/D05；账号健康归 D11 |
| 站点注意 | 评论、退货与沟通政策按站点当前官方规则核验 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/评论口碑`；`private-runtime`: `seller-brain::sops/voc入库`；`official-live`: 当前评论、退货与买家沟通政策 |

## D11 品牌、合规、IP 与账号健康

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 合规预检、商标/专利风险、受限商品、账号健康、申诉材料审计 |
| 核心业务对象 | 品牌、商标、专利、类目要求、政策、证书、Case、账号事件 |
| 必需输入 | `country, locale, product_type, constraints, risk_tier, account_data_or_public_data` |
| 关键决策链 | 识别适用法域/站点 → 风险分类 → 当前官方规则 → 授权证据 → Hard Gate → 人工/专业复核 |
| 常见失败 | 用历史政策做当前结论；单站规则泛化；把相似性搜索当法律结论；缺账号证据推断状态 |
| 推荐方法 | 合规/IP 门禁、风险矩阵、FMEA、Pre-mortem/红队、Human-in-the-loop |
| 不适用方法 | 用总分抵消红线；模型自行给法律结论；根据私库旧案例推断当前账号 |
| 数据源要求 | 官方当前政策、适用市场与生效日；授权第一方账号证据；必要时专业意见 |
| 安全与合规门槛 | 高/关键风险缺当前官方证据即 BLOCK；不得泄露账号、Case、Token 或主体信息 |
| Golden Set | 站点/生效日正确的门禁正例；过期政策、跨站点套用、伪账号状态反例 |
| 相邻域边界 | 产品安全设计归 D02；Listing 声明归 D04；运营指标归 D12 |
| 站点注意 | 所有执行性合规结论均为 `official-live`；Skill 只给证据化风险分流，不替代法律意见 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/合规规则`；`private-runtime`: `seller-brain::governance/合规红线`；`official-live`: 适用站点官方政策与法域规则 |

## D12 经营分析、报表与异常监控

| 项目 | 规格 |
|---|---|
| 典型目标 Skill | 周期报表、指标诊断、异常监控、经营复盘、决策仪表盘 |
| 核心业务对象 | Report、Metric、Dimension、Baseline、Alert、Decision、Action、Verification |
| 必需输入 | `currency, tax_basis, attribution_window, data_time_window, account_data_or_public_data, business_objective` |
| 关键决策链 | 来源/字段契约 → 数据质量 → 同口径基线 → 异常定位 → 业务根因 → 动作/负责人 → 复测 |
| 常见失败 | 空导出当零；跨报表字段直接相加；时区/币种/归因不一致；有图表无决策 |
| 推荐方法 | IPO/契约测试、基线比较、异常检测/控制图、Pareto、OODA/PDCA |
| 不适用方法 | 无稳定基线的复杂模型；仅凭相关性自动归因；为补齐图表插值关键缺失 |
| 数据源要求 | 保留 report type、字段定义、下载时间、时区、币种、税基、归因窗口与覆盖 |
| 安全与合规门槛 | 数据质量失败时只输出质量报告；V1 不发送外部消息或自动改运营对象 |
| Golden Set | 同口径异常闭环正例；空数据、字段漂移、混时区/归因反例 |
| 相邻域边界 | 专域根因转 D01–D11；本域负责跨域口径、监控与决策闭环 |
| 站点注意 | 报表字段、API 版本和归因定义变更必须 `official-live` 核验 |
| 知识标记与来源 | `stable`: `amazon-general::concepts/数据接口`、`amazon-general::concepts/经营底盘`；`private-runtime`: `seller-brain::campaigns/数据诊断`；`official-live`: 当前报表字典与 API 文档 |

## 私库与时效边界

- 私库只提供模式、失败案例和本地运行证据；真实店铺数值、ASIN/SKU、人员、供应商、账户结构、固定竞价/点击/利润阈值不得进入全局 Skill。
- Draft、inbox、raw 与转写材料不得直接成为规范；它们只能触发待验证假设、反例或 Golden Set。
- Rufus、COSMO、费用、促销资格、广告产品/归因、账号健康、政策和法规均视为可能漂移；运行时没有当前官方证据时输出 `UNVERIFIED`、`PARTIAL` 或 `BLOCKED`。
