# 建构决策

## 建构基线

- 建构日期：2026-08-01（Asia/Shanghai）。
- 输入质量：A。用户提供了稳定任务、完整文件树、输入输出、边界、公式、评测与验收要求，Q1–Q5 已由建构提示词预填，不再补问。
- 建构提示词：D:/codex/亚马逊/亚马逊全流程skill/amazon-skill-optimizer-codex建构提示词.md。
- 提示词 SHA-256：2200D052BC8B93799E24E3F25D7629D8DB7D28777CF1F0E2DCC542172E4C11EB。
- 安装源：C:/Users/quyib/.codex/skills/amazon-skill-optimizer。
- 旧草稿 C:/Users/quyib/Documents/Codex/2026-08-01/new-chat/work/amazon-skill-optimizer 不复制、不覆盖，也不作为实现来源。

## 架构

采用唯一锁定架构：

通用 skill-optimizer 内核（引用，不复制）+ Amazon Domain Pack + 独立入口 amazon-skill-optimizer。

通用内核从 $CODEX_HOME/skills/skill-optimizer 解析，备用为 ~/.codex/skills/skill-optimizer。只有 frontmatter 名称正确且 scripts/health_check.py、scripts/verify.py 同时存在才算有效。GBRAIN_SKILLS_DIR 中的同名 Skill 不参与解析，避免把 GBrain 自带能力误当 Codex 核心。

若通用内核缺席，入口只加载 core-fallback-checklist.md，并在报告中标 CORE=FALLBACK；不复制核心正文，不伪装完整验证。

## GBrain 取证快照

- Brain：GBrain 0.42.64.0，PGlite，325 页、6813 chunks。
- amazon-general：30/30 页，last_sync_at=2026-07-26T07:49:31.976Z，last_commit=95547e57ca0dcbd8482a3302cdae061f7d819c2e，clone_state=corrupted。
- seller-brain：232/232 页，last_sync_at=2026-07-28T13:20:58.239Z，last_commit=568760d44f647bdb3df9286ed74a2277a3831541，clone_state=missing。
- 262 页均已读取；建构期覆盖账本保存在任务工作区 work/gbrain-coverage-ledger.csv，不作为运行依赖。
- 覆盖分类：75 页抽象纳入，1 页只作来源证据，31 页仅保留私有运行时模式，155 页不进入规范性知识。
- clone_state 是本次观察到的 Source 健康状态。数据库内容仍可读，本任务不修复、同步或改写 Source。

## 纳入规则

amazon-general 用于跨店铺稳定框架、来源治理和业务主链。主要取证页包括：

- concepts/市场需求：需求、行为、竞争、门槛和单位经济交叉验证。
- concepts/产品定义：VOC 到属性、规格、测试和宣称证据。
- concepts/listing内容：是什么、是否适合、差异和证据。
- concepts/广告流量：广告是放大器，不能脱离零售准备度、利润和库存。
- concepts/定价利润：净收入、成本、退货、广告、现金和敏感性。
- concepts/库存供应：需求区间、完整交期、服务水平、库龄和现金。
- concepts/评论口碑：评论是产品与体验结果，必须合规处理。
- concepts/数据接口：来源、字段、刷新、延迟、权限、站点、时区和归因。
- concepts/核心原则、concepts/经营底盘：生命周期、约束与经营闭环。
- governance/来源边界：S0–S5、实时核验与隐私边界。

seller-brain 只抽象稳定 SOP、实体混淆、失败模式和证据边界。主要取证页包括：

- sops/产品开发：类目洞察到测试迭代的七阶段链路。
- sops/VOC入库：脱敏、聚类、根因与交叉验证。
- keywords/流量词与投放词：Keyword/Target 与 Search Term 的输入—结果边界。
- campaigns/搜索词复盘、campaigns/广告漏斗：归因、生命周期、利润与库存约束。
- campaigns/SC账户：广告层级的业务观察。
- governance/召回策略：raw → digest → 人工确认 → formal。
- schema：Fact、Analysis、Seller Fit 分离。

每个 Domain Pack 在 domain-map.md 标记：

- stable：可以写入跨店铺稳定规则。
- private-runtime：只能运行时从私有事实补充。
- official-live：必须在执行当日查适用站点官方来源。

## Domain Pack 引用清单

`domain-map.md` 共使用 25 次 GBrain 正式页引用，去重后为以下 23 页；全部存在于 262 页覆盖账本中：

