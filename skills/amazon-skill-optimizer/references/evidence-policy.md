# Amazon Skill 证据策略

本策略约束审计结论如何从来源进入主张、计算和动作。存储位置、文档成熟度、来源权威、产品验证强度和主张性质是不同维度，禁止相互“升级”。

## 1. 八层知识架构

| 层 | 内容与存储位置 | 加载条件 | 来源优先级 | 更新与过期 | 冲突解决 | 隐私边界 |
|---|---|---|---|---|---|---|
| ① Skill 协议层 | 目标 `SKILL.md`、`agents/`、脚本、模板、eval | 每次审计必读真实生效目录及同名副本 | 目标 Skill 当前文件 > 历史摘要 | 文件变化即重审；不以旧记忆替代 | 以实际生效路径为准；同名副本显式列出 | 密钥、Token、Cookie 不进入报告 |
| ② 业务本体层 | 本 Skill 的 `entity-model.md`、`domain-map.md` | 命中 Amazon 域或实体计算 | 稳定实体定义 > 模糊自然语言 | 结构变更或官方字段变更时复核 | 站点 > 类目 > 生命周期 > 通用 | 账号实体 ID 默认脱敏 |
| ③ 稳定方法论层 | `methodology-map.md`、`failure-patterns.md` | 已识别具体失败模式时按需加载 | 可验证方法链 > 通用框架 | 季度或失败回归后复核 | 能产生证据化动作的方法优先 | 只保留抽象模式，不复制私库阈值 |
| ④ 官方时效知识层 | 运行时官方政策、费率、资格、字段文档 | 执行性政策/费用/资格/账号结论时强制加载 | 当前适用官方来源 | 通常 30 天；执行日前仍须 live check | 同站点同主题以更新且生效的官方文本为准 | 保存最小引用，不保存登录凭证 |
| ⑤ 指标与计算层 | 公式、输入 JSON、`validate_calculations.py` 输出 | 出现金额、比率、归因、库存计算时 | 原始字段定义与可复算输入 > 摘要数 | 任一口径/费率/窗口变化即失效 | 不同币种、税基、单位、粒度、归因先拆分 | 商业数值只保留任务必需范围 |
| ⑥ 数据源与工具层 | 官方导出、API/MCP 响应、第三方文件及工具日志 | 目标 Skill 声称调用数据/工具时 | 授权第一方 > Amazon 公共 > 可信第三方 | 第一方 7 天；公共/第三方按下文 freshness | 空、失败、无权限与零严格分开 | 最小权限、只读优先，响应先脱敏 |
| ⑦ 账号/项目私有层 | 用户文件、可选 GBrain `seller-brain`、项目资料 | 用户明确要求且授权、且公共信息不足时 | 只对该账号/项目有效，不自动外推 | 依据数据窗口；历史经验不证明当前状态 | 与当前第一方冲突时以当前第一方为准并保留冲突 | 不固化真实店铺、ASIN/SKU、人员、供应商、阈值 |
| ⑧ 案例与评测层 | `golden-cases.jsonl`、trigger eval、历史回归 | 行为评测与发布判定 | 固定断言 + 可复现证据 > 模型自评 | 行为契约变化时版本化；未执行即 UNVERIFIED | 新用例不得通过删旧用例或放宽断言解决 | 使用匿名/合成案例，禁止真实敏感样本 |

GBrain 的稳定治理依据包括 `amazon-general::governance/来源边界`、`amazon-general::governance/入库规范`；私库召回与入库模式参考 `seller-brain::governance/召回策略`、`seller-brain::workflows/业务入库`，仅用于抽象流程，不提升原始来源权威。

## 2. 五级事实证据

| 等级 | 可接受来源 | 可支持的主张 | 限制 |
|---|---|---|---|
| E1 | 当前适用的官方政策/文档；授权第一方账号或店铺数据 | 对应站点的当前规则，或对应账号/窗口的已观测事实 | 官方政策不能证明账号实际状态；第一方账号数据不能替代平台通用政策 |
| E2 | Amazon 公共市场证据，如公开详情页、搜索页、公开榜单 | 指定站点、抓取时间和覆盖范围内的市场观测 | 不能当作完整市场或授权账号事实 |
| E3 | 有方法、日期、覆盖和限制的可信第三方数据 | 有置信区间/限制的估算或趋势 | 必须标 `trusted_third_party`，不得冒充销量、搜索量等第一方事实 |
| E4 | 历史案例、专家经验、经整理的私库内容、用户提供但未验证来源 | 假设、启发、模式、待验证 Seller Fit | 不能证明当前政策、市场或账号状态 |
| E5 | 模型推断或无外部证据的分析 | 候选假设、检查清单、下一步验证建议 | 状态始终 `unverified`，不得作为高风险执行依据 |

### source_type 映射

