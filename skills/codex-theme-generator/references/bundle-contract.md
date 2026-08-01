# Codex Theme Bundle v1

`.codextheme` 是纯数据 ZIP，不改变 Theme Pack v2 内部契约。

固定结构：

```text
bundle.json
themes/<theme-id>/
```

`bundle.json` 顶层只允许：

- `schemaVersion`: 固定为 `1`
- `bundleId`: 小写字母、数字和连字符
- `name`: 1-80 字符
- `series`: 精确包含 `id/name`
- `themes`: 每项精确包含 `id/path`，其中 `path=themes/<id>`
- `files`: 每项精确包含 `path/size/sha256`

生成端必须：

- 在清单中记录所有主题文件，不记录 `bundle.json` 自身。
- 使用真实字节大小和小写 SHA-256。
- 单主题和 `--pair` 双主题均只生成一个 Bundle。
- Bundle 与主题目录任一目标存在时拒绝覆盖。
- 两个输出目标统一暂存、统一提交；提交失败共同回滚。

Studio 导入端必须拒绝：

- ZIP 路径逃逸、重解析点、未知字段、重复路径或重复 ID。
- 解压总量、单文件大小、文件数量、主题数量和压缩比超限。
- 可执行文件、恶意 SVG、哈希或大小不一致。
- 非 Theme Pack v2、主题 ID/目录不一致、资源缺失或解码尺寸超限。
- 任一已存在主题 ID；冲突时整包停止，不覆盖、不部分导入。

导入完成只报告 `activationStatus=NOT_RUN`，不得自动激活。