- amazon-general::concepts/listing内容
- amazon-general::concepts/产品定义
- amazon-general::concepts/定价利润
- amazon-general::concepts/广告流量
- amazon-general::concepts/合规规则
- amazon-general::concepts/经营底盘
- amazon-general::concepts/经营节奏
- amazon-general::concepts/库存供应
- amazon-general::concepts/评论口碑
- amazon-general::concepts/市场需求
- amazon-general::concepts/数据接口
- amazon-general::concepts/质量体验
- seller-brain::campaigns/放量成本
- seller-brain::campaigns/数据诊断
- seller-brain::decisions/回报周期
- seller-brain::governance/合规红线
- seller-brain::keywords/关键词分层
- seller-brain::products/选品方法
- seller-brain::sops/voc入库
- seller-brain::sops/产品开发
- seller-brain::sources/digests/亚马逊广告摘要
- seller-brain::supply-constraints/供应链降本
- seller-brain::supply-constraints/库存放量

## 排除与脱敏

以下内容不进入全局 Skill：

- seller-brain/sources/raw、inbox、录音转写、会议原文、完整课程材料。
- 真实店铺、账户、活动、ASIN、SKU、客户、供应商、精确成本、订单、库存和广告数值。
- Token、Cookie、密钥、授权链接、个人信息和商业敏感数据。
- 固定竞价倍率、点击淘汰线、断货恢复天数、资金规模、利润率或流量比例。
- 可能变化的政策、费用、促销资格、广告机制、API 字段、账号健康、Rufus/COSMO 断言。

这些材料只用于匿名失败模式、Golden Case 或说明运行时需补什么；不得冒充通用规则。

## 证据语义

不把以下四套概念压成同一个等级：

1. S0–S5：来源权威。
2. A–D：产品需求验证强度或输入质量。
3. raw → digest → 人工确认 → formal：知识成熟度。
4. Fact / Analysis / Seller Fit：主张性质。

Evidence Schema 保留提示词规定的 25 字段。evidence_level 表示本 Skill 的证据层级映射，confidence 与 limitations 表示不确定性，status 表示记录状态；映射必须保留原始来源语义，不能把私有摘要升级成官方证据。

## 实体与时效

Keyword、Target、Search Term 的差异由 seller-brain 稳定页支持。Marketplace → Profile 和 Parent ASIN → Child ASIN → SKU → FNSKU → Offer 的精确定义需要官方定义复核，因此 entity-model.md 将其标为协议模型与待 live-check 项，不伪称来自私库。

政策、费用、促销资格、广告产品行为、账号健康、站点法规、Rufus/COSMO 和归因机制必须运行时查当前官方来源。历史知识只能形成检查问题，不能代替当前事实。

## 数值口径

- Landed Cost 仅汇总调用方明确提供的采购、包装、头程、关税、保险、检测、预处理和其他落地分项。
- 贡献毛利从净收入扣除落地成本、平台及履约、仓储、促销、退货损耗、其他变动成本和广告。
- Break-even ACoS 使用广告前贡献毛利率，但明确不覆盖固定成本、资金占用、安全边际和增量不确定性。
- ACoS、TACoS、CTR、CVR 与库存周转采用脚本中声明的公式。
- 不自动换汇；缺失成本不置零；零分母、币种、税基、单位、粒度、时间范围或归因冲突均失败。
- 库存周转采用标准会计口径，不声称来自 seller-brain。

## 评分与发布

13 项权重总计 100：触发9、边界9、Amazon正确性12、业务链8、方法8、证据10、数值10、工具降级7、安全10、输出6、缺失冲突5、上下文3、测试维护3。

四轴不压成单一总分。Hard Gate 不得被高分抵消；发布状态按 scorecard.md 的 READY、CONDITIONAL、REJECT、BLOCKED 映射到 PASS、PASS_WITH_LIMITS、REJECT、BLOCKED。

## 运行依赖与版本边界

- GBrain 是本次建构的知识与证据来源，不是 amazon-skill-optimizer 的运行依赖。
- 用户明确要求结合私有知识时，可以另行只读查询 GBrain；没有 GBrain 也能审计本地 Skill。
- agents/openai.yaml 不声明 GBrain MCP。
- V1：只读审计、报告和 Diff 建议；目标 Skill 修改需单独明确授权。
- V2 候选：多站点规则库、真实目标 Skill 补丁沉淀、自动 Diff 应用；均不在本次范围。
- 精确文件树不含 README、CHANGELOG 或 SKILL.patch.md；首个真实失败发生并获授权沉淀后再评估 patch。
