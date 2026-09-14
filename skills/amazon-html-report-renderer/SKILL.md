---
name: amazon-html-report-renderer
description: 当用户要求生成 Amazon 业务 HTML，或上游 Skill handoff amazon-html-report/v1 时使用。将已完成分析、已脱敏的结构化 JSON 渲染为自包含、响应式、可打印的离线 HTML 和可审计回执；适用于广告、周报、VOC、选品、竞品、关键词、库存、SOP、知识库等展示。不用于上游取数、业务决策、外部系统变更、PDF/飞书/微信排版、普通分析或一般长回答。
---

# Amazon HTML Report Renderer

_v1.0.6

## 目标与职责

把上游已经完成分析和脱敏的 `amazon-html-report/v1` JSON 渲染为可离线打开的单文件 HTML。渲染器只负责契约校验、安全转义、组件选择、版式、内联 SVG、响应式与打印表现，以及产物和回执的原子写出。

本 Skill 不获取数据、不补全缺失值、不计算或修正业务指标、不推导结论、不调用真实店铺/广告/MCP、不发布到外部系统。Renderer-owned business Metric Contract 为 **N/A**；但必须验证上游指标的 `source_refs`，并验证所有 `DERIVED` 指标已携带公式、输入引用与计算收据。数值、引用、哈希、格式转换与 SVG 坐标等确定性计算必须交给脚本，不交给 LLM 手算。

本 Skill 的所有本地文件写操作必须先获得用户明确确认后方可执行。它不写入真实店铺或广告，不删除或移动外部资产，不发送任何消息，不发布或上传任何产物，也不覆盖外部资产。唯一允许的本地输出为调用方指定的 `.html` 与同名回执，该写入可回滚；默认拒绝替换已有文件。只有调用方显式传入 `--overwrite` 才能替换这对本地文件，并必须使用同目录暂存、备份恢复、双产物提交与哈希读回，失败时回滚原文件。

## 何时触发

满足以下任一条件才使用：

1. 用户明确要求生成 Amazon 业务 HTML、离线网页报告或 HTML 模板，并已提供可转换成协议的结构化报告模型。
2. 上游 Amazon Skill 显式交接 `protocol=amazon-html-report/v1`，并要求生成 HTML。

不要因为出现“报告”“Amazon”“分析”或长文本就触发。下列场景不适用，必须让位给原业务 Skill 或专用排版 Skill：

- LinkFox/Amazon 报表请求、轮询、下载、取数或授权。
- 广告、VOC、选品、库存等业务分析、指标计算、诊断或建议生成。
- 店铺、广告、Listing、补货等后台写操作。
- PDF、飞书、微信公众号、发布、上传或托管。
- 非 Amazon 网页、普通 Markdown/长回答、任意旧 HTML 片段转换。

反例：用户只要求分析广告表现时，应由广告分析 Skill 形成指标和结论；用户要求 LinkFox 下载报告时，应由取数 Skill 执行；用户要求微信公众号 HTML 时，应由微信排版 Skill 处理。三者都不得仅因最终可能出现“报告”而触发本 Skill。

## 输入要求

- 唯一业务输入是符合 [报告协议](references/report-spec.md) 和 `assets/report-spec.schema.json` 的 JSON 文件。
- v1 拒绝 raw HTML、raw SVG、raw JavaScript、Markdown 片段和未知组件。
- 输入必须明确 `REAL/DEMO`、`COMPLETE/PARTIAL/BLOCKED`、报告版本、数据质量、证据强度、隐私状态、来源、指标、数据集、章节、限制与渲染配置。
- 缺失、冲突、真实零和不可用状态必须分开；禁止把 `null` 或失败状态转成 `0`。
- Evidence Image 仅接受本地 PNG/JPEG/WebP 或对应 data URI；不得提供远程 URL、SVG、假截图或生成式占位图。

上游来源可以是已授权且已脱敏的一方/官方导出、Amazon 公开对象或标明口径的第三方数据，但必须在 `sources[]` 中声明类型、角色、覆盖、时点与质量。自己店铺或店铺后台私有数据必须来自官方 API、MCP、团队可信服务或官方导出；浏览器和网页抓取禁止用于此类私有数据。本 Skill 不做浏览器、公开网页或其他来源降级。私有数据未授权或来源冲突时只保留原 `PARTIAL/BLOCKED`；弱证据不得支撑高风险修改、证据等级升级或业务结论升级。

完整字段、状态和示例见 [报告协议](references/report-spec.md)、[报告版本](references/report-editions.md) 与 [组件契约](references/component-contracts.md)。

