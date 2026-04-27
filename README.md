# Amazon Skills

Amazon 运营相关 Claude Code Skills 集合。

## Skills 列表

### amazon-ads-initialization

Amazon 新品广告初始化 Skill，用于把既有广告投放 SOP 转成可执行的 Amazon 新品广告初始化方案。

**功能特性**：
- 结合 SIF MCP 数据判断竞品广告强度、流量趋势和销量趋势
- 输出新品期的预算、Campaign 结构、关键词分组、ASIN 定向
- 支持蓝海/红海判定、生命周期判定、预算比例计算
- 自动生成飞书云文档并归档到专属文件夹

**使用方式**：
```
/amazon-ads-initialization
```

**目录结构**：
```
amazon-ads-initialization/
├── SKILL.md                          # Skill 主文件
├── references/
│   ├── advertising-initialization-rules.md  # 广告初始化规则
│   └── sif-data-map.md                      # SIF MCP 数据映射
├── agents/
│   └── openai.yaml                          # Agent 配置
```

## 安装方式

将 Skill 目录复制到 Claude Code 的 skills 目录：

```bash
# macOS/Linux
cp -r amazon-ads-initialization ~/.claude/skills/

# Windows
cp -r amazon-ads-initialization C:\Users\{用户名}\.claude\skills\
```

## 许可证

MIT License