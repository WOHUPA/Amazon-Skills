---
name: amazon-ads-initialization
description: "用于 Amazon 新品广告初始化与 SIF 数据增强广告启动方案。适用于新品广告投放方案、广告初始化、广告投放策略 Skill、SIF MCP 广告数据分析、SP 自动/手动广告结构、ASIN 定向、关键词分组、预算分配，或把广告 SOP 转成可执行初始化方案。"
---

# Amazon 新品广告初始化

这个 skill 用于把既有广告投放 SOP 转成可执行的 Amazon 新品广告初始化方案。核心任务不是泛泛优化广告，而是优先结合 SIF MCP 数据判断竞品广告强度、流量趋势和销量趋势，再输出新品期的预算、Campaign 结构、关键词分组、ASIN 定向和上线前确认清单。

## 必读规则

执行任何广告初始化任务前，必须读取：

- `references/advertising-initialization-rules.md`
- `references/sif-data-map.md`

该文件包含蓝海/红海判定、生命周期判定、预算比例、SP 自动/手动结构、ASIN 定向和初始化执行边界。

## 编码要求

- 本 Skill 及其 `references/`、`agents/` 文件必须保存为 UTF-8 无 BOM。
- Windows PowerShell 查看文件时必须显式使用 `-Encoding UTF8`，否则中文可能被系统默认代码页显示成乱码。
- 启动器若提示编码错误，先检查是否读取了 `D:\codex\02-skills\amazon-ads-initialization` 目录下的 UTF-8 文件，不要读取旧缓存或复制出的乱码副本。
- 不要把终端显示乱码当作规则内容本身；以 UTF-8 读取结果和 `quick_validate.py` 校验结果为准。

## MCP 数据增强

当用户提供 ASIN、关键词、竞品 ASIN 或站点信息时，优先尝试调用 MCP 数据增强；不要只靠用户口述判断。

### SIF MCP 用途

优先按 `references/sif-data-map.md` 中的真实工具目录调用 SIF MCP。核心工具分为四组：

- ASIN 反查与运营数据：
  - `market_get_asin_keyword_signals`
  - `ops_get_asin_traffic_trend_detail`
  - `ops_get_listing_traffic_overview`
  - `ops_get_asin_sales_list`
  - `ops_get_asin_sales_trend`
- 关键词需求与竞争：
  - `market_get_keyword_history`
  - `market_get_keyword_demand`
  - `market_get_keyword_root_trend`
  - `market_get_keyword_competition`
- 广告结构与竞品打法：
  - `ads_get_asin_ad_structure`
  - `ads_get_asin_ad_traffic_trend`
  - `ads_get_asin_ad_feature_profile`
  - `ads_get_asin_ad_historical_feature_profile`
  - `ads_get_asin_campaign_contribution_overview`
- 深度下钻：
  - `ads_get_campaign_structure`
  - `ads_get_campaign_contribution_breakdown`
  - `ads_get_ad_group_keyword_breakdown`

当前 SIF MCP 未在工具 schema 中暴露 CPC、bid、广告竞价或点击成本字段。涉及 CPC/竞价时，必须使用用户提供值、Amazon 广告后台建议竞价，或标注为 `⚠️ SIF 数据缺失`，不得伪造。

### 数据降级规则

- SIF MCP 工具若已作为可直接调用工具暴露，优先直接调用对应工具。
- 若 SIF 工具未直接暴露，但本地 MCP 配置可用，使用 SIF MCP JSON-RPC 兜底：
  - 先调用 `tools/list` 获取真实工具目录。
  - 再通过 `tools/call` 调用 `sif-data-map.md` 中列出的目标工具。
  - 认证信息只从本地 MCP 配置或环境变量读取；不得在回复、日志摘要或输出文件中展示 token。
  - JSON-RPC 兜底仍只调用 SIF MCP，不调用 SellerSprite 或其他第三方数据源。
- SIF MCP 不可用、无数据或缺少 CPC/竞价等字段：标注“⚠️ SIF 数据缺失”，回到用户输入 + 广告 SOP 的纯规则模式。
- 不调用 SellerSprite 或其他第三方数据 MCP，不混用数据口径。
- 纯规则模式下只按广告 SOP 输出初始化模板，不伪造市场、关键词、竞品或广告数据。
- 使用 SIF 广告类工具时，如果工具返回 `render_footer`，最终回复必须保留原文。

## 使用边界

