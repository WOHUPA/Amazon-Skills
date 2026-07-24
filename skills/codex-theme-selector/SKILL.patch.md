# Codex 主题选择器变更记录

## [2026-07-25] v2.7.0

- 安装探测改为原生 EXE 与引擎版本，不再依赖缺失的 `theme-studio.ps1`。
- CLI 统一为 `--engine`，通过 `--package/--theme/--confirm/--result-file` 传递确定性参数。
- Import 改为 `.codextheme` Bundle v1 的预览、严格安全校验和整包事务；导入后仍不自动激活。
- 新增 RuntimeSupervisor 状态语义，任何需要重启 Codex 的动作都要求明确确认。

## [2026-07-21] v2.1.0

- 收缩为已安装 Codex Theme Studio CLI 的轻量 Agent 操作入口。
- 删除 `Install/Update` 动作，客户端缺失时只返回 `NOT_INSTALLED`，不复制安装逻辑。
- 新增只读 `Status`；Import 只导入并保持 `activationStatus=NOT_RUN`，激活继续单独确认。
- 补充三层路由反例、独立单元测试和 10 项 Golden 回归。

## [2026-07-21] v2.0.0

- 从旧 Dream Skin 主题包选择器改为 Codex Theme Studio 唯一操作入口。
- 支持 `list/preview/import/activate/rollback/pause/resume/verify/restore/install/update`。
- 激活前原子备份上一主题，切换失败自动恢复；同 ID 仍拒绝覆盖。
- 精确 ID、显式写入确认、adapter `PARTIAL` 降级和官方外观实时恢复成为固定契约。

## 1.0.0

- 新增主题包 List/Preview/SavedList/Stage/Activate/Verify 六段流程。
- 新增离线 HTML 画廊与九宫格联系表生成器。
- 写入动作绑定精确 theme ID、用户明确确认和 `-Confirm` 参数。
- 同名目标停止，不覆盖、不删除；激活前返回 `previousThemeId`。
- 新增 6 个正反例和确定性 Golden runner。

后续若出现误触发、模糊 ID 或运行时兼容失败，应先把失败案例补入 `references/golden_set.md` 与 `references/golden_cases.json`，再修改流程并重跑验证。
