# Report Editions

## 报告版本

| 版本 | 名称 | 字段覆盖 |
| --- | --- | --- |
| BASIC | 基础版 | 仅 basic_required 字段 |
| ENHANCED_PARTIAL | 部分增强 | basic_required + enhancement_global_required |
| ENHANCED_FULL | 完整增强 | 全部字段，含 module_required 与 full_required |

## 字段级别

- `basic_required`：基础必填字段。
- `enhancement_global_required`：增强版全局必填。
- `module_required`：模块级必填（如 VOC 模块、库存模块）。
- `full_required`：完整增强必填。
- `display_optional`：仅展示可选字段。

## 语义

- 渲染器保留上游 `report_edition`，不自行升级或降级。
- 缺失字段按 `value_status` 语义展示，禁止转成 0 或默认值。
- `report_edition_reason` 说明为何采用当前版本，必须原样展示。
