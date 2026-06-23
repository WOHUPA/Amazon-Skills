# Amazon Skills

Amazon Skills 是一组面向 Amazon 运营、广告投放和 Skill 工程化的 Claude Code / Codex Skills 集合。它把高频运营 SOP、数据判断逻辑、广告结构设计方法和 Skill 质量治理流程沉淀成可复用的智能体能力，让复杂工作从“临场发挥”变成“按流程输入、按标准交付、可复验迭代”。

这个仓库适合用于：

- Amazon 新品广告初始化、广告结构规划、关键词分组和预算分配。
- 将成熟运营 SOP 固化成可复用 Skill，减少人工重复判断。
- 对已有 Skill 做体检、优化、触发冲突审计和回归验证。
- 构建更稳定的 Codex / Claude Code 工作流，让输出格式、执行步骤和验收标准更一致。

## 仓库定位

本仓库不是零散提示词合集，而是可安装、可维护、可迭代的 Skill 工程仓库。每个 Skill 都尽量遵循以下原则：

- **任务边界清晰**：明确什么场景该触发、什么场景不该触发。
- **输入输出明确**：写清用户需要提供什么，最终会得到什么结果。
- **流程可执行**：把专家经验拆成步骤、判断条件、模板和脚本。
- **结果可复验**：关键计算、质量检查和回归验证尽量脚本化。
- **适合长期维护**：方法论、模板、案例、脚本分层存放，避免把所有内容塞进一个文件。

## Skills 一览

| Skill | 主要用途 | 适合场景 |
| --- | --- | --- |
| `amazon-ads-initialization` | Amazon 新品广告初始化方案 | 新品 launch、广告结构设计、预算与关键词规划 |
| `skill-optimizer` | Skill 体检、优化和回归治理 | Skill 不触发、触发打架、输出不稳定、需要系统升级 |

## amazon-ads-initialization

Amazon 新品广告初始化 Skill，用于把既有广告投放 SOP 转成可执行的新品广告初始化方案。它面向 Amazon 卖家的新品期广告搭建，重点解决“预算怎么分、Campaign 怎么建、关键词怎么分层、ASIN 定向怎么选、不同竞争强度下如何启动”的问题。

### 能解决什么问题

- 新品期不知道该用什么广告结构启动。
- 预算有限，需要按蓝海 / 红海、生命周期和竞争强度分配预算。
- 关键词、竞品 ASIN、Campaign 和广告组之间缺少清晰映射。
- 需要把 SIF 等外部数据转成可落地的广告初始化方案。
- 团队希望减少人工经验差异，让新品投放方案有统一标准。

### 功能特性

- 结合 SIF MCP 数据判断竞品广告强度、流量趋势和销量趋势。
- 输出新品期预算、Campaign 结构、关键词分组和 ASIN 定向建议。
- 支持蓝海 / 红海判定、生命周期判定和预算比例计算。
- 自动生成飞书云文档并归档到专属文件夹。
- 把广告初始化规则和 SIF 数据映射拆分到 `references/`，便于后续维护。

### 典型输入

- 目标 ASIN 或竞品 ASIN。
- 目标站点、品类、预算范围和新品阶段。
- SIF MCP 可用的数据上下文。
- 已有广告 SOP 或团队内部投放规则。

### 典型输出

- 新品广告初始化方案。
- Campaign / Ad Group / Keyword / Product Targeting 结构建议。
- 预算分配与投放优先级。
- 蓝海 / 红海与生命周期判断依据。
- 可归档的飞书云文档。

### 使用方式

```text
/amazon-ads-initialization
```

### 目录结构

```text
amazon-ads-initialization/
├── SKILL.md                          # Skill 主文件
├── references/
│   ├── advertising-initialization-rules.md  # 广告初始化规则
│   └── sif-data-map.md                      # SIF MCP 数据映射
├── agents/
│   └── openai.yaml                          # Agent 配置
```

## skill-optimizer

Skill 体检与优化 Skill，用于诊断、优化、升级和改善 Codex Skill 的触发质量、输出稳定性、上下文预算、评测回归与安全边界。它适合用来治理整个 Skill 体系，尤其适合处理“Skill 不触发、触发打架、输出太飘、报告不完整、脚本缺失、改完没法验证”等长期维护问题。

### 能解决什么问题

- Skill description 太长或触发词不前置，导致不触发。
- 多个 Skill 触发语义重叠，导致误触发或抢触发。
- `SKILL.md` 过长，把方法论、案例、模板全部塞在一起。
- 输出报告每次格式不一致，缺少强制字段和验收口径。
- 缺少 Golden Set、回归测试和改前改后对比。
- 涉及真实写操作、权限、敏感信息或外部发布时边界不清。
- 想把某套方法论升级成可安装、可维护、可复验的 Skill。

### 功能特性

