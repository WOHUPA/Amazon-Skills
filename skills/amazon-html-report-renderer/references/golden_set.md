# Golden Set

本清单给通用优化器提供稳定的案例发现入口；真实 fixture、断言和逐案例回执仍以 `tests/fixtures/`、`evals/golden-cases.json` 与 `evals/golden-receipts.jsonl` 为准。

通过标准：案例 1 至 6 必须全部自动执行且 6/6 PASS；任一案例失败或未执行即为 FAIL。

所有案例共用的“回到顶部”验收：页面存在且仅存在一个 `id="report-top"`，控件为原生 `<a href="#report-top">`；禁用 JavaScript 仍可用，启用 JavaScript 时由 `IntersectionObserver` 渐进显隐；Tab 可达且焦点清楚，reduced-motion 下无强制平滑滚动，打印版不显示控件。任一条件缺失即使业务组件正确也判该案例 FAIL。

所有表格还须验收：业务数据表、图表数据摘要、雷达对比表、关键词表与来源附录均按整列表头和全部已格式化可见单元格审核；中文/Unicode 全角计 1 个视觉单位，半角计 0.5，组合符与控制字符计 0，隐藏来源说明不计入。整列最大值 `≤10` 保持紧凑，`>10` 按 `min(48, max(16, 4 × ceil((最大视觉单位 + 2) / 4)))em` 分档加宽，超过 48em 容量后在列内换行且原文完整。4/5/14 列布局保持契约；横向滚动只发生在键盘可达的表格容器，页面根级无横向溢出，打印端取消动态最小列宽并恢复换行。

## 案例 1 广告表现报告

- fixture：`tests/fixtures/ads-performance.json`
- 布局：performance，REAL + COMPLETE。
- 必须保留负数、真实零、来源引用，并渲染 KPI、分布/进度、折线和 TOP N 表格。
- 必须核对回到顶部不会遮挡 KPI、图表、宽表横向滚动区域或主题控件。

## 案例 2 运营周报

- fixture：`tests/fixtures/weekly-performance.json`
- 布局：performance，REAL + PARTIAL。
- 必须明确显示缺失、冲突、限制与 PARTIAL，禁止缺失补零。
- 必须核对 PARTIAL 长页面的回到顶部原生锚点、滚动后显现、键盘焦点与打印隐藏。

## 案例 3 VOC 洞察

- fixture：`tests/fixtures/voc-insight.json`
- 布局：insight，REAL + COMPLETE。
- 必须转义原始引文，并渲染关键词、数据表和带 alt 的合规图片证据组件。
- 必须核对回到顶部不会覆盖引文、Tag Cloud、宽表或图片证据，禁用 JavaScript 仍可导航；VOC 内容密集表须同时通过短字段单行与长证据列换行验收。

## 案例 4 MCP 横向对比

- fixture：`tests/fixtures/mcp-insight.json`
- 布局：insight，DEMO + COMPLETE。
- 必须持续显示 DEMO，渲染雷达、Comparison Grid 与 Evidence Compare，不得把演示结论当真实业务结论。
- 必须核对 DEMO 标识与回到顶部同时保持可读，控件不遮挡 Evidence Compare，reduced-motion 生效。

## 案例 5 日常运营检查

- fixture：`tests/fixtures/operations-operations.json`
- 布局：operations，REAL + COMPLETE。
- 必须渲染叙事、执行清单、SWOT、总结建议，并保持唯一 H1、无空组件及打印样式。
- 必须核对回到顶部在清单键盘导航中保持正常 Tab 顺序、焦点可见，且打印完全隐藏。

## 案例 6 知识库阻塞页

- fixture：`tests/fixtures/knowledge-knowledge.json`
- 布局：knowledge，REAL + BLOCKED。
- 只能输出完整数据质量说明、限制和来源，不得渲染正常看板或伪造数值。
- BLOCKED 页仍必须提供可用的原生回到顶部链接；不得因跳过正常组件而漏掉控件或唯一 `#report-top` 目标。
