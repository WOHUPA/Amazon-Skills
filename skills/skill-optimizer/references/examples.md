# Few-shot：优化前后对比范例

> 由 SKILL.md 按需加载。给出「优化前 → 诊断 → 优化后」的黄金范例，照抄结构。

---

## 范例 1：触发描述优化（机制① + 方法 #5）

### ❌ 优化前（触发词埋在后半段，会被截断）
```yaml
description: 这是一个专业的亚马逊广告分析工具，融合了多年运营经验和算法认知，
  能够帮助卖家深入理解广告数据背后的逻辑，经过大量实践验证，可以处理各种复杂场景，
  ……（300 字后才出现）……当用户上传 SP/SB/SD 广告报表时，清洗数据并诊断 ACOS。
```
**诊断**：核心触发场景「上传广告报表→清洗诊断」在 300 字后，超预算会被砍 → 不触发。

### ✅ 优化后（倒金字塔，触发词第一句）
```yaml
description: 清洗并诊断亚马逊 SP/SB/SD 广告报表。当用户上传广告报告 Excel、要求分析广告数据、
  诊断 ACOS、找出单词、识别浪费词、生成否定词建议时触发。输出结构化诊断报告。
  不适用于：广告架构搭建（用 ad-initialization）、Listing 文案（用 listing-generator）。
```
**改了什么**：① 第一句=动作+对象 ② 触发词前置 ③ 加反触发词 ④ 总长压到 8000 内。

---

## 范例 2：把「看情况」变成决策树（模型 4 + 方法 #10）

### ❌ 优化前（模糊指令，输出飘）
```
根据产品情况选择合适的广告策略，新品和成熟品策略不同，灵活调整出价。
```

### ✅ 优化后（显式阈值 + 脚本化计算）
```
## 决策树
IF 上架天数 < 30 AND 订单 < 50 → 走「8 Campaign 冷启动模型」
ELIF 30 ≤ 天数 < 90 → 走「成长期模型」
ELSE → 走「成熟期利润收割模型」

## 出价计算（不交给 LLM，调用脚本）
运行 scripts/calc_bid.py --acos-target 0.25 --cvr 0.08 --aov 29.9
脚本输出建议 bid，禁止 LLM 手算。
```

---

## 范例 3：触发打架根治（机制③ + 方法 #6）

### 场景：`listing-expert` 和 `listing-generator` 总是抢触发

### ✅ 解法（机制层根治，不只是改描述）
1. 定位主次：`listing-generator`=编排器（主），`listing-expert`=被调用能力（次）。
2. 给**次要**的 `listing-expert/agents/openai.yaml` 设：
```yaml
policy:
  allow_implicit_invocation: false   # 只能被 generator 显式调用或 $listing-expert
```
3. `listing-generator` 的 description 明确「编排调度 collector/review/keyword 子 skill」。
**效果**：用户说「写 listing」→ 稳定命中 generator，不再二选一打架。

---

## 范例 4：分层加载防截断（方法 #1）

### ❌ 优化前
单个 SKILL.md 写了 6000 行，含全部阈值表、违禁词清单、范例 → 每次全载，挤占上下文，易截断。

### ✅ 优化后
```
SKILL.md（200 行骨架 + 索引）
├── references/thresholds.md   （阈值表，用到才读）
├── references/banned-words.md （违禁词清单，合规校验时读）
└── references/examples.md     （范例，需参照时读）
```
SKILL.md 里写：「合规校验时读 references/banned-words.md，不要预加载」。

---

## 通用优化模式速记
| 症状 | 一招制敌 |
|------|----------|
| 不触发 | description 倒金字塔，触发词提到第一句 |
| 触发打架 | 次要 skill 设 allow_implicit_invocation:false |
| 输出飘 | 模糊指令→决策树+显式阈值+固定模板 |
| 算错数 | 数学全进 scripts/，禁 LLM 手算 |
| 被截断 | SKILL.md 拆 references，按需加载 |
| 改完退化 | 跑回归测试 + Golden Set 对比 |
