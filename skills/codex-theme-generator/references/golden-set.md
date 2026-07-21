# Golden Set

## 正例

- `生成一套深色 Codex 主题，背景、图标、菜单和输入区要配套。` → 触发生成器，输出并静态验证 Theme Pack v2。
- `做一套可以分别切换的深浅双主题。` → 使用 `--pair`，生成两个独立 ID。
- `用黑金模板做 cinematic 布局。` → 先要求精确 Codex 版本，只读检测独立 Studio；缺少受信任 `COMPLETE` 矩阵时返回 `BLOCKED`。

## 反例

- `安装或更新 Codex Theme Studio。` → 由独立客户端处理，不触发生成器。
- `导入刚生成的主题。` → 使用 `codex-theme-selector`，导入后不自动激活。
- `切换到 obsidian-gold。` → 使用 `codex-theme-selector`。
- `把旧 CodexDreamSkin 主题迁移过来。` → 显式使用 `codex-skin-maker`。
- `把 Codex 官方设置切成浅色。` → 不触发主题生成。
- `生成 Windows 壁纸。` → 不触发。

## 执行断言

- v2 顶层、子字段和八个图标槽位均为精确集合。
- 双模式生成两个独立 ID；已有目标拒绝覆盖。
- 恶意 SVG、路径逃逸、reparse point、可执行文件、超限图片、未知字段和越界布局失败关闭。
- 生成失败无半成品；合法包静态验证为 `COMPLETE` 且 `publishable=true`。
- `tool/codex-theme-studio` 不存在于 Generator 源码；安装、更新和运行时测试不属于 Generator。
- 默认布局为 `native/240/920/0/comfortable`；实验布局只读查询已安装 Studio 的受信任矩阵。
- 生成结果必须显式报告 `importStatus=NOT_RUN` 与 `activationStatus=NOT_RUN`。
- 颜色、对比度、图片尺寸、结构计数和原生载荷由脚本计算，不允许模型手算。
