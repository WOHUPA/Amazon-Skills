# Amazon Skill 发布结论

## 结论

{{PASS_OR_PASS_WITH_LIMITS_OR_REJECT_OR_BLOCKED}}

- 目标 Skill：{{target_skill_name}}
- 版本：{{target_version}}
- 审计时间：{{audited_at}}
- Core：{{core_mode}}
- 总分：{{total_score}}/100
- CoreHealth：{{core_health}}
- AmazonFitness：{{amazon_fitness}}
- BehavioralEval：{{behavioral_eval}}
- EvalCoverage：{{eval_coverage}}
- Hard Gate：{{hard_gate_count}}

## 判定依据

{{decision_basis}}

## 回归结果

| 测试组 | 通过 | 失败 | 跳过 | 结论 |
|---|---:|---:|---:|---|
| 触发 | {{trigger_pass}} | {{trigger_fail}} | {{trigger_skip}} | {{trigger_result}} |
| 契约 | {{contract_pass}} | {{contract_fail}} | {{contract_skip}} | {{contract_result}} |
| 数值 | {{numeric_pass}} | {{numeric_fail}} | {{numeric_skip}} | {{numeric_result}} |
| 安全 | {{safety_pass}} | {{safety_fail}} | {{safety_skip}} | {{safety_result}} |
| Golden Set | {{golden_pass}} | {{golden_fail}} | {{golden_skip}} | {{golden_result}} |

## 修改与版本记录

{{change_log}}

## 限制和遗留风险

{{known_limits}}

## 回滚方法

{{rollback_steps}}

## 后续条件

{{next_conditions}}
