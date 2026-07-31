# Codex Themes 技术路线对标

## 参考基线

- 上游：`https://github.com/freestylefly/codex-themes`
- 固定审阅版本：`10b7606bafe63d71b20fcdf02dc4bf6254664c3f`（`v0.2.9`）
- 许可证：MIT；本项目仅借鉴其架构与公开配方契约，未复制其商业、支付或云端代码。

## 上游完整链路

```text
图片或 AI 提示
  -> Theme Recipe v1
  -> 本机图像分析与 palette synthesis
  -> 主题编译 / 预览
  -> .codextheme 导入
  -> CDP watcher 应用 / 恢复
  -> 可选的社区投稿、审核、积分和支付
```

上游客户端是 macOS + Electron，页面层使用 React，官网使用 Astro，社区与商业层使用 Vercel API、Supabase 和支付宝。主题层不改写 Codex 安装包，而是通过本机 CDP watcher 注入纯视觉效果，并在窗口或页面刷新后重新应用。

## 本项目的 Windows 对等实现

| 上游能力 | Theme Studio 现状 | 对标策略 |
| --- | --- | --- |
| Theme Recipe v1 | 新增配方编译桥 | 接受配方和本地图片，编译为 Theme Pack v2 |
| 画廊、导入与预览 | 已具备 | 保留 WPF 主题库、Bundle 预览与单独确认导入 |
| `.codextheme` | 已具备且有 ZIP 清单校验 | 不降低原子导入、哈希、路径逃逸与无自动激活门禁 |
| CDP watcher | 已具备且有 RuntimeSupervisor | 保留严格宿主矩阵、结构/几何/视觉证据验证 |
| 安装、更新与卸载 | 已具备 Windows MSI + Minisign | 不采用上游未签名 DMG 分发方式 |
| AI 连续创作 | 下一阶段 | 复用上游“候选图 + 不可变配方修订”模型，接入现有 Codex 交接，不把模型输出直接当运行时代码 |
| 社区、账号、支付 | 不在当前改造范围 | 需要独立服务端、RLS、审计与支付合规后再立项 |

## 新增的配方兼容桥

`RecipeThemeCompiler` 只接受以下输入：

- Theme Recipe v1 JSON（最多 1 MB）；
- 本地 PNG/JPEG 主图（1600×900 至 7680×4320，最多 80 MB）。

它会从内置深色或浅色模板创建一个新的 Theme Pack v2，并保留所有现有图标、安全验证、预览、原生载荷与 Bundle 兼容能力。上游的八种视觉布局当前统一映射为已经由本机宿主矩阵验证过的 `native` 布局；不会把未验证的 CSS 或布局名直接注入 Codex。

生成成功仅会写入主题库和 `AI 配方`系列，不会导入 Bundle、不会启动 Codex、不会激活主题。返回值会始终包含 `activationStatus: NOT_RUN`。

### 自动化入口

```powershell
CodexThemeStudio.exe --engine create-recipe `
  --recipe "C:\Themes\recipe.json" `
  --image "C:\Themes\hero.png" `
  --confirm --result-file "C:\Themes\result.json"
```

之后在 Studio 中检查生成主题，再由用户单独确认“应用主题”。

## 下一阶段的实现顺序

1. 在 WPF 客户端增加“配方 + 主图”向导和真实 Codex 结构预览；复用现有异步操作、取消和事务交互。
2. 将 `codex-theme-generator` 的受控输出改为 Recipe v1 + Theme Pack v2 双产物，保持生成与安装分离。
3. 以“候选主图批次、配方修订、采纳的不可变版本”为本地数据模型，引入连续 AI 创作。
4. 为每一种新增布局建立 Windows 宿主版本矩阵、截图、组件几何与对比度证据；未通过前不可开放应用。
5. 只有明确需要运营主题市场时，再设计账号、投稿审核、权益、账本和支付服务端；不得把这些能力塞入本地安装器。