- 聚焦新品广告初始化，默认生命周期为新品期；若用户明确要求推广期或稳定期，再切换对应预算规则。
- 不直接执行真实店铺写操作，不创建真实广告，不改预算，不改竞价。
- 涉及预算上限、库存风险、毛利线、首页溢价、竞品截流等高风险初始化设置时，必须标记“需要人工确认”。
- 只输出广告初始化方案；不要输出上线后的否词、调价、BD+ 优化、ACOS/CVR 优化、每日/每周/每月复盘动作。
- 缺少核心信息时只补问一次；如果用户要求直接输出，缺失字段必须写 `未提供/待确认`，不得随机补全产品信息。
- 只有预算比例、SP 拆分比例这类来自规则公式的结果可以写 `⚠️ 估算`，且必须说明公式来源。

## 广告创建结构硬规则

- 手动关键词广告必须按单元化结构创建：`1 个 Campaign = 1 个广告组 = 1 个关键词`。
- 同一个关键词如果同时使用精准、词组或广泛匹配，必须拆成不同 Campaign，不要放在同一个广告组里。
- SP 自动广告按 `1 个 Campaign = 1 个广告组` 输出，允许在同一个广告组内同时开启紧密匹配、宽泛匹配、同类商品、关联商品四种自动定向。
- ASIN 定向按 `1 个 Campaign = 1 个广告组 = 1 个 ASIN 定向目标` 输出；若多个竞品 ASIN，则逐个拆分。
- 输出 Campaign 结构时必须展示：广告类型、Campaign 名称建议、广告组名称建议、关键词或定向目标、匹配方式、预算占比和用途；SP 自动展示四种自动定向开启状态。

## 固定产品信息字段

每次生成初始化方案前，必须先把用户输入整理成以下固定字段。不得新增随机字段，不得把演示用例、历史测试数据或模型猜测写入产品信息。

| 字段 | 说明 | 缺失时写法 |
|---|---|---|
| 站点 | Amazon 站点，如 US/UK/DE/JP | `未提供，默认按 US 估算需确认` |
| 产品名称 | 产品名称 | `未提供` |
| 目标 ASIN 或 SKU | 目标 ASIN 或 SKU | `未提供` |
| 生命周期阶段 | 新品期/推广期/稳定期 | `未提供，默认新品期需确认` |
| 上架周数 | Listing 上架周数 | `未提供` |
| 评价数 | 当前评价数量 | `未提供` |
| 评分 | 当前星级评分 | `未提供` |
| 目标月销售额 | 目标月销售额 | `未提供` |
| 月广告预算上限 | 月广告预算上限 | `未提供` |
| 日广告预算上限 | 日广告预算上限 | `未提供` |
| 毛利率或毛利金额 | 毛利率或毛利金额 | `未提供` |
| 库存可售天数 | 当前库存预计可售天数 | `未提供` |
| 核心关键词 | 核心关键词列表 | `未提供` |
| 长尾关键词 | 长尾关键词列表 | `未提供` |
| 竞品 ASIN | 竞品 ASIN 列表 | `未提供` |
| 品牌词 | 品牌词 | `未提供` |
| 初始否词候选 | 初始否词候选 | `未提供` |
| 市场类型输入 | 用户给出的蓝海/红海判断或竞争描述 | `未提供` |
| 其他风险约束 | 预算、库存、毛利、品牌授权、禁投词等额外限制 | `未提供` |

固定字段只能来自三类来源：

- `用户输入`：用户明确提供的产品、预算、库存、毛利、关键词、ASIN 等。
- `SIF MCP`：通过 ASIN 或关键词查询得到的市场、关键词、竞品、流量结构等数据。
- `规则推导`：根据广告 SOP 计算出的预算比例和 Campaign 结构。

不得随机生成产品名、ASIN、关键词、竞品、预算、库存、毛利线或评分。若缺少市场类型，按“竞品≤1页为蓝海、竞品＞1页为红海”判断；若仍无法判断，输出蓝海版和红海版两套初始化结构，并提示需要人工选择。

## 工作流程

1. 判断市场类型：蓝海走拓流优先，红海走精准卡位。
   - 有竞品 ASIN 时，先用 SIF 判断竞品广告投放强度、流量结构、销量趋势和反查关键词。
   - 只有关键词、没有 ASIN 时，调用 SIF 关键词需求与竞争工具；如果 SIF 不可用，再根据用户描述和 SOP 规则输出 `⚠️ 估算` 判断。
2. 判断生命周期：新品期、推广期、稳定期；本 skill 默认以新品期初始化为主。
   - 有目标 ASIN 时，结合销量趋势、上架时间、评价数和广告依赖度判断。
3. 设定预算基线：新品期总预算和 SP 占比先行，再按市场类型拆分。
4. 生成 Campaign 结构：SP 自动、SP 手动、ASIN 定向是否开启。
5. 生成关键词初始化：核心词、长尾词、竞品词、匹配方式和初始否词边界。
6. 标记上线前人工确认项：预算上限、库存、毛利线、首页溢价和高风险定向。

