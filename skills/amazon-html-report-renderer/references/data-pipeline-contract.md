# 数据管道与交接契约

## 适用范围

本 Skill 不取数、不缓存业务事实、不合并来源，也不计算业务指标，但会消费上游 JSON 并写出 HTML 与回执，因此 DataPipelineContract 适用于“结构化 spec → HTML/receipt”产物交接。

机器可读目录位于 `assets/data-pipeline-contract.json`，遵循 Amazon Skill Optimizer 的 vendor-neutral `schema_version=1.2`。该 JSON 通过结构校验只表示“声明形状可解析”，不等于运行实现已验证；发布结论仍要逐项核对下表和真实测试。Renderer-owned business Metric Contract 为 N/A；这不免除对上游 `metrics[]`、`source_refs` 与 `derivation` 收据的输入验证。

## Catalog 字段到实现的映射

Optimizer 的通用 catalog 同时覆盖抓取、增量、合并和修订型管道，而本 Skill 只消费一个不可变 spec 并产生本地文件。不能生搬字段或把 N/A 伪装为已实现。

| Catalog 概念字段 | 本 Skill 实际来源/字段 | 状态与边界 |
|---|---|---|
| `canonical_input_hash` | receipt `input_semantic_hash` | 运行时重算规范化 spec 的 SHA-256；必须由测试验证 |
| `source_artifact_hash` | receipt `source_spec_raw_hash` | 对输入文件原始 bytes 计算 SHA-256；与语义哈希分开 |
| `transform_version` | receipt `template_version` | 运行时字段；模板变化必须改变版本 |
| `plan_fingerprint` | receipt `render_plan_fingerprint` | 绑定输入语义、模板版本和 resolved family |
| `state_hash` | receipt `render_state_hash` | 绑定语义输入、计划与 HTML 状态，不等同于业务状态 |
| HTML artifact hash | receipt `html_hash` | 对提交 HTML bytes 重算；提交后读回核对 |
| `manifest_hash` | receipt `manifest_hash` | 对不含自身 hash 的核心 manifest 字段计算，避免自引用 |
| 完整 receipt 文件 hash | Golden runner `renderer_receipt_hash` | 由下游对完整 receipt bytes 外部计算，不要求嵌入 receipt |
| `validated_fields` | receipt `validation` | 记录实际执行的 Schema、安全、离线与产物检查，不得写未运行检查 |
| `report_id` / `declared_period` | 输入 `report.report_id` / `report.period` | 输入身份与展示范围；不证明事实覆盖完整 |
| `scope_fingerprint` | 由 report type、Marketplace、period 的规范化值参与 `input_semantic_hash` | v1 不另发独立 scope hash；不得把人类可读 alias 当身份 |
| `provider_family` | 输入 `sources[].provider_family` | 输入声明；不复制到 receipt，不自动证明来源独立 |
| `data_cutoff_at` / `source_watermark_at` | receipt `data_as_of` / `cutoff`，来源为 report period 与 sources | 上游事实时点；渲染运行时间不能替代 |
| `render_run_date` | receipt 的尝试元数据（若实现提供） | 必须排除在语义 HTML/hash 之外；未提供时 N/A |
| `base_state_hash` / merge | N/A | v1 不合并业务状态；默认拒绝覆盖，`--overwrite` 是显式文件替换门，不得宣称业务 CAS |
| cursor / late arrival / revision chain | N/A | v1 不增量取数、不维护历史修订；新 spec 作为新输入重新渲染 |

若真实 receipt 或脚本与上表不一致，以实现与逐案例证据为准，并在发布前修正文档或实现。禁止只凭 catalog validator PASS 标记 DataPipelineContract 已完全实现。

## 身份与血缘

- 输入语义身份由规范化 JSON 的 SHA-256 决定；对象键排序、稳定序列化，运行时间和临时路径不得进入语义哈希。
- `report_id`、protocol、模板版本、family、spec 语义哈希和输出内容哈希应进入回执；若实现未输出某项，验证报告必须明确缺口而不是从文档推定。
- HTML 与 receipt 是同一提交单元。receipt 必须记录输入 hash、HTML hash、模板版本、状态、warnings 与 checks。
- 消费方不得只信任回执自报；必须读回 HTML/receipt 并重算哈希链。

## 写出与幂等

1. 默认目标存在即失败；`--overwrite` 只允许替换精确目标。
2. 在目标同目录创建不可预测暂存文件，完整写入后再校验。
3. 校验 HTML 结构、CSP、离线性、外部资源、占位符、状态标识和内容哈希。
4. HTML 与 receipt 使用原子提交；提交失败不得留下声明成功的 receipt。
5. 提交后读回并重算哈希。读回不一致时返回失败。
6. 相同规范化输入、模板版本和 family 必须生成相同语义 HTML/状态哈希；尝试时间等元数据放在语义哈希之外。

## stdout 与失败状态

v1.0.4 支持 opt-in `--receipt-path-mode relative`：receipt 记录 `artifact_path_base=receipt_directory` 及同目录 HTML/receipt 文件名，仍对其签发 manifest 哈希；实际写出目标和 stdout 绝对路径不变。默认 absolute 与旧消费者兼容。完整产物对搬迁后，上游必须再读回最终文件并重算哈希，不得修改历史 receipt。

stdout 只输出一个 JSON envelope。成功时固定包含 `ok`、执行状态 `VALIDATED|RENDERED`、`report_status`、family、`input_semantic_hash` 与 warnings；实际渲染还包含 `output_path`、`receipt_path` 和 `html_hash`。失败时包含 `ok=false`、`status=BLOCKED` 与安全错误对象。日志写 stderr。

Schema、安全、隐私、凭证、路径、图片或引用失败使用非零退出码，并且不提交产物。`--validate-only` 不写 HTML/receipt，只返回验证 envelope。`BLOCKED` 是业务输入状态，不等同于渲染器失败；它只能生成阻塞说明页并在回执保留 `BLOCKED`。

## 数据覆盖边界

请求存在、spec 可解析或 HTML 成功写出都不等于业务事实完整。渲染器不得把其运行成功升级为 `COMPLETE`、数据质量 A 或强证据；这些值始终来自上游并受契约一致性检查约束。
