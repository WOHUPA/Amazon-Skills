# Windows Changelog

## Unreleased

### 2.6.1 本地背景与主题管理

- 原生客户端新增本地 PNG/JPEG 背景上传，并以事务方式同时更新首页与任务页；活动主题更新失败会自动恢复。
- 新增可恢复的主题删除，阻止删除当前活动主题；内置主题删除后不会在下次启动时自动回填。
- “创建主题”提示词升级为背景质量优先流程，明确收集本地参考图、视觉方向、输出目录和安全区要求。

### 2.6.0 MSI 与事务式独立更新器

- 主分发格式迁移为固定 `UpgradeCode` 的 WiX MSI，接入 Windows Installer 修复、卸载和事务回滚能力。
- 保留 Inno Setup EXE 作为 2.5.x 用户的一次性兼容桥；桥接安装后客户端自动切换到 MSI 更新通道。
- 新增独立 `CodexThemeStudio.Updater.exe`：等待主程序退出，再次校验 SHA-256、Minisign 和更新器自身哈希，然后调用 `msiexec`。
- 升级事务、详细 MSI 日志和最终回执写入更新目录；失败时保留旧版本并重新打开客户端展示原因。
- 下载支持断点续传和三次重试；安装成功后校验磁盘中的实际程序版本。
- 更新信任由单一公钥升级为可轮换公钥环，清单同时兼容单签名和多签名过渡版本。
- GitHub Release 同时发布 MSI、桥接 EXE、各自 Minisign 签名及双平台 `latest.json`。

### 2.5.1 .NET 引擎、可信更新与统一黑白品牌

- 客户端的激活、回退、暂停、恢复、验证、运行时安装和卸载迁入 .NET，不再启动 PowerShell。
- 安装包内置经过固定 SHA-256 校验的 Node.js 24 LTS，干净 Windows x64 电脑无需预装 Node.js。
- 采用 CC Switch 式 GitHub Release `latest.json` 持续升级，并强制校验 SHA-256 与客户端固定公钥的 Minisign/Ed25519 更新签名。
- GitHub 托管 Runner 可直接构建无 Authenticode 的个人开源版本；将来取得 Windows 证书后可额外签名主程序与安装包，不改变现有更新协议。
- Logo、任务栏、托盘和安装器统一为原创黑白几何标志；标题栏按钮改为与深色主体一致的中性色和克制关闭态。
- 托盘菜单改为 WorkBuddy 式紧凑状态菜单，提供打开、暂停/恢复、验证、检查更新和退出。
- 修复旧版开始菜单 PowerShell 快捷方式残留，并让任务栏、开始菜单和托盘直接复用主程序同一图标源。
- 修复 .NET watcher 将 Chromium 文件版本误当 Codex 包版本而导致切换失败的问题；旧状态自动迁移为 schema v4。
- 为 `codex-theme-selector` 增加 `--engine` 轻量 CLI 入口，安装和切换逻辑仍只存在于客户端。

### 2.4.1 稳定切换与统一图标

- 修复切换完成后界面回调卡住或误报失败的问题。
- 缓存主题封面，避免每次切换重复解码全部大图。
- 去除窗口顶部系统白边，补齐主题主视觉上方圆角边框。
- 安装包、窗口、任务栏、快捷方式与系统托盘统一使用多分辨率正式图标。

### 2.4.0 编辑式主题工坊

- 按高端创意工具方向重构主题库：大画幅主题舞台、横向胶片库和编辑式排版。
- 移除固定 Viewbox 缩放，默认窗口升级为 1380×840，并保留 1120×720 的可用下限。
- 主题切换改用底部非阻塞任务坞，实时展示进度、耗时并支持取消操作。
- 主题卡负责选择，应用与预览集中到主舞台，减少重复按钮与界面噪声。

### 2.3.1 客户端稳定性修复

- 主题切换、验证、回退与恢复改为异步执行，避免阻塞 WPF UI 线程。
- 增加单操作保护与 120 秒安全超时，窗口关闭时终止仍在执行的子进程。
- 修复启动器错误隐藏 Theme Studio 主窗口的问题。

### 2.3.0 Windows EXE 分发补充

