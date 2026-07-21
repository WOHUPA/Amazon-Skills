# Codex Theme Studio 迁移清单

## 来源

- 上游：`https://github.com/Fei-Away/Codex-Dream-Skin`
- 上游与本机基线 commit：`e776fa6d5361a2bdd5c1614674397681e7b00874`
- 许可证：MIT，副本保存在根目录 `LICENSE`。
- 上游声明：根目录 `NOTICE-UPSTREAM.md`。

## 三层拆分

- `codex-theme-generator` 只生成和静态验证 Theme Pack v2。
- 本目录是独立 Codex Theme Studio 客户端、安装器和运行时源码。
- `codex-theme-selector` 只代理已安装客户端的 CLI。
- 独立客户端不包含 Theme Pack 构建器或旧主题迁移入口；导入验证器作为不信任外部主题包的安全边界继续保留。

## 本地定制保全

- 删除前二进制补丁：`C:\Users\quyib\Documents\Codex\2026-07-21\new-chat\outputs\dream-skin.patch`
- 原仓库存在 16 个 tracked 变更/删除和 3 个未跟踪萧炎预设目录。
- 三个未跟踪预设已迁入 `presets/legacy`，不作为 Theme Pack v2 默认主题。

## 能力迁移

- 保留：Store 包身份验证、回环 CDP、Browser ID、原子引擎更新、watcher、托盘、暂停、恢复和实机验证。
- 保留：Theme Pack v2 导入校验、首页/任务页背景、八个语义图标、palette/materials、白名单 layout、适配器降级、回退和独立 CLI。
- 停用：旧 `%LOCALAPPDATA%\CodexDreamSkin` watcher；其数据默认保留为人工回滚备份。

## 删除门禁

只有独立 Studio 源码通过完整测试、Generator 与 Selector 回归通过、全局 Skill 同步完成，并确认不再引用 `skill-src/tool/codex-theme-studio` 后，才删除旧内嵌客户端目录。
