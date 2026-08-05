# 问题—方法—证据—动作映射

方法只有在能定位具体失败、产生可审计中间产物并改变决策时才可加载。证据等级 `E1–E5` 见 [evidence-policy.md](evidence-policy.md)；它不等于产品验证强度 `A–D`。

域编号沿用 [domain-map.md](domain-map.md)。生命周期使用 `research / development / pre_launch / launch / growth / mature / decline / recovery`。

## 进入工作流的方法

| 解决的失败模式 | 适用域与生命周期 | 所需输入与证据等级 | 中间产物与决策 | 编码位置 + 常见误用 + 禁用场景 |
|---|---|---|---|---|
| 症状被当作根因 | 全域；全部阶段 | 目标、约束、实体与观测；至少 E4，关键事实按域提高 | 可证伪的基本事实与约束列表；决定继续拆解或 ASK | `SKILL.md`/审计流程；第一性原理不是忽略平台规则；缺可验证事实时禁用结论化表达 |
| 问题重叠、遗漏或粒度混乱 | 全域；全部阶段 | 目标 Skill 契约、文件与失败证据，E4+ | Issue Tree 与不重叠问题集；决定审计顺序 | `SKILL.md` + `assets/audit-report.md`；MECE 只组织问题，不证明因果；单点问题不单独加载 |
| 输入、处理、输出或权限未定义 | 全域；全部阶段 | SKILL/脚本/模板/历史输出，E4+ | IPO/权限契约与缺口；决定 ASK/DEGRADE/BLOCK | `SKILL.md`、`validate_context.py`、契约 eval；误用是只查格式；无法读取真实 Skill 时 BLOCK |
| 多阶段行为无确定失败状态 | 全域；全部阶段 | 触发、状态、转移、错误与授权条件，E4+ | 14 步状态机覆盖表；决定不可达/死路修复 | `SKILL.md`、Golden Case；误用是写流程图不测行为；简单原子检查不加载 |
| 重复质量问题未定位根因 | D02/D05/D10/D12；development–recovery | 多源观测和实体映射，E1–E4 | 5 Whys/Ishikawa 根因树；决定产品/内容/流程修复 | `methodology-map.md` + Golden Case；误用是凭单一评论追问；样本不可追溯时只列假设 |
| 证据昂贵且假设未排序 | D01/D02/D06/D07；research–growth | 假设、先验、可观测信号，E2–E5 | 假设—证据—停止条件表；决定下一最小验证 | `assets/optimization-proposal.md`；误用是把假设写成事实；没有可证伪观测时禁用 |
| 相关性被写成因果或增量 | D06/D07/D10/D12；launch–recovery | 时间序列、干预、混杂因素，优先 E1/E2 | 因果图、替代解释、反事实验证；决定是否允许因果动作 | `methodology-map.md` + 对抗 eval；误用是画图即证明；无对照/自然实验时只能 UNVERIFIED |
| 动作循环无复测与停止条件 | D06/D07/D09/D12；launch–recovery | 基线、动作、窗口、责任与阈值，E1–E4 | OODA/PDCA 日志；决定保持、调整或回滚 | `release-decision.md` + 回归；误用是高频改多个变量；无稳定读数窗口时禁用自动闭环 |
| 系统被次要指标牵引 | D02/D06/D07/D09/D12；全部阶段 | 主链、容量、库存、预算与质量约束，E1–E4 | TOC 约束图；决定先修最窄约束 | `domain-map.md`；误用是把 ACoS 永久当唯一约束；约束无法度量时只标待验证 |
| 多方案收益风险不可比较 | D01/D03/D08/D09；research–mature | 概率/区间、收益、成本与损失，E2–E4 | 期望值区间；决定 Go/No-Go 或试验 | `optimization-proposal.md`；误用是伪精确概率；无合理区间时禁用单点 EV |
| 新证据没有改变置信度 | D01/D02/D07/D11；全部阶段 | 先验假设、证据独立性与等级，E1–E5 | 定性贝叶斯更新日志；决定升级/降级置信度 | `evidence-policy.md`；误用是捏造数值先验；证据高度相关时不得重复加权 |
| 模型/专家置信度与事实强度不匹配 | 全域；全部阶段 | claim、source、coverage、冲突，E1–E5 | 置信度校准表；决定 VERIFIED/PARTIAL/UNVERIFIED | `validate_evidence.py`；误用是高置信替代高等级证据；无验证集时不报校准率 |
| 多属性选择缺透明权重 | D01/D02/D03/D08；research–pre_launch | 决策目标、权重、阈值、证据，E2–E4 | 加权矩阵与敏感性；决定候选排序 | `optimization-proposal.md`；误用是权重掩盖 Hard Gate；合规/安全项禁止加权抵消 |
| 单点假设主导结论 | D01/D03/D07/D08/D09；全部阶段 | 关键变量、范围、口径，E1–E4 | 单变量/多情景敏感性表；决定稳健区间 | `validate_calculations.py` + 报告；误用是无来源上下界；混币种/税基时先 BLOCK |
| 未来需求或成本高度不确定 | D01/D03/D08/D09；research–mature | 低/中/高情景与触发条件，E2–E4 | 情景表和应对门槛；决定分批/延后/停止 | `optimization-proposal.md`；误用是把情景当预测；缺情景依据时禁用概率标签 |
| 严重度、发生率、可探测性未系统化 | D02/D03/D05/D09/D11；development–mature | 失败模式、影响、原因、控制，E1–E4 | FMEA 与优先修复项 | `failure-patterns.md`；误用是评分伪科学；合规红线仍直接 P0 |
| 上线前未想失败与攻击路径 | D05/D06/D07/D11/D12；pre_launch–growth | 目标、权限、外部动作、攻击面，E1–E4 | Pre-mortem/红队场景；决定保护条款与回滚 | `evals/` 对抗用例；误用是泛泛风险清单；不得执行真实破坏动作 |
| 风险只有分数没有门禁 | D02/D03/D05/D11；全部阶段 | 影响、概率、适用规则与证据，E1–E4 | 风险矩阵 + Hard Gate；决定 BLOCK/人工复核 | `scorecard.md`；误用是平均化 P0；高风险政策缺 E1 时必须 BLOCK |
| 选品只看需求 | D01；research | 需求、竞争、成本、合规、供应，E1–E4 | 需求-竞争-利润-风险卡；决定 Go/No-Go | `domain-map.md` + Golden Case；误用是第三方销量当第一方；缺两条关键轴时禁给 Go |
| 阶段未过门就进入下一步 | D01/D02/D06；research–growth | 阶段产物、验收标准、未决风险，E1–E4 | Stage-Gate 表；决定进入、返工、停止 | `SKILL.md`/Golden Case；误用是固定天数代替证据；Hard Gate 未清不得放行 |
| 客户痛点未转产品要求 | D01/D02/D04/D05/D10；research–mature | VOC、场景、属性与可测规格，E2–E4 | JTBD/VOC→Kano→QFD 映射；决定规格和证据优先级 | `domain-map.md`；误用是词频等于重要度；无原始样本与覆盖时只做探索 |
| 卖点与产品证据断裂 | D02/D04/D05/D10；development–mature | 痛点、属性、产品事实、测试证据，E1–E4 | 痛点→属性→卖点→证据链；决定保留/降级/删除宣称 | `entity-model.md` + Listing/视觉 eval；误用是模型补事实；缺证据时禁止强宣称 |
| 搜索词、关键词与意图混淆 | D01/D04/D07；research–growth | Query/Keyword/Search Term、站点、时间，E1–E3 | 意图层级与实体映射；决定内容覆盖或投放审计 | `entity-model.md` + 触发/实体 eval；误用是同文本即同实体；字段语义未知时 BLOCK 精确动作 |
| 广告局部指标掩盖主链 | D06/D07/D12；launch–recovery | Impression/Click/Order、自然销售、利润、库存，E1 | 流量→CTR→CVR→订单→贡献利润漏斗；决定断点修复 | `scorecard.md` + Ads Golden Case；误用是 ACoS 单指标；缺归因或库存时不做扩量 |
| 商品未就绪却投流 | D04/D05/D06/D07/D08/D09；pre_launch–growth | Listing、价格、评论、库存、履约和合规，E1–E3 | Retail Readiness Gate；决定先修复或允许小测 | `domain-map.md` + Hard Gate；误用是用广告弥补根本缺陷；红线未清禁放量 |
| 成本、广告和利润口径断裂 | D03/D07/D08/D12；全部阶段 | 收入、成本、广告、币种、税基、单位，E1–E4 | Landed Cost、贡献毛利、Break-even ACoS/TACoS；决定可承受投放/促销 | `validate_calculations.py`；误用是缺失当零或毛利替代贡献利润；混口径时 BLOCK |
| 补货与现金只看平均销量 | D03/D09/D12；launch–mature | 需求区间、交期、服务水平、在途、现金，E1–E4 | 周转/补货点/安全库存/现金周期；决定补货区间 | `validate_calculations.py` + 库存 Golden Case；误用是固定覆盖天数；无 SKU 映射时禁精确数量 |
| SKU 重要度与波动混为一谈 | D09/D12；growth–mature | SKU 级价值、销量与波动窗口，E1 | ABC-XYZ 矩阵；决定差异化服务水平 | `methodology-map.md`；误用是 Parent ASIN 汇总；数据窗太短时只做临时分层 |
| 报表异常没有稳定基线 | D07/D09/D12；launch–recovery | 同口径时间序列、事件与阈值，E1 | 控制图/基线差异与异常队列；决定调查而非自动归因 | `score_report.py`/Golden Case；误用是季节变化当异常；字段漂移或空导出时先 FAIL 数据质量 |
| 少数问题贡献大但动作无排序 | D02/D07/D09/D10/D12；全部阶段 | 可比分类、影响与覆盖，E1–E4 | Pareto 排序；决定先查高贡献项 | `audit-report.md`；误用是频次等于严重度；类别重叠时先清洗 |
| 政策/IP 风险被业务分数抵消 | D02/D04/D05/D11；全部阶段 | 当前官方政策、授权文件、适用市场，E1 | 合规/IP Gate；决定 BLOCK/专业复核/继续 | `scorecard.md`；误用是历史私库当当前规则；缺官方适用证据时必须 BLOCK |
| 行为质量只由模型自评 | 全域；全部阶段 | 固定输入、期望行为与可执行断言，E4+ | Golden Set 通过率；决定发布结论 | `evals/golden-cases.jsonl`；误用是用同模型改写期望；无行为评测只能 UNVERIFIED |
| 触发边界与修改前后行为漂移 | 全域；全部阶段 | 正/反/边界触发与历史输出，E4+ | Trigger precision/recall 和回归差异；决定修触发或回滚 | `trigger-evals.json`；误用是只有正例；未执行用例不得计通过 |
| Schema、计算或权限接口漂移 | 全域；全部阶段 | 接口字段、有效/无效样例，E4+ | 契约测试结果；决定兼容修复 | `scripts/validate_*.py`；误用是只测 happy path；第三方接口未知时不得猜字段 |
| 正常测试无法发现保护条款缺口 | 全域；全部阶段 | Hard Gates、Prompt Injection、变异输入，E4+ | 对抗/变异结果；决定加强拒绝与降级 | `evals/`；误用是直接攻击真实系统；只在隔离样例上执行 |
| 失败没有稳定类别与回归归属 | 全域；全部阶段 | 历史失败、根因、修复与复测，E4+ | 失败分类与 P0–P3；决定局部补丁或结构调整 | `failure-patterns.md`；误用是一错一类；无法复现时标 UNVERIFIED |
| 高风险判断需人工授权或专业复核 | D03/D07/D09/D11；全部阶段 | 风险、证据缺口、拟议动作与影响对象，E1–E4 | Human-in-the-loop 签核点；决定只读/提案/执行 | `optimization-proposal.md`；误用是把确认当橡皮章；未确认写操作必须 BLOCK |

