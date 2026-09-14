# `amazon-html-report/v1` 报告协议

## 协议边界

协议描述“上游已确认的报告事实如何交给渲染器”。它不是取数协议、分析协议或任意内容注入接口。输入必须通过 `assets/report-spec.schema.json`；未知顶层字段、未知组件和未知对象属性默认拒绝。

顶层固定为：

```text
protocol
report
sources[]
metrics[]
datasets[]
sections[]
limitations[]
render
```

## 报告头

`report` 至少声明：

- 稳定 `report_id`、`report_type`、标题、`locale`、Marketplace、周期、时区和币种。
- `report_version`、`data_mode=REAL|DEMO`、`status=COMPLETE|PARTIAL|BLOCKED`。
- `report_edition=BASIC|ENHANCED_PARTIAL|ENHANCED_FULL` 及非空版本原因。
- `data_quality=A|B|C|D` 与 `evidence_strength=strong|medium|weak|conflict|none`。二者互不替代。
- `privacy.redaction_status=REDACTED|PUBLIC_ONLY|NOT_APPLICABLE` 与 `contains_private_identifiers=false`。

`period` 至少包含人类可读 `label`；日期范围和 `data_as_of` 有事实依据时再填。缺少日期不得制造默认日期。

## 来源

每个 `source_id` 在文件内唯一。来源必须分别表达：

- `source_type`：`official_policy`、`authorized_first_party`、`amazon_public`、`trusted_third_party`、`historical_case`、`expert_experience`、`user_provided` 或 `model_inference`。
- `provider_family`：底层提供方家族，用于识别伪多源；多个包装不自动成为多个独立来源。
- `role`：`PRIMARY|VERIFICATION|FALLBACK|MANUAL`。
- `status`：`AVAILABLE|PARTIAL|UNAVAILABLE|CONFLICT|NOT_APPLICABLE`。
- `source_tier=S0..S5`、`data_quality_grade=A..D`、`behavior_evidence_tier=STATIC|UNIT|INTEGRATION|LIVE|UNVERIFIED`。
- 实际观测时间、可选数据截至时间、作用域和局限。

渲染器只展示并校验这些声明，不判断来源当前是否可用。私有一方来源不等于允许展示原始账号、店铺或 Campaign 标识。

## 指标与派生值

`metrics[]` 是 KPI 等组件引用的单一指标目录。每个指标必须带稳定 `metric_id`、显示名、值、值状态、单位、字段等级与 `source_refs`。

值状态固定为：

```text
OBSERVED | DERIVED | MISSING | CONFLICT | NO_ROW | NO_ACCESS |
COLLECTION_FAILURE | NOT_APPLICABLE | NO_BASELINE
```

- 真实零写为 `value: 0` 且状态为 `OBSERVED` 或经审计的 `DERIVED`，不使用缺失状态。
- 非事实值写 `value: null` 与准确状态；不得补零。
- 数值必须有非空 `source_refs`，且所有引用必须存在。
- `DERIVED` 必须提供 `derivation.formula`、`input_refs` 与 `calculation_receipt`。渲染器不执行公式，只验证声明完整并展示必要口径。
- `field_level` 使用五级字段；详见 [report-editions.md](report-editions.md)。

## 数据集

图表与表格只通过 `dataset_id` 引用统一数据集，不在组件内复制另一套数值。

```json
{
  "dataset_id": "trend-sales",
  "label": "销售趋势",
  "kind": "series",
  "source_refs": ["source-main"],
  "columns": [
    {"column_id": "date", "label": "日期", "data_type": "date"},
    {"column_id": "sales", "label": "销售额", "data_type": "number", "unit": "USD"}
  ],
  "rows": [
    {
      "row_id": "row-1",
      "values": [
        {"column_id": "date", "value": "2026-08-01", "status": "OBSERVED", "source_refs": ["source-main"]},
        {"column_id": "sales", "value": 0, "status": "OBSERVED", "source_refs": ["source-main"]}
      ]
    }
  ]
}
```

每行必须恰好覆盖全部 column，不能重复或遗漏 `column_id`。数值 cell 必须有非空来源；推荐所有 cell 都带来源。`null` 必须保留状态。图表不得把缺失点连成真实数据。

## 章节、限制与渲染

- `sections[]` 按顺序定义章节，每个 section 有唯一 ID、标题和 `components[]`。
- 组件公共字段为 `type`、可选 `component_id` 与可选 `title`；缺少 `component_id` 时渲染器按 `section_id + 顺序号` 生成确定性 ID，显式 ID 必须全局唯一。专属字段见 [component-contracts.md](component-contracts.md)。
- `limitations[]` 以唯一 ID、详情、`INFO|WARNING|ERROR|BLOCKER` 严重度和可选来源/影响表达限制。
- `render.family=auto|performance|insight|operations|knowledge`，`theme=system|light|dark`，`show_toc` 为布尔值。
- `report_type=custom` 时禁止 `family=auto`。

## 跨字段校验

Schema 负责结构；渲染器还必须确定性检查：

1. 所有 ID 唯一，组件对 metric/dataset/source 的引用存在。
2. 每个 dataset row 恰好覆盖声明 columns。
3. 数值与状态一致，缺失不是零；派生值收据完整。
4. `BLOCKED` 不进入正常 dashboard 版式；`DEMO` 标识持续存在。
5. 没有有效数据的组件被跳过并记录 warning，而不是生成空壳。
6. 图片、安全、隐私、外部资源和输出路径满足 fail-close 规则。