- `official_policy`、`authorized_first_party` → E1，但二者适用主张不同。
- `amazon_public` → E2。
- `trusted_third_party` → E3。
- `historical_case`、`expert_experience`、`user_provided` → 默认 E4；若用户文件的底层官方/第一方来源已验证，应按底层来源重新分类并保留原始位置。
- `model_inference` → E5。

第三方估算不得冒充第一方事实；历史知识不得替代实时账号检查；缺数据输出 `PARTIAL / BLOCKED / UNVERIFIED`，缺失值不得当零。

## 3. 四个独立证据维度

| 维度 | 取值 | 回答的问题 | 禁止混淆 |
|---|---|---|---|
| 来源权威 | `S0–S5` | 信息最初来自哪里、对哪类主张有权威 | 存入 GBrain 或被人工整理不改变原始权威 |
| 产品验证强度 | `A–D` | 产品/方案经过多强的样品、测试或市场验证 | 高权威政策不等于产品已验证；销量观测不等于根因已验证 |
| 文档成熟度 | `raw → digest → manual-confirmed → formal` | 内容经过多少治理与确认 | formal 私库页仍可能只是 E4，不会自动成为 E1 |
| 主张性质 | `Fact / Analysis / Seller Fit` | 是观测事实、分析推断，还是特定卖家的适配判断 | Analysis 和 Seller Fit 必须展示推理与限制，不得标成 Fact |

### S0–S5 到 E1–E5

- S0（当前官方原文）和 S1（授权第一方）映射 E1，但必须保留各自适用范围。
- S2 必须检查底层来源：Amazon 公共证据映射 E2，可信第三方映射 E3，不能仅凭 S2 标签决定。
- S3（整理后的内部知识）与 S4（历史/专家/用户材料）映射 E4。
- S5（模型生成或无来源推断）映射 E5。

### 产品验证强度 A–D

- A：重复测试或真实使用验证，样本、方法、验收与反例可追溯。
- B：有样品/实验或多源一致观测，但覆盖或复现有限。
- C：有需求/VOC/竞品证据，尚未完成产品级验证。
- D：仅假设或模型建议，未验证。

产品验证强度必须另行记录在 Observation/Inference 的上下文中，不占用 `evidence_level`。

## 4. Evidence Schema（25 字段）

输入可以是单个 JSON 对象、JSON 数组或 JSONL。未知字段可以保留，但以下字段的名称和语义不得改写。

| # | 字段 | 类型/允许值 | 必填与校验 |
|---:|---|---|---|
| 1 | `evidence_id` | 非空字符串 | 核心必填；文件内唯一且稳定 |
| 2 | `claim_id` | 非空字符串 | 核心必填；指向被支持/反驳的 claim |
| 3 | `claim` | 非空字符串 | 核心必填；一次只表达一个可核验主张 |
| 4 | `source_type` | `official_policy, authorized_first_party, amazon_public, trusted_third_party, historical_case, expert_experience, user_provided, model_inference` | 核心必填；决定默认证据等级上限 |
| 5 | `source_location` | 字符串或可定位引用 | 核心必填；不得写搜索结果页或虚构 URL |
| 6 | `marketplace` | Marketplace code/string | 核心必填；跨站点须拆成多条或显式列表 |
| 7 | `category` | 字符串或 null | 类目相关主张条件必填 |
| 8 | `entity_type` | 实体类型字符串或 null | 实体主张条件必填，遵循 entity-model |
| 9 | `entity_id` | 字符串/脱敏别名或 null | 实体主张条件必填；必须与 entity_type 匹配 |
| 10 | `time_range` | `{start,end}` 或 null | 指标、趋势、账号状态条件必填；ISO 日期/时间 |
| 11 | `observed_at` | ISO 8601 时间 | 核心必填；记录实际观测/下载时间 |
| 12 | `effective_date` | ISO 日期/时间或 null | 政策、费率、资格条件必填 |
| 13 | `timezone` | IANA/明确 UTC offset 或 null | 报表、日界线与时间序列条件必填 |
| 14 | `currency` | ISO 4217 三位码或 null | 金额主张条件必填；不自动换汇 |
| 15 | `unit` | 明确单位字符串或 null | 数值主张条件必填，如 per_unit、count、percent |
| 16 | `tax_basis` | `tax_inclusive, tax_exclusive, not_applicable, unknown` 或 null | 金额/利润主张条件必填；unknown 阻断精确利润 |
| 17 | `attribution_window` | `{click_days,view_days,source}` 或 null | 广告归因主张条件必填 |
| 18 | `coverage` | 0–1 数值 | 可选但建议；缺失时 limitations 必须说明 |
| 19 | `freshness` | `fresh, aging, stale, unknown` | 依据下文规则计算或验证 |
| 20 | `evidence_level` | `E1, E2, E3, E4, E5` | 核心必填；不得高于 source_type 允许上限 |
| 21 | `confidence` | 0–1 数值 | 核心必填；置信度不改变 evidence_level |
| 22 | `limitations` | 字符串数组 | 核心必填；允许空数组，但不确定/估算不得为空 |
| 23 | `conflicting_evidence` | evidence_id 字符串数组 | 可选；冲突存在时必填，禁止静默覆盖 |
| 24 | `status` | `observed, verified, partial, unverified, superseded, rejected` | 核心必填；E5 必须 unverified |
| 25 | `supersedes` | evidence_id 字符串数组 | 可选；替代旧证据时必填且保留旧记录 |