## 固定输出结构

输出必须使用以下结构：

1. `一、初始化结论`
2. `二、输入信息与关键假设`
3. `三、SIF MCP 数据摘要`
4. `四、产品判定`
5. `五、预算分配`
6. `六、Campaign 初始化结构`
7. `七、关键词与 ASIN 定向`
8. `八、初始化前检查清单`
9. `九、人工确认项`
10. `十、初始化执行清单`

## 输出要求

- 预算必须给出比例和拆分逻辑，不要只说”建议增加预算”。
- Campaign 必须拆到广告类型、广告组、匹配方式和用途；手动关键词和 ASIN 定向按”1 个 Campaign = 1 个广告组 = 1 个关键词或 1 个定向目标”，SP 自动允许四种自动定向开在同一个广告组。
- 关键词必须区分核心词、长尾词、竞品词、品牌词和初始否词候选；不要按投放后表现划分优质词、潜力词、低效词、无效词。
- `二、输入信息与关键假设` 必须使用固定产品信息字段表输出，缺失字段写 `未提供/待确认`，不得随机补全。
- 每条建议必须能追溯到规则来源，使用”依据：...”简短说明。
- 使用 MCP 数据时必须写明数据来源：SIF MCP、用户输入或纯规则模式。
- 对不确定数据使用 `⚠️ 估算`，不要伪装成确定结论。
- 输出应面向卖家执行，不写成理论解释。

## 飞书云文档输出

完成广告初始化方案后，必须同时生成两个输出：

1. **本地 MD 文档**：保存到用户工作目录，便于本地存档和后续编辑
2. **飞书云文档**：通过 `lark-cli` 创建并移动到专属文件夹，便于团队协作与在线分享

### 文档创建流程

1. **生成本地 MD 文档**：
   - 文件名格式：`Amazon-Ads-Init-{ASIN}-{日期}.md`
   - 保存路径：用户当前工作目录
   - 内容：完整初始化方案（一到十全部章节）

2. **检查并创建飞书文件夹**：
   - 文件夹名称：`Amazon广告初始化方案`
   - 文件夹位置：飞书云空间根目录
   - 使用 `lark-cli drive files list` 检查文件夹是否已存在
   - 若不存在，使用 `lark-cli drive +create-folder --name “Amazon广告初始化方案” --as user` 创建
   - 记录文件夹 token 供后续文档移动使用

3. **创建飞书云文档**：
   - 使用 `lark-cli docs +create` 将 MD 内容创建为飞书云文档
   - 文档标题：`Amazon 新品广告初始化方案 - {ASIN} - {日期}`
   - 文档权限：默认以用户身份创建，文档归属用户

4. **移动文档到文件夹**：
   - 使用 `lark-cli drive +move` 将新创建的文档移动到「Amazon广告初始化方案」文件夹
   - 参数：`--file-token {文档token} --folder-token {文件夹token} --type docx --as user`

### 文档格式要求

- 使用飞书云文档支持的 Markdown 格式
- 表格使用飞书表格组件（`| 列1 | 列2 |` 格式）
- 标题使用飞书标题组件（`# 一级标题`、`## 二级标题`）
- 重要提示使用飞书高亮组件（`**文本**` 加粗）
- 警告标记使用飞书提示组件

### 调用方式

**⚠️ 重要**：`lark-cli docs +create` 的 `--markdown` 参数必须传入 Markdown 内容字符串，不能直接传入文件路径。

**正确调用方式**：

```bash
# 方式1：从文件读取内容后传入（推荐）
lark-cli docs +create --title “标题” --markdown “$(cat '文件路径.md')” --as user

# 方式2：直接传入内容字符串
lark-cli docs +create --title “标题” --markdown “## 正文内容\n\n段落...” --as user
```

**错误方式**（会导致文档内容为空）：
```bash
# ❌ 错误：直接传入文件路径作为参数值
lark-cli docs +create --title “标题” --markdown “文件路径.md” --as user
```

### 文件夹管理命令

```bash
# 创建文件夹（若不存在）
lark-cli drive +create-folder --name “Amazon广告初始化方案” --as user

# 列出根目录文件（检查文件夹是否存在）
lark-cli drive files list --page-all --format table --as user --params '{“folder_token”:””}'

# 移动文档到文件夹
lark-cli drive +move --file-token “{文档token}” --folder-token “{文件夹token}” --type docx --as user
```

### 输出检查清单

完成飞书云文档输出后，必须确认：

- ✓ 本地 MD 文档已保存到用户工作目录
- ✓ 飞书云文档已创建成功
- ✓ 飞书云文档已移动到「Amazon广告初始化方案」文件夹
- ✓ 向用户返回文件夹链接和文档链接