## 删除或降级的方法

| 方法 | 处理 | 理由 |
|---|---|---|
| Monte Carlo | V1 删除 | 没有经验证的概率分布与相关结构时只会制造伪精确；以敏感性分析和显式情景替代 |
| 独立 SWOT | 删除 | 不能直接绑定实体、证据或动作，容易变成通用框架堆砌；用 Issue Tree + 需求-竞争-利润-风险卡替代 |
| 独立 AIDA | 删除 | 不能覆盖 Amazon 搜索意图、产品事实、证据和合规；内容审计使用意图→事实→证据链 |
| 纯自动加权排名 | 删除 | 权重会掩盖数据缺失和 Hard Gate；加权矩阵只用于门禁之后且必须做敏感性分析 |
| 全量复杂贝叶斯模型 | V1 删除 | 缺可靠先验、似然和校准集；仅保留可审计的定性证据更新 |
| 无基线机器学习异常检测 | 删除 | 无法区分季节、字段漂移和真实异常；先用同口径基线/控制图 |
| 独立 Kano 或 QFD | 合并 | 单独使用会让 VOC、规格和证据断链；只在 JTBD/VOC→Kano→QFD 工作链中加载 |
| 独立 OODA 或 PDCA | 合并 | 两者在本 Skill 中承担同一“动作—复测—回滚”职责，保持一个轻量循环即可 |

## 选择规则

1. 从已证实失败模式出发，每个问题默认选择一个主方法，必要时加一个验证方法。
2. 方法输入不满足证据门槛时，先 `ASK` 或 `DEGRADE`；不得通过加载更多方法掩盖数据缺失。
3. Hard Gate 先于任何加权、期望值或优化方法。
4. 每个方法必须产出可保存的中间产物、明确决策和回归断言，否则从本次审计上下文卸载。
