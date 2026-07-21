# Golden Set（结构化入口）

本文件案例编号必须与 `golden_cases.json` 一致；详细执行断言同时见 `golden-set.md`。

## 案例 1 完整深色主题

输入：生成一套深色 Codex 主题，背景、图标、菜单和输入区配套。期望：生成并静态验证 Theme Pack v2、原生载荷和安全 native 布局。

## 案例 2 双模式主题

输入：生成可分别切换的深浅双主题。期望：使用 `--pair` 生成两个独立 ID 和两套原生载荷。

## 案例 3 实验布局只读检测

输入：用黑金模板生成 cinematic 布局。期望：要求精确 Codex 版本，并只读查询已安装 Studio 的受信任矩阵；Studio 缺失或矩阵非 `COMPLETE` 时返回 `BLOCKED`。

## 案例 4 三层职责分离

输入：安装或更新 Codex Theme Studio。期望：Generator 不处理，交给独立客户端；生成器源码不得包含 `tool/codex-theme-studio`。

## 案例 5 切换反例

输入：切换到 obsidian-gold。期望：不触发生成器，路由到 `codex-theme-selector`。

## 案例 6 旧主题迁移反例

输入：迁移旧 CodexDreamSkin v1。期望：不触发生成器，显式路由到 `codex-skin-maker`。

## 案例 7 官方模式反例

输入：把 Codex 官方设置切成浅色。期望：不触发扩展主题生成。

## 案例 8 安全失败关闭

输入：恶意 SVG、路径逃逸、越界布局或已存在目标。期望：`BLOCKED`、无半成品、不覆盖目标。

## 案例 9 静态与运行状态分离

输入：主题包静态验证通过但尚未导入。期望：`packStatus=COMPLETE`、`handoffStatus=READY`，同时 `importStatus=NOT_RUN`、`activationStatus=NOT_RUN`。

## 案例 10 原生主题编译

输入：合法 Theme Pack。期望：确定性生成 `codex-theme-v1:`，校验器拒绝缺失或与 Theme Pack 分叉的原生载荷。