- 输出完整 Skill 体检报告，覆盖维度得分、红线项、触发审计、安全与稳定性专项审计。
- 支持 `health_check.py` 文本报告、JSON 报告与跨 Skill 触发冲突审计。
- 内置优化方法论、检查清单、诊断报告模板、Patch 模板和 Golden Set。
- 强制“先体检、再形成待确认优化计划、确认后修改、复验并沉淀”的闭环。
- 把确定性检查脚本化，避免靠人工手算 description 字符数、触发重叠和目录完整性。
- 支持对单个 Skill 做体检，也支持对整个 skills 根目录做触发冲突审计。

### 标准工作流

```text
锁定优化维度
→ 读取目标 Skill 结构
→ 运行 health_check.py / audit_description.py
→ 输出完整体检报告
→ 生成待确认优化计划
→ 用户确认后再修改文件
→ 复验文本报告、JSON 报告和触发冲突
→ 将关键经验沉淀到 SKILL.patch.md 或 Golden Set
```

### 典型输入

- 一个 Skill 目录路径。
- 一份 `SKILL.md` 全文或片段。
- 一句症状描述，例如“这个 skill 不触发”“输出太飘”“给这个 skill 做体检”。
- 一份准备 Skill 化的方法论、SOP 或业务文档。

### 典型输出

- 完整 Skill 诊断报告。
- 维度得分表、红线项、触发审计和安全专项审计。
- 按 ROI 排序的待优化清单。
- 待用户确认的系统化执行计划。
- 修改后的复验结果和沉淀记录。

### 使用方式

```text
/skill-optimizer
```

### 常用脚本

```bash
# 文本体检报告
python scripts/health_check.py path/to/skill

# JSON 体检报告
python scripts/health_check.py path/to/skill --format json

# 跨 Skill 触发冲突审计
python scripts/health_check.py path/to/skill --skills-root path/to/skills-root

# 扫描整个 skills 根目录的 description 预算与触发重叠
python scripts/audit_description.py path/to/skills-root
```

### 目录结构

```text
skill-optimizer/
├── SKILL.md                          # Skill 主文件
├── SKILL.patch.md                    # 演进记录
├── references/                       # 方法论、机制、检查清单、案例和 Golden Set
├── scripts/                          # 体检与触发审计脚本
├── assets/                           # 报告、Patch 和 Agent 配置模板
├── agents/
│   └── openai.yaml                   # Agent 配置
```

## 安装方式

按你使用的客户端选择对应目录，将需要的 Skill 文件夹复制进去即可。

### 安装到 Codex

```bash
# macOS/Linux
cp -r skill-optimizer ~/.codex/skills/
cp -r amazon-ads-initialization ~/.codex/skills/

# Windows PowerShell
Copy-Item -Recurse skill-optimizer $env:USERPROFILE\.codex\skills\
Copy-Item -Recurse amazon-ads-initialization $env:USERPROFILE\.codex\skills\
```

### 安装到 Claude Code

```bash
# macOS/Linux
cp -r skill-optimizer ~/.claude/skills/
cp -r amazon-ads-initialization ~/.claude/skills/

# Windows PowerShell
Copy-Item -Recurse skill-optimizer $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse amazon-ads-initialization $env:USERPROFILE\.claude\skills\
```

## 推荐使用方式

1. 先把具体业务 Skill 安装到本地 skills 目录。
2. 遇到输出不稳定、触发不准、上下文过长或规则漂移时，使用 `skill-optimizer` 做体检。
3. 对体检报告中的高优先级问题进行修改。
4. 修改后再次运行体检脚本和触发冲突审计。
5. 将新规则、踩坑和修复经验写入对应 Skill 的 `SKILL.patch.md`。

## 维护约定

- 新增 Skill 时，优先采用 `SKILL.md` + `references/` + `scripts/` + `assets/` + `agents/` 的结构。
- `SKILL.md` 只保留触发说明、主流程、资源索引和关键边界，长方法论放到 `references/`。
- 涉及确定性计算、批量清洗、格式转换和质量检查时，优先放到 `scripts/`。
- 涉及固定输出格式时，优先放到 `assets/` 模板中。
- 每次实质性升级后，建议使用 `skill-optimizer` 重新体检并记录演进。

## 微信公众号

<img src="docs/images/wechat-official-account-qrcode.jpg" alt="微信公众号二维码" width="400" height="400" />

公众号内容聚焦 `亚马逊跨境电商 + AI` 的实战结合，持续分享两类内容：一类是围绕选品、广告、流量、内容生产、自动化提效等场景的深度文章；另一类是围绕 Codex、Claude Code、Amazon 运营工作流和相关工具链的开源项目发布、迭代记录与落地经验。

这里会更强调“能直接拿来用”的内容，而不只是概念讨论，更新方向通常包括：

- 亚马逊运营与 AI 结合的实战方法、流程拆解和案例复盘。
- 广告投放、关键词策略、数据分析、内容生成等场景的提效思路。
- 与跨境电商相关的 AI Agent、Skill、自动化脚本和开源项目发布。
- 项目更新日志、使用说明、踩坑记录和工作流优化经验。

如果你也在关注 Amazon 跨境电商、AI 提效和可复用的运营工具，欢迎扫码关注，一起跟进最新文章和项目更新。

## 许可证

MIT License
