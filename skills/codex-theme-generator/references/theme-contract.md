# Theme Pack v2 固定契约

主题包为纯数据和静态资产。顶层必须且只能包含：

`schemaVersion`、`id`、`name`、`appearance`、`assets`、`palette`、`materials`、`layout`、`art`、`compatibility`、`provenance`。

- `schemaVersion`: 固定 `2`。
- `appearance`: `dark|light|auto`；双模式必须用两个独立 ID。
- `assets`: `homeBackground`、`taskBackground` 和八槽位 `icons`。
- `palette`: `accent/accentContrast/canvas/surface/surfaceElevated/text/textMuted/border/menu/panel/composer/dialog`，全部 `#RRGGBB`。
- `materials`: `panelOpacity/composerOpacity/dialogOpacity` 为 `0.25..1`；`radius` 为 `0..28`；`shadow` 为 `none|soft|strong`；`blur` 为 `0..24`。
- `layout`: `mode` 为 `native|compact|cinematic|focus`；`sidebarWidth` 为 `200..320`；`contentMaxWidth` 为 `720..1280`；`composerOffset` 为 `-48..48`；`density` 为 `compact|comfortable|spacious`。生成默认值固定为 `native/240/920/0/comfortable`。后三种模式仅是实验请求，只有精确宿主版本对应矩阵为 `COMPLETE` 时才允许生成和启用。
- `art`: `focusX/focusY/homeIntensity/taskIntensity` 为 `0..1`；`safeArea` 为 `left|right|center|none`。
- `compatibility`: `codexMinVersion`、固定 `rendererFingerprint: codex-theme-studio-v2`、`generatorVersion`。
- `provenance`: 固定生成器、来源 `generated|provided|none|migrated`、三个内置模板之一。

对比度：正文/表面至少 4.5:1，弱化文字/表面至少 3:1，强调色文字/强调色至少 4.5:1。

背景只接受 PNG/JPEG，最大 20 MB，最低 1600×900，约 16:9。图标只接受安全 SVG 或 PNG，单个最大 256 KB。目录及资产链路禁止 junction/symlink 和路径逃逸。

任何未知字段、任意 CSS、JavaScript、selector、运行时命令、可执行文件或恶意 SVG 都必须失败关闭。主题运行时只把 `layout` 映射到版本化白名单 adapter；Theme Pack 不携带 selector 或运行逻辑。

## 状态与发布语义

- Generator 的 `COMPLETE`: Theme Pack 静态契约、资源、对比度、路径安全和原生载荷完整，`publishable: true`。它不表示已导入、已激活或实机验证成功。
- Generator 的 `BLOCKED`: 输入无效、静态验证失败、目标冲突，或实验布局缺少独立 Studio 的受信任矩阵。必须返回非零。
- Studio 的 `COMPLETE/PARTIAL/BLOCKED`: 仅由独立客户端及运行时产生，用于表达导入、宿主适配、几何和视觉证据状态。

Generator 必须额外输出 `importStatus=NOT_RUN` 与 `activationStatus=NOT_RUN`。任何组件都不得把静态 `COMPLETE` 冒充客户端或运行时 `COMPLETE`。

## 三层所有权

- `codex-theme-generator`：构建和静态验证 Theme Pack，不携带客户端源码。
- `Codex Theme Studio`：安装、更新、导入校验、宿主矩阵、视觉门禁和运行时。
- `codex-theme-selector`：只代理已安装客户端的 CLI，不实现安装器或主题生成器。

## 受信任宿主适配器

宿主身份由精确 `Codex Appx 版本 + 组件构建号 + 结构签名集合` 决定。宿主 selector、场景识别、组件计数和布局矩阵只存在于独立 Codex Theme Studio 的受信任 `host-adapters.json` 与运行时中。Generator 只能只读检测已安装 Studio；不得内置或复制运行时矩阵。Studio 缺失、未知版本或矩阵非 `COMPLETE` 时，Generator 必须阻断实验布局。

## 场景与视觉门禁

场景按 `home/task/project-menu/app-menu/dialog/task-sidebar` 分别声明组件，不使用全局 8/8 图标计数。几何门禁阻断重叠、裁切、越界、横向溢出、命中区错位和配置尺寸未生效。组件状态门禁覆盖按钮、菜单/浮层、输入区、侧栏/任务面板、弹窗/提示的状态矩阵。

PR 矩阵、四件套视觉证据和 12 个内置主题烟测由独立 Studio 维护和执行，不属于 Generator 的静态验证。任一文件缺失或 JSON 非 `COMPLETE` 时，Studio 门禁至少为 `PARTIAL`，不得冒充实机成功。

## Codex 原生主题载荷

单一深/浅主题同时输出 `native-theme.json` 与以 `codex-theme-v1:` 开头的 `native-share.txt`；`appearance=auto` 因原生契约要求明确 `variant`，分别输出 `native-theme-dark.json`、`native-theme-light.json` 及对应分享字符串。原生载荷只包含 `codeThemeId/variant/theme`，其中 `theme` 精确包含 `accent/contrast/fonts/ink/opaqueWindows/semanticColors/surface`，不包含背景、圆角、模糊、布局、图标、selector 或运行逻辑。

基于 Codex `26.715.8383.0` 的只读拆包证据，生成器使用注册代码主题 `codex`，保留字体 `null`，深色/浅色 `contrast` 分别为 `60/45`，`diffAdded/diffRemoved` 分别为 `#40C977/#FA423E` 与 `#00A240/#BA2623`。`accent/ink/surface/skill` 从 Theme Pack 配色确定性映射。宿主升级后必须重新核对原生 schema、注册代码主题和默认种子；不得把扩展字段伪装成原生主题字段。
