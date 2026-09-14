# Data Pipeline Contract

## 产物与血缘

每次渲染产生一对产物：`<name>.html` 与 `<name>.render-receipt.json`。回执包含：

- `input_semantic_hash`：输入 JSON 的语义哈希（键排序后）。
- `source_spec_raw_hash`：输入 JSON 原样字节的 SHA-256。
- `render_plan_fingerprint`：布局族、主题、目录开关等计划指纹。
- `render_state_hash`：渲染状态哈希（模板版本 + 输入语义哈希 + 计划指纹）。
- `html_hash`：输出 HTML 字节的 SHA-256。
- `manifest_hash`：回执自身主要字段的哈希。
- `template_version`、`render_run_date`、`revision_id`、`supersedes_revision_id` 等血缘字段。

消费方必须重算哈希链验证完整性；`manifest_hash` 必须与重算结果一致。

## 原子提交

- 写入必须先进入同目录暂存文件（`.tmp`）。
- 静态校验通过后才原子替换；HTML 与回执成对提交。
- 提交后读回并校验哈希；任一失败回滚备份。
- 默认拒绝覆盖已有目标；`--overwrite` 显式放开。

## 默认覆盖保护

- 目标已存在且未 `--overwrite`：拒绝并返回错误。
- `--overwrite`：先备份原文件到同目录 `.bak`，提交成功后删除备份。
- 失败路径不留下半成品；回执与 HTML 要么都成功要么都不成功。

## stdout 契约

stdout 只输出一个机器可解析 JSON 对象：

```json
{"ok": true, "status": "COMPLETE", "output_path": "...", "receipt_path": "...", "html_hash": "...", "manifest_hash": "..."}
```

诊断信息（警告、错误、进度）写入 stderr，不得污染 stdout。