- 新增内嵌运行时的 `CodexThemeStudio.exe` Windows 启动器。
- 新增 Inno Setup 单文件安装包、Windows 卸载登记、桌面与开始菜单快捷方式。
- 升级继续使用 staging/backup 原子替换；卸载恢复官方外观并删除引擎，但保留用户主题、备份和状态。

### 2.3.0 三层职责拆分

- 从 `codex-theme-generator` 迁出为独立客户端、安装器与运行时源码。
- 安装和更新由 Studio 自己负责；Generator 只生成主题包，Selector 只代理已安装 CLI。
- 移除客户端发行包中的 Theme Pack 构建器和旧主题迁移入口，保留独立导入验证器作为安全边界。
- 新增“创建新主题”按钮：复制 `$codex-theme-generator` 提示词并通过已验证的 Store 包身份打开 Codex，不使用未经证明的提示词深链。
- 导入与激活保持两个独立动作，生成或导入后不会静默激活主题。

### 2.2.1 流式状态宿主适配

- 为 Codex `26.715.8383.0` 改用主布局、任务时间线、composer 根节点和侧栏滚动区的稳定结构标记，移除对缺失 `role=main` 的成功假设。
- 将流式 `Stop/停止` 建模为 `send` 槽位的受信任原生互斥状态；停止生成期间保留原生图标并产出状态证据，不再误报图标缺失或覆盖错误图标。
- 主动作节点切换时会清除旧主题图标并恢复被隐藏的原生 SVG，避免发送/停止切换后残留覆盖层。
- 裁切判定同时要求内容溢出且 `overflow=hidden/clip`；可见侧栏缩放手柄不再制造假阳性，真实裁切仍保持阻断。
- 视觉状态矩阵新增 `streaming-stop`，线上问题先由 Windows 任务流式 fixture 稳定复现后再修适配器。

### 2.2.0 严格发布门禁

- 实时验证只接受 `adapterStatus=COMPLETE`；`PARTIAL/BLOCKED` 统一返回非零并禁止发布。
- 新增精确 Appx 版本、组件构建号、结构签名、页面场景和实验布局收据组成的受信任宿主适配器。
- 新增按场景组件与语义图标期望，阻断重叠、裁切、越界、横向溢出、命中区错位和布局尺寸未生效。
- 新增 PR 三主题六场景九窗口/DPI 组合，以及发布前 12 主题首页/任务页烟测；每例必须具备截图、矩形、计算样式和对比度四类证据。
- 新主题与内置主题统一使用 `native + comfortable + composerOffset=0`，实验布局矩阵未全绿时拒绝启用。

### 修复

- 收起或重建左侧栏时不再因找不到 `aside.app-shell-left-panel` 而整页卸掉皮肤；只要主内容壳层仍在就继续应用当前主题，避免闪回 Codex 原生配色。透明辅助窗口仍会清理残留样式。
- 托盘「暂停皮肤」现在与 macOS 一致：写入暂停标记后立刻通过 CDP 执行 `injector --remove` 卸下当前窗口皮肤，不再只等 watcher 轮询；「继续显示皮肤」会清除暂停并重新应用。
- Windows 注入器补齐与 macOS 相同的窗口内操作浮层（loading / 成功 / 失败）；暂停、继续与重新应用时在 Codex 主区显示「正在暂停皮肤…」「正在应用皮肤…」等进度，不再只有托盘气泡。
- 安装/主题库初始化会把 macOS 同款「Gothic Void Crusade / 哥特虚空远征」播种到已保存主题（`presets/preset-gothic-void-crusade`），可与「桥本有菜」一并在托盘切换；默认活动主题仍为桥本有菜。

## 1.2.0 — 2026-07-17

### 新增

