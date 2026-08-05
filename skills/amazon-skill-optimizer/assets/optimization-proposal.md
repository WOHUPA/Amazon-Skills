# Amazon Skill 优化提案

## 签核状态

- 目标 Skill：{{target_skill_name}}
- 提案版本：{{proposal_version}}
- 当前状态：待用户确认
- 允许修改范围：{{approved_scope_or_none}}
- 明确排除：{{excluded_scope}}

在用户明确批准目标、文件和范围前，本提案只读，不执行 Diff。

## 提案项

### {{proposal_id}} · {{proposal_title}}

1. 问题：{{problem}}
2. 证据等级：{{evidence_grade}}
3. 影响：{{impact}}
4. 改动对象：{{change_target}}
5. 具体动作：{{action}}
6. 预期收益：{{expected_benefit}}
7. 验收方式：{{acceptance}}
8. 风险：{{risk}}
9. 回滚：{{rollback}}

## Diff 摘要

| 文件 | 动作 | 行为变化 | 是否获批 |
|---|---|---|---|
| {{file}} | {{change_type}} | {{behavior_change}} | {{approved}} |

## 可审阅 Diff

{{unified_diff}}

## 回归计划

- 正例：{{positive_tests}}
- 反例：{{negative_tests}}
- 边界例：{{boundary_tests}}
- 历史回归：{{historical_tests}}
- Hard Gate：{{hard_gate_tests}}

## 授权记录

- 用户原话：{{approval_quote}}
- 授权时间：{{approval_time}}
- 授权范围：{{approval_scope}}
- 未授权范围：{{unapproved_scope}}
