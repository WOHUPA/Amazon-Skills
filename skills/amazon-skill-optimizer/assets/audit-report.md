# Amazon Skill 审计报告

## 结论摘要

- 目标 Skill：{{target_skill_name}}
- 唯一生效源：{{effective_source_path}}
- 输入质量：{{data_quality_grade}}
- Core：{{core_mode}}
- 发布结论：{{release_status}}
- 总分：{{total_score}}/100
- Hard Gate：{{hard_gate_count}}
- 主要风险：{{top_risks}}

## 四轴

| 轴 | 得分或状态 | 覆盖 | 说明 |
|---|---:|---:|---|
| CoreHealth | {{core_health}} | {{core_coverage}} | {{core_note}} |
| AmazonFitness | {{amazon_fitness}} | {{amazon_coverage}} | {{amazon_note}} |
| BehavioralEval | {{behavioral_eval}} | {{behavioral_coverage}} | {{behavioral_note}} |
| EvalCoverage | {{eval_coverage}} | {{executed}}/{{planned}} | {{coverage_note}} |

## AmazonContext 快照

{{amazon_context_json}}

### 缺失、冲突与假设

- ASK：{{ask_items}}
- DEGRADE：{{degrade_items}}
- BLOCK：{{block_items}}
- 假设：{{assumptions}}

## 生效源与文件证据

- 同名副本：{{duplicate_sources}}
- 文件清单与哈希：{{file_inventory}}
- 未读取项：{{unread_items}}

## 问题清单

| ID | 严重度 | 问题 | 证据等级 | 证据位置 | 影响 | 建议动作 | 风险 |
|---|---|---|---|---|---|---|---|
| {{finding_id}} | {{severity}} | {{problem}} | {{evidence_grade}} | {{evidence_location}} | {{impact}} | {{action}} | {{risk}} |

## Hard Gate 检查

| Gate | 状态 | 证据 | 处理 |
|---|---|---|---|
| {{gate_id}} | {{gate_status}} | {{gate_evidence}} | {{gate_action}} |

## 100 分评分明细

| 评分项 | 权重 | 状态 | 得分 | 证据 |
|---|---:|---|---:|---|
| {{score_item}} | {{weight}} | {{status}} | {{score}} | {{evidence}} |

## 安全与稳定性

- 写操作边界：{{write_boundary}}
- 敏感信息：{{sensitive_data_result}}
- 私有数据降级：{{private_data_fallback_result}}
- 子 agent 判断：{{subagent_decision}}
- 故障与恢复：{{recovery_result}}

## 已运行验证

{{executed_checks}}

## 未验证项与限制

{{unverified_items}}

## 证据链

Evidence → Observation → Derived Metric → Inference → Decision → Action → Expected Effect → Verification → Rollback

{{traceability_rows}}
