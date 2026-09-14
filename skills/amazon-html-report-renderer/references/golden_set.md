# Golden Set

## 六组 Golden 案例

| Case | 布局族 | 状态 | 断言要点 |
| --- | --- | --- | --- |
| G-ADS | performance | COMPLETE | 自包含、负值/真实零保留、可访问图表、回到顶部 |
| G-WEEKLY | performance | PARTIAL | 部分可见、限制可见、null 保留、来源冲突可见 |
| G-VOC | insight | COMPLETE | 引号转义、内嵌图片、alt、话题表 |
| G-MCP | insight | COMPLETE | DEMO 标识、雷达摘要、对比网格、证据标签 |
| G-OPERATIONS | operations | COMPLETE | 清单状态、单 H1、无空组件、打印样式 |
| G-KNOWLEDGE | knowledge | BLOCKED | 数据质量页、无正常看板、限制可见 |

## 回归入口

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/run_golden_fixtures.py --format json
python -m evals.trigger_evals
python scripts/sync_to_codex.py --dry-run
node tests/run_visual_qa.mjs
```

## 验收标准

- 40/40 单元与集成测试通过。
- 6/6 Golden PASS，无未执行案例。
- 20/20 Trigger eval 符合预期。
- 40/40 Chrome 视觉 QA 场景通过（四布局 × 3 视口 × 浅/深/打印 + 移动端无 JS）。
- 每次行为性修改后对比改前改后；新增失败模式写入 `SKILL.patch.md`。
