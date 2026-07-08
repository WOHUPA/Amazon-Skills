# SKILL.patch.md

## 2026-07-08 - 安全边界与触发评测链修复

### 背景

`skill-optimizer` 体检发现本 skill 的 Amazon 数据源降级边界还不够明确，人工复核又发现触发评测脚本使用 `query/should_trigger` schema，而 `evals/evals.json` 是人工评审 schema，直接用于 `run_eval.py` 会失败。

### 已修复

- 在 `SKILL.md` 沟通规则中补充 Amazon 数据源降级分层：公开前台、竞品和 SellerSprite/SIF/Sorftime 市场数据可降级但必须标注口径；自己店铺后台、广告、订单、库存、财务、结算数据只能用官方 API、MCP、团队可信服务或官方导出文件，不能用浏览器、视觉或截图兜底。
- 新增 `evals/trigger-evals.json`，专供 `scripts/run_eval.py` 和 `scripts/run_loop.py` 做 description 触发评测。
- 在 `references/schemas.md` 明确区分 `evals/evals.json` 的人工评审 schema 与 `evals/trigger-evals.json` 的触发评测 schema。
- 在 `SKILL.md` 的测试与完成定义中更新回归说明，避免再把人工评审用例直接喂给触发评测脚本。
- 修复 `scripts/run_eval.py` 在 Windows 下直接调用 `claude` 失败的问题：先用 `shutil.which("claude")` 解析真实 CLI shim，再交给子进程执行。
- 修复 `scripts/run_eval.py` 的触发误判：忽略 Claude Code `system/init` 事件里的 slash command 清单，只把后续事件中的命令名视为实际触发信号。
- 增加 Claude Code stream-json 错误提取：遇到模型不可用、API 失败等 `is_error` 结果时显式警告，避免把外部模型配置问题误读为 description 触发失败。

### 验证方式

- 运行 `python scripts/quick_validate.py <skill目录>`。
- 运行 `skill-optimizer` 文本体检、JSON 体检和同根目录触发冲突审计。
- 使用 `evals/trigger-evals.json` 跑一次触发评测入口；若外部 `claude` CLI 或认证不可用，则记录为外部依赖限制。

### 本轮验证结果

- `quick_validate.py` 通过。
- `skill-optimizer` JSON 体检通过：`100/100`，A，`WARN=0`，`FAIL=0`，`SKIP=0`。
- `scripts/run_eval.py` 已能读取 `evals/trigger-evals.json` 并显式报告 Claude Code stream-json 错误；本机 Claude Code 当前默认模型返回 `model_not_found`，因此真实触发率评测仍需先修复外部模型配置后重跑。

## 2026-06-30 - 接入 Skill 创建方法论质量门

### 背景

根据 `skill-creation-methodology.md` 复核后发现，本 skill 已能完成 5 步引导、业务模板分流和评测回归，但创建前质量分级、证据链、完整交付契约、子 agent 委派边界和基础校验脚本仍有缺口。

### 已修复

- 在 `SKILL.md` 新增创建前数据质量等级 A/B/C/D，覆盖任务稳定性、输入完整性、输出明确性、边界、工具、安全和验证可行性。
- 在审查 / 优化输出中加入证据等级和证据链要求：`问题 -> 证据等级 -> 改动对象 -> 动作 -> 验收 -> 风险`。
- 增加弱证据护栏：弱证据或冲突证据只能补验证、降级建议或请求确认，不能直接支撑高风险修改。
- 增加子 agent 边界：默认不启用；未获用户明确确认前不得调用 `spawn_agent`，已启用意图也要评估可用性和是否建议取消启动。
- 扩展完成定义，要求交付包含 Skill 名称、路径、触发 / 反触发、输入输出、目录结构、核心流程、验证、风险和后续迭代点。
- 更新 `references/5步引导流程.md`、`references/golden_set.md` 和 `evals/evals.json`，新增质量不足、完整交付契约、证据链与子 agent 边界回归案例。
- 修复 `scripts/quick_validate.py` 对 PyYAML 的硬依赖；没有 PyYAML 时使用轻量 frontmatter 解析器。

### 验证方式

- 直接运行 `python scripts/quick_validate.py <skill目录>`，确认不依赖 PyYAML 也能校验当前 skill。
- 运行 `skill-optimizer` 文本体检、JSON 体检和同根目录触发冲突审计，确认 WARN 收敛。
- 解析 `evals/evals.json`，确认新增案例合法且案例数量符合 golden set。

## 2026-06-17 - 审查体检输出加固

### 背景

`skill-optimizer` 复检发现本 skill 已达到 99/100，但“输出稳定性”里仍缺少审查 / 体检场景的完整报告硬性规则，容易退化成只给总分、评级或几条泛泛建议。

### 已修复

- 在 `SKILL.md` 增加“审查 / 体检输出规范”，要求 review、审查、诊断或体检已有 skill 时输出完整诊断报告。
- 明确完整诊断报告至少包含结论摘要、证据清单、风险排序、ROI 修复清单、待确认执行计划、验证与未运行项。
- 在沟通规则中补充最小权限和敏感信息边界：只读取任务必要文件，不要求无关账号 / token / 客户数据，报告中不得暴露密钥或客户敏感信息。
- 在 `references/golden_set.md` 和 `evals/evals.json` 增加第 9 个回归案例，覆盖“只体检不编辑”的完整报告输出要求。

### 验证方式

- 重新运行 `skill-optimizer` 的文本体检、JSON 体检和同根目录触发冲突审计。
- 运行 `quick_validate.py`，确认 frontmatter、引用和 Markdown 基本结构仍有效。

## 2026-06-17 - 体检修复

### 背景

`skill-optimizer` 体检发现本 skill 无红线项，但存在评测回归、触发路由、确定性规则和沉淀记录方面的 WARN。

### 已修复

- 收窄 `description`：首句改为“创建、优化、审查或评测可复用 Codex skill”，减少与一次性选品、广告、关键词分析类 skill 的触发重叠。
- 新增 `agents/openai.yaml`：补充 Codex 元数据、隐式触发策略和可选 MCP 依赖声明。
- 新增 `evals/evals.json`：沉淀 8 个 Golden Set 案例，覆盖新建、快速试验、优化、审查、误触发负例、MCP 设计和评测补齐。
- 新增 `references/golden_set.md`：用 `## 案例` 标题保留人工可读基准，便于健康检查和人工审查同时识别。
- 在 `SKILL.md` 增加确定性规则：字符数、触发词重叠、评测通过率、benchmark 汇总、JSON 格式校验等确定性计算必须脚本化。
- 增加回归要求：触发或路由优化时复用 `evals/evals.json`，新增误触发案例要先沉淀再回归。

### 后续观察

- 若后续仍与更专业的选品、广告、评论或关键词 skill 抢触发，优先继续压缩本 skill 的业务词，只保留“把流程沉淀为 skill”的触发语义。
- 每次新增场景或发现误触发，先补 `evals/evals.json`，再运行健康体检和触发审计。
