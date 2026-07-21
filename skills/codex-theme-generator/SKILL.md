---
name: codex-theme-generator
description: 当用户明确要求创建、生成或重建 Codex Desktop 主题时使用，是新主题唯一入口。只生成并静态验证纯数据 Theme Pack v2 与 Codex 原生主题分享载荷；不适用于安装、更新、导入或激活 Codex Theme Studio，后续操作交给 codex-theme-selector。所有输出写入均须先确认目录，目标存在时拒绝覆盖并回滚临时事务；不执行不可逆操作。禁止修改 WindowsApps、app.asar、官方签名和认证数据。
metadata:
  version: "2.3.0"
---

# Codex Theme Generator

## 适用边界

用于新建深色、浅色或双模式主题，生成背景、八个语义图标、配色、材质、白名单布局、静态预览、Theme Pack v2 和 Codex 原生分享载荷，并执行确定性静态验证。

本 Skill 不携带、不安装、不更新 Codex Theme Studio，也不导入、激活、回退、暂停、恢复或实机验证主题。不适用于修改 Codex 官方外观。已有主题的管理操作使用 `codex-theme-selector`；Studio 的安装和更新由独立客户端负责；旧 Dream Skin v1 迁移使用显式 `codex-skin-maker`。

主题包只含白名单 Schema 和静态资产，不允许任意 CSS、JavaScript、selector、安装命令或运行时路径。单主题生成是连续事务，本 Skill 不启用子 agent。

所有写操作必须先获得用户明确确认后执行。所有主题文件写入必须先确认输出目录；目标已存在时拒绝覆盖。高风险输入、路径冲突、客户端身份不明或实验布局证据不足时必须停止，不得猜测或降级成假成功。

## 输入与输出

输入：

- 主题名与 `kebab-case` ID。
- `dark`、`light`、`auto` 或双模式；双模式生成 `<id>-dark` 与 `<id>-light` 两个独立 ID。
- 可选首页/任务页 16:9 PNG/JPEG、八个语义图标目录、强调色、焦点、安全区和布局。
- 默认布局固定为 `native + comfortable + composerOffset=0`。
- 输出目录；目标已存在时拒绝覆盖。

输出：

- 一个或两个完整 Theme Pack v2 目录。
- 静态验证报告与原生分享载荷。
- `packStatus/studioDetected/handoffStatus/importStatus/activationStatus/notRun` 状态字段。
- 可供 `codex-theme-selector` 使用的精确主题目录与主题 ID。

身份保持或品牌复刻需要真实参考图；只有抽象方向时可使用 `immersive-dark`、`clear-light`、`obsidian-gold` 三个内置模板之一。

## 七阶段工作流

### 1. 锁定范围与安全边界

确认主题 ID、外观、素材和输出路径。不得修改 WindowsApps、`app.asar`、官方签名、线程、认证数据或模型配置。背景图不得烘焙 Codex UI、文字、水印或伪交互。

### 2. 设计静态视觉资产

背景优先 2560×1440，最低 1600×900，主体与安全区分离。自定义图标只接受安全 SVG 或 PNG；经用户明确确认后创建静态图标，键名仅允许 `newTask/search/projects/history/attach/send/settings/skills`。这些键名不会执行发送、删除、发布、上传或覆盖等不可逆动作。

### 3. 原子构建 Theme Pack v2

单模式：

```powershell
python scripts\build_theme.py --output-dir "<目录>" --id "<id>" --name "<名称>" `
  --appearance dark --template immersive-dark --accent "#7C8CFF" `
  --home-background "<可选图片>" --task-background "<可选图片>"
```

双模式：

```powershell
python scripts\build_theme.py --output-dir "<目录>" --id "<id>" --name "<名称>" --pair
```

脚本在同级临时目录完成全部写入和验证后原子提交；失败不得留下半成品。

### 4. 确定性静态验证

```powershell
python scripts\validate_theme.py --theme-dir "<主题目录>"
python -m unittest discover -s tests -v
```

只有静态契约、资源、对比度、原生载荷和路径安全全部通过时，`packStatus=COMPLETE` 且 `publishable=true`。`PARTIAL/BLOCKED` 一律返回非零。完整契约见 `references/theme-contract.md`。

颜色归一化、对比度、图片尺寸、路径、结构计数和原生载荷全部由脚本计算，禁止模型手算或凭截图估计。

### 5. 只读检测独立 Studio

默认只检测：

```powershell
$studio = "$env:LOCALAPPDATA\CodexThemeStudio\engine\scripts\theme-studio.ps1"
Test-Path -LiteralPath $studio -PathType Leaf
```

检测不得安装、更新或启动 Studio。`native` 布局不依赖 Studio 即可生成；`compact/cinematic/focus` 属于实验布局，必须提供精确 `--codex-version`，并由已安装 Studio 的受信任宿主矩阵证明对应布局为 `COMPLETE`，否则 `BLOCKED`。

### 6. 生成导入交接

生成完成后报告精确主题目录和 ID，并给出使用 `codex-theme-selector` 导入的下一步。只有用户明确要求导入时，才交给选择器执行；导入完成后仍不得自动激活。

### 7. 交付验收

必须报告：主题目录、主题 ID、外观、布局、背景/图标清单、原生载荷、对比度、静态 Schema 验证、Studio 是否检测到，以及未运行项。

状态边界：

- `packStatus=COMPLETE|BLOCKED`：仅表示主题包静态验证。
- `studioDetected=true|false`：只读检测结果，不表示安装成功。
- `handoffStatus=READY|BLOCKED`：是否具备导入所需目录与精确 ID。
- `importStatus=NOT_RUN`：Generator 永不冒充已导入。
- `activationStatus=NOT_RUN`：Generator 永不冒充已激活或实机验证。

静态预览不能冒充实机效果，主题生成不能冒充客户端安装，主题导入不能冒充激活成功。

## Theme Pack v2 结构

```text
<theme-id>/
├── theme.json
├── preview.html
├── README.md
├── native-theme.json
├── native-share.txt
├── native-theme-dark.json      # 仅 appearance=auto
├── native-theme-light.json     # 仅 appearance=auto
├── native-share-dark.txt       # 仅 appearance=auto
├── native-share-light.txt      # 仅 appearance=auto
└── assets/
    ├── home-background.png|jpg（可选）
    ├── task-background.png|jpg（可选）
    └── icons/<八个语义图标>.svg|png
```

顶层字段白名单：`schemaVersion/id/name/appearance/assets/palette/materials/layout/art/compatibility/provenance`。双模式是两个完整、独立、可切换主题。

## 引用与工具

- Schema 与边界：`references/theme-contract.md`
- 正反例与验收：`references/golden-set.md`
- 构建：`scripts/build_theme.py`
- 严格静态验证：`scripts/validate_theme.py`
- Codex 原生主题编译：`scripts/compile_native_theme.py`
- 回归：`python scripts/run_golden_fixtures.py --format json`

---
_v2.3.0 · generator-only Theme Pack pipeline + independent Studio handoff_
