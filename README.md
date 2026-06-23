# Amazon Skills

Amazon 运营及 Skill 工程相关 Claude Code / Codex Skills 集合。

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

### skill-optimizer

Skill 体检与优化 Skill，用于诊断、优化、升级和改善 Codex Skill 的触发质量、输出稳定性、上下文预算、评测回归与安全边界。

**功能特性**：
- 输出完整 Skill 体检报告，覆盖维度得分、红线项、触发审计、安全与稳定性专项审计
- 支持 `health_check.py` 文本报告、JSON 报告与跨 Skill 触发冲突审计
- 内置优化方法论、检查清单、诊断报告模板、Patch 模板和 Golden Set
- 强制“先体检、再形成待确认优化计划、确认后修改、复验并沉淀”的闭环

**使用方式**：
```
/skill-optimizer
```

**目录结构**：
```
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

将 Skill 目录复制到 Claude Code 的 skills 目录：

```bash
# macOS/Linux
cp -r amazon-ads-initialization ~/.claude/skills/
cp -r skill-optimizer ~/.codex/skills/

# Windows
cp -r amazon-ads-initialization C:\Users\{用户名}\.claude\skills\
cp -r skill-optimizer C:\Users\{用户名}\.codex\skills\
```

## 许可证

MIT License
