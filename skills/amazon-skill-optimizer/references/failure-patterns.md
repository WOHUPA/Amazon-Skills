# Amazon Skill 领域失败模式

本文件只描述可被证据识别、可映射到修复与回归的 15 个模式。命中 Hard Gate 时按 `references/scorecard.md` 直接升级为 P0；否则根据核心输出影响判为 P1–P3。

| ID | 失败模式与识别特征 | 检测方法 | 对应修复动作 | 关联评分项 |
| --- | --- | --- | --- | --- |
| `FP-01` | 只堆 AIDA、SWOT 等通用框架；没有 Amazon 实体、站点、输入、决策链或验收产物 | 人工沿主流程追踪“输入→中间产物→决策→输出”；检索框架名是否只有定义无调用 | 删除无法进入工作流的框架；把保留方法绑定到失败模式、证据要求和决策动作 | `amazon_domain_correctness`、`method_decision_fit`、`output_actionability` |
| `FP-02` | references 很多，但主流程没有条件读取规则，或不论任务都全量加载 | 脚本比对 reference 文件与 `SKILL.md` 路由链接；人工验证一次只加载 1–2 个域 | 在入口增加“域→文件/章节→加载条件”映射；删除孤儿引用并补路由回归 | `tool_routing_degradation`、`context_efficiency`、`testing_maintainability` |
| `FP-03` | 美国站规则、词法、税费或资格被直接套到欧盟、日本等站点 | 检查 AmazonContext marketplace；对每条规则核对站点、locale、有效期和来源 | 将规则限定到证据支持的站点；跨站点时 ASK 或 BLOCK，并增加泄漏反例 | `amazon_domain_correctness`、`missing_conflict_handling`、`safety_compliance` |
| `FP-04` | 使用过期政策、费用、广告规则，未标 observed/effective date 或适用范围 | `validate_evidence.py` 检查 freshness；人工对执行型规则做当日官方核验 | 更新官方证据；保留旧规则为历史并标 superseded；无法核验时输出 UNVERIFIED/BLOCKED | `data_evidence_quality`、`amazon_domain_correctness`、`safety_compliance` |
| `FP-05` | 第三方估算缺来源、日期、置信度，或被标成官方/第一方 | 校验 `source_type/evidence_level/source_location/observed_at/confidence`；抽查原始来源 | 降级证据等级，补限制和交叉验证；不得据此做高风险精确结论 | `data_evidence_quality`、`missing_conflict_handling` |
| `FP-06` | 缺数据却编造销量、搜索量、利润率、转化率或店铺状态 | 对每个数字追溯 Evidence→Derived Metric；用缺字段 fixture 验证是否拒绝伪造 | 改为 ASK/DEGRADE/BLOCK；缺失值保持缺失，输出范围或待验证项 | `data_evidence_quality`、`numerical_correctness`、`missing_conflict_handling` |
| `FP-07` | 只润色文案或格式，没有重建触发、IPO、权限与核心结果契约 | 将变更 Diff 与审计清单比对；检查是否有触发/输入/输出/失败状态证据 | 先完成契约审计，再决定局部补丁、结构调整或重写；补契约回归 | `boundary_input_contract`、`trigger_accuracy`、`output_actionability` |
| `FP-08` | 用模型自评分数代替 Golden Set，没有输入 fixture、断言或实际输出 | 检查是否存在可执行案例、原始输出与逐条断言；拒绝仅有“自评通过” | 建立正例、反例、边界例和历史回归；机器断言与人工评审分开记录 | `testing_maintainability`、`output_actionability` |
| `FP-09` | 多个 Amazon Skill 都使用“分析/优化亚马逊”等模糊触发词，无法区分业务执行与 Skill 审计 | 运行正反触发集并对同名/相邻 description 做冲突审计 | 将触发锚定为“审计的对象是另一个 Amazon Skill”，补不触发业务请求样例 | `trigger_accuracy`、`boundary_input_contract` |
| `FP-10` | 全部知识塞入 `SKILL.md`，正文臃肿且无按需加载 | 统计正文行数/字符数、重复内容和无条件加载资源；观察上下文成本 | 正文只留入口与状态机；本体、方法、证据、评分和案例下沉 references/evals | `context_efficiency`、`testing_maintainability` |
| `FP-11` | 选品只看需求或竞争，不检查单位经济、供应交付、合规与现金约束 | 用选品 Golden Case 检查主链与证据缺口；核对是否出现伪精确利润 | 增加需求×竞争×利润×风险交叉验证，缺关键成本或合规证据时阻断结论 | `business_chain_completeness`、`numerical_correctness`、`safety_compliance` |
| `FP-12` | 广告只看 ACoS，不看贡献利润、TACoS、生命周期、库存、价格、评论或归因窗口 | 检查输入和计算字段；复算广告指标并验证窗口/币种/税基一致性 | 将广告放回零售就绪与利润主链；分层诊断并禁止未经授权调预算/出价 | `business_chain_completeness`、`numerical_correctness`、`safety_compliance` |
| `FP-13` | Listing 堆词损害可读性，卖点无规格/VOC/测试证据，或出现不合规宣称 | 人工核对搜索意图、自然表达与证据链；对主张做 claim-evidence 覆盖检查 | 先锁定产品、受众和意图，再写“差异→证据→适用边界”；删除无证据宣称 | `amazon_domain_correctness`、`data_evidence_quality`、`output_actionability` |
| `FP-14` | 单一类目经验被当作跨类目/跨站点规则；适用范围与例外缺失 | 构造另一 marketplace/category 的变异案例；检查输出是否静默复用旧规则 | 将经验标成 context-bound heuristic；按站点/类目证据重新验证，否则 DEGRADE/BLOCK | `amazon_domain_correctness`、`method_decision_fit`、`missing_conflict_handling` |
| `FP-15` | 为过测试删除失败用例、放宽断言、吞异常，或只跑新用例不跑历史回归 | 比较修改前后 eval 清单、断言与退出码；检查异常处理和基线差异 | 恢复原断言与案例；修复根因；同批运行正反边界与历史用例并记录 regression rate | `testing_maintainability`、`safety_compliance` |

## 记录格式

每次命中记录：`pattern_id → 证据位置 → 可信度 → 严重度 → 受影响评分项 → 修复动作 → 回归 case id`。同一证据可命中多个模式，但不得重复计算同一业务影响来抬高问题数量。