- Windows 安装器会先校验并原子复制运行所需的 `assets/` 与 `scripts/` 到 `%LOCALAPPDATA%\CodexThemeStudio\engine`，启动、恢复和托盘快捷方式统一指向该受管副本；安装完成后可移动或删除源码克隆。重装前若旧托盘仍在运行，安装器会明确要求退出，避免新旧脚本混用。
- 渲染层支持通用自适应图像主题：本地 Canvas 采样图像亮度、主色、焦点和比例，为壁纸层提供自适应色彩与构图建议；支持 `appearance: auto | light | dark`、`art.focusX/focusY`（`0..1`）、`art.safeArea: auto | left | right | center | none`、`art.taskMode: auto | ambient | banner | off`。外观壳仍由显式主题或原生外观信号决定。
- 显式外观与艺术元数据优先于分析结果；超宽图默认任务横幅，普通比例图默认环境背景，`off` 可关闭任务页图像。分析完全在渲染器本地完成，不上传图片。
- Windows 发行 payload 直接读取受管 `theme.json`，完整支持与 macOS 一致的外观、焦点、安全区和任务页模式契约，不再依赖预先设置的 renderer 全局变量。
- 新增纯 PowerShell/Windows Forms 系统托盘入口，可快速查看状态、应用或暂停皮肤、更换背景、保存和切换主题、打开图片文件夹，以及执行完整恢复；不引入第三方依赖。
- 新增 `%LOCALAPPDATA%\CodexThemeStudio` 主题仓库，用户图片会复制到受管目录，活动主题和已保存主题均保持图片与配置自包含。
- Windows 首次安装会把 UI-free 的 2560 × 1440「桥本有菜」设为活动主题并播种到「已保存主题」，无需再从 macOS 目录手动导入。

### 修复

