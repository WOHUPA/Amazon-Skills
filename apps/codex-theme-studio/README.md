# Codex Theme Studio

独立的 Windows Codex Desktop 客户端、安装器与主题运行时，读取纯数据 Theme Pack v2，并通过受验证的本机回环 CDP 应用背景、图标、配色、材质和白名单布局。不会修改 WindowsApps、`app.asar`、官方签名或认证数据。

客户端窗口、任务栏入口、系统托盘、主题事务和 Codex 会话均由编译后的 C# WPF `CodexThemeStudio.exe` 统一承载。客户端不再启动 PowerShell；内置 Node.js 24 LTS 仅运行页面渲染器。

## 目录

- 源码：独立 `codex-theme-studio` 项目目录
- 引擎：`%LOCALAPPDATA%\CodexThemeStudio\engine`
- 主题：`%LOCALAPPDATA%\CodexThemeStudio\themes`
- 活动主题：`%LOCALAPPDATA%\CodexThemeStudio\active-theme`
- 状态/备份/日志：`state.json`、`backups`、`logs`

## Windows EXE 安装包

面向普通用户的正式分发物是单个 Windows Setup EXE，安装形态参考 CC Switch：应用安装到用户的 Local Programs，创建桌面和开始菜单入口，并登记到 Windows“已安装的应用”。启动器内嵌经过验证的 Theme Studio 运行时；升级时使用 staging/backup 原子替换，主题仓库和用户状态独立保留。

```powershell
# 首次构建前安装 Inno Setup 6
winget install --id JRSoftware.InnoSetup --exact --accept-source-agreements --accept-package-agreements

# 生成 dist\Codex-Theme-Studio-Setup-2.5.1.exe
& .\scripts\build-windows-installer.ps1
```

持续升级采用与 CC Switch 相同的 GitHub Release `latest.json` 拓扑：版本比较、平台包选择、下载和原位安装；每个安装包都必须通过 SHA-256 和客户端内置公钥的 Minisign/Ed25519 签名验证。Windows Authenticode 暂不作为发布前置条件，将来可在不改变更新协议的情况下叠加。GitHub 自动发布和密钥配置见 [`docs/windows-release.md`](docs/windows-release.md)。

卸载会先恢复官方外观并删除运行时引擎，但默认保留 `%LOCALAPPDATA%\CodexThemeStudio\themes`、备份和状态数据，便于重装后恢复。安装包不修改 WindowsApps、`app.asar`、官方签名或认证数据。

安装与更新只由本客户端负责；`codex-theme-generator` 不再携带客户端源码，`codex-theme-selector` 也不实现安装逻辑。

选择器或自动化只调用已安装客户端的轻量 CLI，不复制引擎实现：

```powershell
CodexThemeStudio.exe --engine activate --theme immersive-dark --result-file result.json
CodexThemeStudio.exe --engine verify --result-file result.json
CodexThemeStudio.exe --engine rollback --result-file result.json
```

客户端“创建新主题”按钮会复制精确的 `$codex-theme-generator` 提示词并打开官方 Codex。当前没有使用未经验证的提示词深链，因此用户需要在新任务中粘贴该提示词；生成完成后由选择器执行导入，激活仍需单独确认。

`pause`/`restore` 实时卸下主题并显示官方外观，同时保留运行时和主题；完整清理由 Windows 卸载程序负责。高级布局只来自精确 Codex 版本的宿主矩阵；版本未知时降级 `native` 并报告 `BLOCKED`，结构签名漂移时报告 `PARTIAL`。两种状态都不会通过验证或发布门禁。

PR 视觉证据使用 `node scripts/injector.mjs --visual-gate pr --evidence-dir <目录>` 校验；发布前使用 `--visual-gate release`。矩阵要求截图、组件矩形、计算样式和对比度四类证据同时为 `COMPLETE`。

内置示范主题：`immersive-dark`、`clear-light`、`obsidian-gold`。

来源、许可证和迁移说明见 `NOTICE-UPSTREAM.md`、`LICENSE` 以及 `references/migration-manifest.md`。
