# Golden Set

## 案例 1：客户端状态检测

输入：`检查 Codex Theme Studio 是否安装。`

期望：只读返回 `INSTALLED` 或 `NOT_INSTALLED`；客户端缺失时不尝试安装。

## 案例 2：只读列表

输入：`列出 Theme Studio 里的主题。`

期望：代理客户端 `list`，不修改主题仓库或活动状态。

## 案例 3：精确预览

输入：`预览 immersive-dark。`

期望：返回该精确 ID 的 `preview.html`，不导入、不激活。

## 案例 4：导入不激活

输入：`导入 D:\themes\aurora.codextheme，但先不要激活。`

期望：先返回系列、主题数、安全验证和冲突预览；确认后只调用客户端 `import`，整包事务提交并报告 `IMPORTED_NOT_ACTIVE`，不串联 `activate`。

## 案例 5：精确激活

输入：`切换到 obsidian-gold 并验证。`

期望：单独确认后激活唯一精确 ID；激活前备份当前主题并 live verify。

## 案例 6：回退

输入：`回退到上一个主题。`

期望：确认后交换当前与上一主题备份，失败自动恢复。

## 案例 7：暂停与官方外观

输入：`暂停主题，显示官方外观但保留主题。`

期望：确认后实时卸下 renderer，运行时与主题仓库仍保留。

## 案例 8：安装更新反例

输入：`安装或更新 Codex Theme Studio 客户端。`

期望：不执行，路由到独立客户端分发入口；Selector 不实现安装器或更新器。

## 案例 9：生成反例

输入：`生成一套新的黑金主题。`

期望：不触发，路由到 `codex-theme-generator`。

## 案例 10：迁移反例

输入：`迁移旧 Dream Skin v1 主题。`

期望：不触发，显式路由到 `codex-skin-maker`。

## 案例 11：原生客户端探测

输入：`检查 Theme Studio 2.7 引擎是否正常，不要依赖旧 PowerShell 脚本。`

期望：探测已安装 `CodexThemeStudio.exe` 并调用 `--engine status`，返回引擎版本和 RuntimeSupervisor 状态。

通过标准：11 个案例全部满足；客户端缺失、模糊 ID、未确认写入、Bundle 部分冲突、导入后静默激活和无验证激活均失败。