- 安装器在完成受管运行时副本的 SHA-256 校验后，仅清除其中 PowerShell 脚本的下载区标记；启动、恢复、托盘快捷方式和托盘子进程改用 `RemoteSigned`，不再组合隐藏 PowerShell 与 `ExecutionPolicy Bypass` 触发常见 LNK 启发式告警，同时继续服从系统和企业组策略。
- 保留 Codex 原生固定顶栏的定位与层级，避免打开任务侧边面板后开关被推出主区、导致面板无法关闭。
- 暗色外观下，原生顶部菜单栏现在使用深色半透明可读性层，并提高菜单按钮与图标的文字对比度，避免浅色壁纸让导航项难以辨认。
- 渲染层现在只在检测到完整 Codex 主界面壳层时启用皮肤；宠物等透明辅助窗口会主动清理主题背景与装饰节点，避免出现遮挡宠物的矩形背景框。
- 16:9 及更宽图像现在作为侧栏与主区共享的单张整窗背景；首页、任务、插件、计划任务和 Pull Requests 路由使用同一透明顶栏与连续表面，不再在卡片或任务层重复裁切图片。
- 移除主区原生顶部渐隐和 composer 后方底部渐隐；浅色与深色 composer 均只保留一个可读表面，避免出现双层输入框或不连续底板。
- watcher 可在不重启 Codex 的情况下响应主题文件和暂停标记变化，重载 renderer 后仍保持当前应用或暂停状态。
- watcher 会为已连接的 renderer 注册带 generation 检查的 early payload；后续 reload/navigation 优先在新文档建立皮肤，CDP 不支持时仍保留 load-event 兜底注入。
- watcher 改用主题 JSON 与图片字节的 SHA-256 修订值识别热更新，并以轻量 stat 快速路径配合 30 秒强哈希审计，避免每 1.2 秒重读整张图片；同步读取图片尺寸后再构建首帧 payload，避免宽屏主题先以错误比例闪现。
- 主题导入与注入均拒绝空图片和超过 16 MB 的图片；注入前还会拒绝任一边超过 16384px 或总像素超过 50MP 的声明尺寸，降低压缩炸弹风险。完整恢复会终止托盘进程，暂停菜单使用独立闭包值，避免旧托盘重新应用皮肤或连续点击状态反转错误。
- 托盘导入新背景时会重置为 `auto` 焦点、安全区、任务模式和外观，不再错误继承上一张预设的人物位置；从「已保存主题」切换时仍保留该主题的显式元数据。
- PowerShell 主题仓库除词法路径包含检查外，还会逐级拒绝 junction、符号链接等 reparse point；已保存主题不能借链接逃出受管目录。
- 主题仓库会在创建受管目录以及关键图片复制/移动的前后拒绝 reparse point，暂停标记写入前也会检查路径；状态文件仍写入受管根目录并使用 UTF-8 原子替换。导入在复制前复用 Node 图片元数据解析器拒绝超过 16384px 或 50MP 的图片。
- `appearance: auto` 优先读取原生计算后的 `color-scheme`，只有缺少可信原生信号时才回退到系统 `prefers-color-scheme`；横幅任务页与环境任务页共用连续整窗壁纸，不再单独截一块图。
- 启动会先完成 state 校验和重启确认，再清除暂停标记；取消重启提示或遇到校验失败时，已有的暂停 watcher 会继续保持暂停。
- 原生 `color-scheme` 采样会抑制并排空临时 class 变更产生的 observer 记录，不再每约 180ms 自触发一次完整 renderer ensure。
- 安装不再把用户的 `appearanceTheme` 强制改成 `light`；检测到旧版精确托管的浅色三元组时才按已有备份安全迁移，当前安装的恢复也不会覆盖用户后来选择的外观。
- `--verify`、`--once` 和 `--remove` 现在显式把预期 Browser ID 传入一次性目标发现，不再因引用越域的 CLI 变量而等待超时并导致启动验证回滚。
- 记录中的 injector PID 若仍存活但身份不匹配，启动与恢复会保留 state 并中止，不再归档后继续操作未知进程。
- Windows PowerShell 5.1 现在使用同目录临时备份调用 `File.Replace`，避免空备份参数被绑定为非法路径而导致现有 `config.toml` 无法更新。
- 修复 Windows PowerShell 5.1 下注入器/Node 一旦向 stderr 输出（崩溃堆栈、超时报错、Node 警告）就把启动脚本炸成 `NativeCommandError` 的问题：现在原生命令统一经 `Invoke-DreamSkinNative` 执行，verify 失败时 `verify.log` 能真正写出本次输出与退出码，回滚清除注入的路径也不再被 stderr 干扰误判。
- 带引号键名和 CRLF 的 `[desktop]` 配置现在可以逐字节往返恢复；新版 Codex 写入的非冲突 `[desktop.*]` 子表会原样保留，仅在子表与 Dream Skin 必须管理的标量键冲突时拒绝修改。
- Codex 的启动、失败回滚和恢复重开统一通过已注册 Store 包清单中的 AppUserModelId 激活，不再直接执行可能被 WindowsApps 权限拒绝的 `ChatGPT.exe`；CDP 和自定义 profile 参数仍通过系统包激活接口传递。
- 安装与 `-RestoreBaseTheme` 现在严格按 UTF-8 读取，保留原换行风格，并以无 BOM、同目录原子替换方式写回 `config.toml`，避免中文项目名称乱码或导致 Codex 无法启动。
- 遇到带 BOM/无 BOM 的 UTF-16、NUL 字符、无效 UTF-8 或写入期间被其他程序改动的配置时停止修改，不再静默转码或覆盖较新的内容。
- 安装会在当前注册包或 state 记录的旧 Codex 仍运行时明确提示先关闭；配置临时文件写完后会在原子替换前再次核对原始字节，进一步缩小并发覆盖窗口。
- 配置恢复只修改 `[desktop]` 内的外观键，不再误碰其他 section 的同名配置；新增 `-RecoverConfigBackup` 用于显式恢复安装前原始文件，并先保存当前文件。
- 完成配置恢复后会归档本轮安装前备份，使下一次安装重新保存当时的配置，避免重复安装使用过期主题值。
- schema 3 记录的旧 injector PID 只有在 Node 精确路径、脚本命令行、端口、Browser ID 和进程启动时间匹配时才会停止；兼容旧 state 时仍要求原 state 含脚本路径和端口，且 PID 仍匹配 `node.exe`、脚本与 watch 参数，无法确认便归档而不结束进程。
- 启动验证失败会停止 injector、清理状态，并把本次新开的 Codex 恢复为无调试口的普通启动。
- Restore 使用状态中记录的端口，先关闭运行态再写配置；失败时保留 state 并尽量正常重开 Codex，不再留下半完成状态或静默报告假成功。
- Store 更新后若旧版本仍持有已保存的 CDP，会按 state 中的精确路径关闭；检测到新旧版本同时运行时安全停止并提示人工处理。
- 支持带注释或引号的 `[desktop]` 表头与目标键；遇到转义同义键、多行字符串/数组、dotted key 或重复目标键时会在写入前明确停止，避免把合法但无法安全行编辑的 TOML 改坏。
- Store 更新后的旧路径只有在 Appx full name、family name、安装目录和可执行文件仍能与系统注册包匹配时才允许自动关闭；无法证明归属时保留状态并要求手动关闭。
- Store 更新时，仍在运行且身份有效的旧版本 CDP 会直接热重应用；旧版本若未开启 CDP，则在获得现有重启授权后关闭并启动当前注册版本，避免并行打开两个 Codex。
- 遇到 `[desktop.*]` 子表时会在写配置前停止，避免外观标量键与 TOML 子表冲突；热重应用验证失败时会尽力移除本次残余样式。
- Restore 不再要求当前环境仍能找到 Node；schema 3 清理会严格匹配安装时记录的 Node 路径，Node 已升级或卸载也不影响安全恢复。
- 截图验证不再派发 Escape、移动鼠标或额外等待 300ms，避免验证过程改变当前窗口状态。