## 输出产物

- `<name>.html`：自包含、无外部请求、无 JavaScript 仍能阅读正文并使用原生“回到顶部”锚点的语义化 HTML。
- `<name>.render-receipt.json`：输入语义哈希、HTML 哈希、模板版本、状态、警告与验证结果。
- stdout：只输出一个机器可解析 JSON 对象；诊断信息不得污染 stdout。

默认拒绝覆盖已有目标。写出必须经过暂存、静态校验、原子替换和读回校验；失败时不留下半成品。管道身份、血缘与交接要求见 [数据管道契约](references/data-pipeline-contract.md)。

## 执行流程

1. 确认任务同时满足 Amazon 业务与 HTML/显式 handoff 触发条件。
2. 读取 JSON，先按 Schema 检查形状、枚举、未知字段和引用，再执行安全与跨字段校验。
3. 阻断凭证、未脱敏私有标识、远程资源、非法图片路径、raw HTML/SVG/JavaScript、无来源数值和无收据派生指标。
4. 保留上游 `report_edition`、数据质量、证据强度与状态，不自行升级或重算。
5. `family=auto` 时按 [布局族](references/layout-families.md) 映射；`report_type=custom` 必须显式指定非 `auto` 布局族。
6. 按 [组件契约](references/component-contracts.md) 只渲染具有有效数据的组件；不生成空图、空卡片或伪数据。
7. 按 [设计系统](references/design-system.md) 生成安全 HTML、原生 CSS、最少量渐进增强 JavaScript和确定性内联 SVG；所有表格先审核整列表头与已格式化单元格的可见宽度，超过 10 个中文等宽字符时分档加宽；每份 COMPLETE、PARTIAL、BLOCKED 或 DEMO 页面都提供原生“回到顶部”锚点。
8. 校验离线性、CSP、语义结构、可访问性、打印和哈希后原子提交 HTML 与回执。

`BLOCKED` 输入只能生成醒目标识的数据质量/阻塞说明页，不能伪装成正常经营看板。`DEMO` 必须在页首、结论区和打印版持续显示演示标识。

数据质量说明必须是完整报告，包含阻塞原因、质量等级、证据强度、限制与来源；禁止只给总分、评级或一句简短建议。

## CLI

```powershell
python scripts/render_report.py `
  --spec <report-spec.json> `
  --output <report.html> `
  [--family auto|performance|insight|operations|knowledge] `
  [--validate-only] `
  [--overwrite] `
  [--receipt-path-mode absolute|relative]
```

`--overwrite` 只放开已存在本地产物的替换门，该替换可由备份恢复；它不放宽安全、Schema、隐私或读回校验。

默认 `absolute` 保留既有路径合同。需要整体搬迁离线产物的上游可显式选择 `relative`：receipt 的 `output_path / receipt_path` 仅记录同目录文件名，新增 `artifact_path_base=receipt_directory`，这些字段参与 manifest 哈希。stdout 仍返回本次绝对物理输出路径。调用方必须在搬迁后按最终 receipt 目录定位并重算 HTML 与 manifest；不得手改历史收据。

## Codex 部署与同步

本 Skill 的 Codex 安装副本位于 `~/.codex/skills/amazon-html-report-renderer/`（Windows 下 `~/.codex` 是指向其他盘符的 junction）。当前项目中 `skill-work/` 本身就是一个指向该安装目录的 junction，编辑项目即编辑已安装 Skill，Codex 自动检测变更（未生效时重启 Codex）。

- **同步脚本**：`python scripts/sync_to_codex.py` 是独立副本（如 git 仓库检出）→ 安装目录的安全同步入口。源与目标为同一物理目录时报告 `in-sync via junction` 并退出；否则逐文件复制、排除 `__pycache__` 与 `*.pyc`、同步后逐文件 SHA-256 校验，任一不一致即非零退出。`--dry-run` 先预览差异；`--prune` 可清理目标中源已不存在的文件；`--json` 输出机器可读结果。
- **禁用**：在 `~/.codex/config.toml` 中对本 SKILL.md 路径设置 `[[skills.config]]` 的 `enabled = false`。
- **触发策略**：`agents/openai.yaml` 声明 `allow_implicit_invocation: true`，Codex 可依 description 自动触发；本 Skill 不依赖 MCP/外部工具，因此不声明 `dependencies`。

## 视觉与质量门

统一 Design Read：面向中国 Amazon 卖家和运营团队的高密度、证据优先 B2B 报告，视觉严肃、现代、有 Amazon 识别度，采用语义化 HTML、原生 CSS 和内联 SVG。

