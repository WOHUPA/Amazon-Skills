---
name: codex-theme-selector
description: 当用户要求检测、浏览、预览、导入 .codextheme、激活、回退、暂停、恢复或验证 Codex Theme Studio 主题时使用。仅作为已安装原生客户端 `--engine` CLI 的轻量 Agent 入口；不适用于生成主题、安装或更新客户端，所有写操作要求明确确认，导入后不自动激活。
metadata:
  version: "2.7.0"
---

# Codex Theme Selector

## 适用边界

这是已安装 `Codex Theme Studio` CLI 的轻量操作入口。列表、状态和预览为只读；导入、激活、回退、暂停、恢复属于写操作，必须来自用户对精确目标的明确请求。

本 Skill 不生成或重绘主题，不实现客户端安装器或更新器，不复制 Studio 运行时代码。创建主题使用 `codex-theme-generator`；Studio 安装和更新使用独立客户端分发入口；旧 Dream Skin v1 迁移使用显式 `codex-skin-maker`。本 Skill 不启用子 agent。

所有写操作必须先获得用户明确确认。激活、回退和完整恢复属于高风险动作；目标 ID 模糊、客户端缺失、状态冲突或验证证据不足时必须先停止，不得猜测。

## 输入与输出

输入：

- `Status/List/Preview/Import/Activate/Rollback/Pause/Resume/Verify/Restore` 动作。
- Preview/Activate 使用唯一精确 Theme Pack v2 ID。
- Import 使用 `.codextheme` Bundle v1；整包任一 ID 冲突则全部停止。
- 写操作需要 `-Confirm`；完整恢复另需用户明确要求 `-Full`。

缺少动作、精确 ID 或主题目录时先补齐参数；客户端缺失、路径不可读或权限不足时返回 `BLOCKED` 并标注未运行项，不安装客户端，也不猜测目标。

输出字段：

`status/currentThemeId/previousThemeId/runtimeStatus/adapterStatus/iconsApplied/verification/notRun`。

确定性 ID、主题计数、路径、状态和验证结果必须由脚本读取，禁止模型手算。客户端缺失时返回 `BLOCKED + runtimeStatus=NOT_INSTALLED`，不尝试安装。CLI 失败时保留原始错误与退出码；不得把缺文件、缺权限或解析失败降级为成功。

## CLI

```powershell
$selector = "$env:USERPROFILE\.codex\skills\codex-theme-selector\scripts\theme-selector.ps1"
& $selector -Action Status
& $selector -Action List
& $selector -Action Preview -ThemeId immersive-dark
& $selector -Action Import -PackagePath '<主题.codextheme>' -Confirm
& $selector -Action Activate -ThemeId immersive-dark -Confirm
& $selector -Action Verify
& $selector -Action Rollback -Confirm
& $selector -Action Pause -Confirm
& $selector -Action Resume -Confirm
& $selector -Action Restore -Confirm
```

默认代理的客户端 CLI：

```powershell
$studio = "$env:LOCALAPPDATA\Programs\Codex Theme Studio\CodexThemeStudio.exe"
```

Selector 统一代理原生参数：`--engine <action>`，配合 `--package`、`--theme`、`--confirm` 与 `--result-file`。`Status` 同时读取 `engineVersion`，不再通过旧 PowerShell 文件推断是否安装。

## 工作流

1. `Status`：只读检测独立 Studio 是否安装；缺失时返回 `NOT_INSTALLED`。
2. `List/Preview`：列出精确 ID 或返回主题自身的 `preview.html`，不修改状态。
3. `Import`：预览并严格校验 Bundle v1、ZIP 路径、大小、SHA-256、可执行文件、恶意 SVG 和 Theme Pack v2；整包暂存、整包提交，同 ID 已存在时全部停止；完成后保持 `activationStatus=NOT_RUN`。
4. `Activate <id>`：再次要求明确确认，仅接受清单中唯一精确 ID；激活前备份当前主题，失败自动恢复。
5. `Verify`：验证 Store 身份、回环 CDP、Browser ID、renderer、主题 ID、adapter 和交互几何。
6. `Rollback`：交换当前主题与上一主题备份并重新验证。
7. `Pause/Resume`：实时卸下或重新应用 renderer 主题，运行时和主题仓库保留。
8. `Restore`：显示官方外观并保留 Studio；`Restore -Full` 可能关闭 CDP 会话并重启 Codex，只在用户明确要求完整恢复时执行。

## 状态与安全

- `COMPLETE`：目标动作完成且该动作要求的验证通过。
- `PREVIEW_ONLY`：只读预览，没有导入或激活。
- `IMPORTED_NOT_ACTIVE`：主题已导入但没有激活。
- `INSTALLED_NOT_ACTIVE`：客户端存在，但没有可验证活动主题。
- `PARTIAL`：主题已应用，但部分 adapter 或图标状态未通过。
- `BLOCKED`：客户端、主题、精确 ID、权限或安全验证缺失。
- `HEALTHY/SELF_HEALING/NEEDS_RESTART/PAUSED/OFFLINE/FAULT`：原生 RuntimeSupervisor 的运行状态；`NEEDS_RESTART` 必须由用户确认，禁止静默结束 Codex。

不接受模糊 ID、序号猜测、同名覆盖、批量激活或主题提供的代码。不修改 WindowsApps、`app.asar`、官方签名、认证数据或用户任务。

## 正反例

- `导入 D:\themes\aurora.codextheme。` → 先预览系列、主题数与冲突，确认后整包导入，报告 `IMPORTED_NOT_ACTIVE`，不激活。
- `切换到 aurora-calm 并验证。` → 先从列表确认精确 ID，再要求激活确认并验证。
- `安装或更新 Theme Studio。` → 不执行，交给独立客户端。
- `生成新的黑金主题。` → 不触发，交给 `codex-theme-generator`。

## 回归与资源

- 触发正反例：`references/golden_set.md`
- 机器案例：`references/golden_cases.json`
- 回归：`python scripts/run_golden_fixtures.py --format json`
- 单元测试：`python -m unittest discover -s tests -v`
- 每次修改前后使用同一批 Golden 与单元测试对比；失败案例先追加到 Golden Set 与 `SKILL.patch.md`，再修改路由或写入流程。
- 主题数、ID、冲突、引擎版本和运行状态只读脚本或原生 `--result-file`，禁止模型手算。

---
_v2.7.0 · native Studio engine proxy + atomic Bundle import_