### 安全

- Codex 以 `--remote-debugging-address=127.0.0.1` 启动；同时校验监听 PID 对应精确的官方 Store 可执行文件。
- 说明：loopback 可阻止局域网访问，但 CDP 不验证同一 Windows 用户下的其他本地进程；不用皮肤时建议执行 Restore 关闭调试会话。
- Appx 发现要求 `SignatureKind=Store` 且不是 development mode，同名开发包或侧载包不会被当作官方 Codex 启动或关闭。
- injector 只连接相同端口、page ID 与路径一致的 loopback WebSocket，并在注入前确认真实 Codex shell DOM 标记。
- watcher 绑定启动时的 CDP Browser ID，并持续持有 Browser WebSocket 作为身份锚；原浏览器关闭或端口被复用时直接退出，不会连接到新端点。
- CDP HTTP、WebSocket 建连与命令均加入超时，HTTP 探测拒绝重定向，异常目标不会无限挂起或把探测带离 loopback。
- injector 收到畸形 JSON 或 `null`、字符串、数字等非对象 CDP 帧时会安全关闭会话，不再因直接读取消息字段而抛出未处理异常。
- injector 日志与验证文件不再记录窗口标题、页面路由、页面文本或被拒绝 URL 的内容，只保留临时 target ID、结构标记和布局结果。
- 快捷方式不再静默携带 `-RestartExisting`；需要重启时先向用户确认。
- install、start、restore 和 verify 使用当前用户互斥锁，避免双击或并发命令竞争端口、配置和 state。

### 改进

- 预置主题的稳定 ID 从 `preset-romantic-rose` 更名为 `preset-arina-hashimoto`；初始化只清理旧预置目录，继续保留用户自建主题。
- 默认端口被占用时自动在后续 100 个端口内选择空闲端口；显式指定的冲突端口仍安全失败。
- injector 会等待首轮注入完成再判定启动成功；目标异常时使用有上限的指数退避和限频日志，减少后台唤醒和日志膨胀。
- 明确要求 Node.js 22 或更新版本，并记录 `process.execPath`，兼容 PATH 中的启动转发程序。
- 带空格或结尾反斜杠的测试 profile 路径现在按 Windows 命令行规则引用。

### 测试

- 增加渲染层辅助窗口与 early-bootstrap 回归测试，覆盖主窗口正常注入、透明辅助窗口清理残余样式、shell guard、generation 切换、computed-scheme observer 排空，以及辅助目标随后成为完整主界面时可重新启用皮肤。
- 增加本地 HTTP/CDP fixture，逐项执行 `--verify`、`--once` 和 `--remove`，确认一次性目标发现会校验 Browser ID 且不再访问未定义变量。
- 增加受管主题初始化、换图、保存、切换、暂停标记、payload 配置嵌入、整窗 CSS 和托盘菜单静态回归检查。
- 增加中文项目路径、CRLF/LF、UTF-16 与歧义 TOML 拒绝、并发写检测、section 隔离、精确恢复、Appx/state 身份、状态归档、payload 构造、Browser ID 和不安全 CDP URL 的回归检查。
- injector 自检覆盖非对象 CDP 帧拒绝和截图流程不派发 renderer 输入事件。
