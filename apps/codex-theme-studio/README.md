# Codex Theme Studio

独立的 Windows Codex Desktop 客户端、安装器与主题运行时，读取纯数据 Theme Pack v2，并通过受验证的本机回环 CDP 应用背景、图标、配色、材质和白名单布局。不会修改 WindowsApps、`app.asar`、官方签名或认证数据。

客户端窗口、任务栏入口、系统托盘、RuntimeSupervisor、主题事务、Bundle 导入、系列目录和 Codex 会话均由编译后的 C# WPF `CodexThemeStudio.exe` 统一承载。客户端不再启动 PowerShell；内置 Node.js 24 LTS 仅运行页面渲染器。

## 目录

- 源码：独立 `codex-theme-studio` 项目目录
- 引擎：`%LOCALAPPDATA%\CodexThemeStudio\engine`
- 主题：`%LOCALAPPDATA%\CodexThemeStudio\themes`
- 活动主题：`%LOCALAPPDATA%\CodexThemeStudio\active-theme`
- 状态/备份/日志：`state.json`、`backups`、`logs`
- 系列目录：`catalog.json`
- 私有缩略图缓存：`cache\thumbnails`

## Windows MSI 安装包

面向普通用户的正式分发物是 WiX MSI，应用安装到用户的 Local Programs，创建桌面和开始菜单入口，并由 Windows Installer 登记、修复、升级和卸载。启动器内嵌经过验证的 Theme Studio 运行时；主题仓库和用户状态独立保留。

```powershell
# Inno Setup 6 只用于给 2.5.x 用户生成兼容桥接 EXE；WiX 由构建脚本按哈希下载
winget install --id JRSoftware.InnoSetup --exact --accept-source-agreements --accept-package-agreements

# 同时生成主 MSI 与兼容桥接 EXE
& .\scripts\build-windows-installer.ps1
```

持续升级采用 GitHub Release `latest.json`：2.5.x 读取桥接 EXE，新客户端读取 MSI。独立更新器会等待主程序退出，二次验证 SHA-256 与 Minisign，调用 Windows Installer，记录安装日志和结果回执，再校验实际程序版本。Windows Authenticode 暂不作为发布前置条件，将来可在不改变更新协议的情况下叠加。GitHub 自动发布和密钥配置见 [`docs/windows-release.md`](docs/windows-release.md)。

卸载会先恢复官方外观并删除运行时引擎，但默认保留 `%LOCALAPPDATA%\CodexThemeStudio\themes`、备份和状态数据，便于重装后恢复。安装包不修改 WindowsApps、`app.asar`、官方签名或认证数据。

安装与更新只由本客户端负责；`codex-theme-generator` 不再携带客户端源码，`codex-theme-selector` 也不实现安装逻辑。

选择器或自动化只调用已安装客户端的轻量 CLI，不复制引擎实现：

```powershell
CodexThemeStudio.exe --engine status --result-file result.json
CodexThemeStudio.exe --engine list --result-file result.json
CodexThemeStudio.exe --engine preview --package C:\Themes\fantasy.codextheme --result-file result.json
CodexThemeStudio.exe --engine import --package C:\Themes\fantasy.codextheme --confirm --result-file result.json
CodexThemeStudio.exe --engine activate --theme immersive-dark --confirm --result-file result.json
CodexThemeStudio.exe --engine verify --result-file result.json
CodexThemeStudio.exe --engine rollback --confirm --result-file result.json
```

客户端“创建新主题”按钮会复制精确的 `$codex-theme-generator` 提示词并打开官方 Codex。当前没有使用未经验证的提示词深链，因此用户需要在新任务中粘贴该提示词；提示词会优先收集本地参考图、高质量背景方向、主题目录和 `.codextheme` 目标。生成完成后可双击 Bundle 或点击“导入主题”直接预览并导入 Studio，无需经过 Selector，激活仍需单独确认。

主题页按系列组织，首次迁移生成“基础主题”与“斗破苍穹”，并提供“全部/未分类”虚拟系列。用户可创建、重命名、排序、删除系列和移动主题；删除系列只把主题移到“未分类”。`.codextheme` 双击后通过单实例命名管道打开导入预览，严格校验后整包导入，且不会自动激活。

主题详情支持选择本地 PNG/JPEG 作为首页与任务页背景。图片必须至少 1600×900、接近 16:9，最大 7680×4320。非当前主题可在二次确认后删除；客户端会把删除内容保留在 `%LOCALAPPDATA%\CodexThemeStudio\backups\deleted-themes`，当前正在使用的主题不能删除。

`pause`/`restore` 实时卸下主题并显示官方外观，同时保留运行时和主题；完整清理由 Windows 卸载程序负责。高级布局只来自精确 Codex 版本的宿主矩阵；版本未知时降级 `native` 并报告 `BLOCKED`，结构签名漂移时报告 `PARTIAL`。两种状态都不会通过验证或发布门禁。

PR 视觉证据使用 `node scripts/injector.mjs --visual-gate pr --evidence-dir <目录>` 校验；发布前使用 `--visual-gate release`。矩阵要求截图、组件矩形、计算样式和对比度四类证据同时为 `COMPLETE`。

内置 12 个 Theme Pack v2：3 个基础主题与 9 个 `doupo-*` 斗破苍穹主题。

来源、许可证和迁移说明见 `NOTICE-UPSTREAM.md`、`LICENSE` 以及 `references/migration-manifest.md`。