固定 Taste dials：`DESIGN_VARIANCE=5`、`MOTION_INTENSITY=2`、`VISUAL_DENSITY=7`。`taste-skill` 只指导报告外壳、首屏、节奏、主题与反模板化；高密度数据组件、CJK 排版、可访问性和视觉 QA 以 `frontend-design` 及本 Skill 数据契约为准。

“回到顶部”必须使用指向稳定唯一 `#report-top` 的原生 `<a>`，不能由 JavaScript 接管导航。无 JavaScript 时链接保持可见并可用；启用 JavaScript 后只能用 `IntersectionObserver` 根据报告首屏是否离开视口渐进显隐。控件必须有明确可访问名称、可见 `:focus-visible`、合理触控尺寸和正常 Tab 顺序；不得使用正 `tabindex`、滚动事件轮询或仅鼠标可用的交互。`prefers-reduced-motion: reduce` 下不得强制平滑滚动，打印时控件必须隐藏。完整规则见 [视觉设计系统](references/design-system.md)。

以下任一情况必须失败且不生成正常报告：

- 协议、Schema、引用或组件类型非法。
- 私密数据未脱敏，或输入疑似包含 Token、Cookie、密钥、签名 URL、邮箱/手机号等不应公开内容。
- 数值无 `source_refs`，派生指标缺公式、输入引用或计算收据。
- 图片不是允许的本地格式、单张超过 5 MiB、合计超过 20 MiB，或路径越界。
- 目标存在且未显式 `--overwrite`，或暂存、校验、提交、读回、哈希任一步失败。

## 按需读取

- 协议字段、引用和缺失语义：[references/report-spec.md](references/report-spec.md)
- 十组必备组件及附加文本组件：[references/component-contracts.md](references/component-contracts.md)
- 四个布局族与自动映射：[references/layout-families.md](references/layout-families.md)
- 视觉 tokens、Taste 边界与可访问性：[references/design-system.md](references/design-system.md)
- BASIC/部分增强/完整增强和五级字段：[references/report-editions.md](references/report-editions.md)
- 产物、血缘、原子提交和回执：[references/data-pipeline-contract.md](references/data-pipeline-contract.md)
- 六组 Golden 案例、量化验收与回归入口：[references/golden_set.md](references/golden_set.md)

## 最小回归与验收

- `python -m unittest discover -s tests -p "test_*.py" -v`：40/40 单元与集成测试必须全部通过。
- `python scripts/run_golden_fixtures.py --format json`：6/6 Golden 案例必须 PASS，且不得存在未执行案例。
- `evals/trigger-evals.json`：20/20 正反触发案例必须符合预期。
- `python scripts/sync_to_codex.py --dry-run`：与 Codex 安装副本保持同步（junction 场景报告 `in-sync via junction`；独立副本场景必须显示 0 个待变更文件）。
- Chrome 视觉 QA：四个布局族各执行 3 个视口乘浅色、深色、打印，再加移动端禁用 JavaScript，共 40/40 场景 PASS；不得有页面横向溢出、控制台异常或外部请求。
- 表格列宽：业务数据表、图表数据摘要、雷达对比表、关键词表与来源附录统一扫描表头和全部已格式化可见单元格；中文及 Unicode 全角字符计 1 个视觉单位，半角字符计 0.5，组合符与控制字符计 0。整列最大值 `≤10` 时保持紧凑，`>10` 时按 `min(48, max(16, 4 × ceil((最大视觉单位 + 2) / 4)))em` 分档加宽；超过 48em 容量后在加宽列内换行，原文不得截断、省略或隐藏，隐藏来源说明不参与计宽。
- 内容密集表格：5 列以上或 4 列且存在加宽列时进入宽表，14 列以上进入密集表；屏幕端横向滚动只允许发生在键盘可达的表格容器，页面根级不得横向溢出，打印端取消动态最小列宽并恢复自适应换行。
- Golden 1–6 均须核对“回到顶部”：唯一 `#report-top` 目标、原生 `href="#report-top"`、无 JavaScript 可用、IntersectionObserver 仅渐进显隐、键盘焦点可见、reduced-motion 生效且打印隐藏。
- 每次行为性修改后用同一批案例改前改后对比；新增失败模式写入 `SKILL.patch.md` 与 Golden Set，再重跑 D05+D12 审计。
- 后续优化计划必须逐项绑定问题、证据等级、改动对象、具体动作、验收方式和风险；证据不足时只补验证，不直接修改行为契约。