核心必填字段共 11 个：`evidence_id, claim_id, claim, source_type, source_location, marketplace, observed_at, evidence_level, confidence, limitations, status`。

### 条件完整性

- 政策/费率：补 `effective_date, category`（如适用）和明确 Marketplace。
- 金额/利润：补 `currency, unit, tax_basis, time_range`；任一缺失不得给精确结论。
- 广告：补 `entity_type, entity_id, time_range, timezone, currency, attribution_window`。
- 市场指标：补 `time_range, coverage, unit`；第三方估算必须列方法与局限。
- 实体主张：补 `entity_type, entity_id`；父子、ASIN/SKU、Keyword/Search Term/Target 不得混用。

## 5. Freshness 规则

| 来源/主张 | fresh | aging | stale/处理 |
|---|---|---|---|
| 官方政策、平台行为、费用、资格 | 观测 ≤30 天 | 不作为执行依据 | >30 天为 stale；即使 ≤30 天，执行前仍需 live check |
| 授权第一方账号数据 | 观测 ≤7 天且窗口完整 | 8–30 天，仅趋势/历史比较 | >30 天或权限/导出不完整为 stale/partial |
| Amazon 公共市场证据 | ≤30 天 | 31–90 天 | >90 天 stale |
| 可信第三方 | ≤30 天且方法/覆盖完整 | 31–90 天 | >90 天或无方法/日期为 stale/unverified |
| 历史案例/专家经验/用户材料 | 不用于证明“当前” | 可作假设 | 始终不能单独支持当前政策/市场/账号事实 |
| 模型推断 | 不适用 | 不适用 | freshness 为 unknown，status 为 unverified |

时间阈值是默认审计门槛，不是对平台稳定性的保证。类目、风险与具体官方生效日可以要求更短窗口。

## 6. 冲突、缺失与追溯

### 冲突决策

1. 先确认冲突证据是否描述同一 claim、Marketplace、实体、时间、币种、税基、单位和归因窗口。
2. 不同作用域先拆分，不能通过平均值“消除”冲突。
3. 同作用域按“适用性 → 来源权威 → freshness → coverage → 可复算性”比较。
4. 当前官方规则优先于旧政策；当前授权第一方账号事实优先于历史案例；二者不能跨主张互相替代。
5. 仍未解决时填写 `conflicting_evidence`，状态设 `partial` 或 `unverified`；高风险决策直接 `BLOCKED`。
6. 新证据替代旧证据时填写 `supersedes`，旧记录改为 `superseded`，禁止删除审计轨迹。

### 缺失语义

- `null`、缺字段、空导出、无权限、工具失败、字段不适用和数值 0 是六种不同状态。
- 能由用户安全补齐的阻塞输入为 `ASK`；不影响核心结论的缺口为 `DEGRADE` 并标假设；会制造伪精确或安全风险的缺口为 `BLOCK`。
- 未执行测试、未调用工具或未看到账号数据，不得写成 PASS、零值或“当前正常”。

### 追溯链

```text
Evidence
→ Observation
→ Derived Metric
→ Inference
→ Decision
→ Action
→ Expected Effect
→ Verification
→ Rollback
```

- Observation 只陈述直接读到的内容并引用 `evidence_id`。
- Derived Metric 保留公式、输入 ID、单位、币种、税基、时间与归因。
- Inference 明确替代解释、置信度和限制，不伪装成 Fact。
- Decision 记录采用/拒绝的备选项及 Hard Gate。
- Action 在 V1 只能是只读检查或待确认 Diff；外部写操作需要独立授权。
- Expected Effect 必须可测；Verification 给出窗口与断言；Rollback 给出恢复对象和触发条件。

## 7. 隐私与发布边界

- 全局 Skill 不包含私库真实账号结构、人员、客户、供应商、ASIN/SKU、订单、预算、竞价或利润阈值。
- 报告对 ID 做掩码或稳定别名；只有完成任务所必需的局部字段可短暂进入上下文。
- 不输出 Token、Cookie、完整授权链接或未脱敏原始报表。
- Draft、raw、inbox、转写和旧案例只能生成待验证假设或匿名评测，不得直接写成规范。
- 证据不足时降低结论强度，不通过扩大上下文、猜测字段或调用未授权工具弥补。
