"""验证创建器的入口分流、交付契约和报告版本规则。"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    """按 UTF-8 读取 Skill 内的契约文件。"""
    return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")


def read_json(relative_path: str) -> dict[str, object]:
    """读取并解析 Skill 内的 JSON 文件。"""
    return json.loads(read_text(relative_path))


class CreatorContractTests(unittest.TestCase):
    """每个 Golden 案例对应一个可独立运行的静态契约测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = read_text("SKILL.md")
        cls.guide = read_text("references/5步引导流程.md")
        cls.questionnaire = read_text("references/5问模板.md")
        cls.report_contract = read_text("references/report-editions.md")
        cls.mcp_selection = read_text("references/mcp-selection.md")

    def assert_contains_all(self, text: str, *fragments: str) -> None:
        """一次断言同一契约中的多个必要片段。"""
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_new_skill_full_intake(self) -> None:
        self.assert_contains_all(
            self.skill,
            "新建 skill 时必须按 Q1 到 Q5 顺序推进",
            "| Q1 现有做法 |",
            "| Q2 具体步骤 |",
            "| Q3 方法论 |",
            "| Q4 调用方式 |",
            "| Q5 期望输出 |",
            "5 步结果映射",
        )

    def test_quick_experiment_exception(self) -> None:
        self.assert_contains_all(
            self.skill,
            "快速试验例外",
            "只问 Q2、Q5",
            "结果可能偏空",
            "补齐 Q1、Q3、Q4",
        )

    def test_optimize_existing_skill(self) -> None:
        self.assert_contains_all(
            self.skill,
            "先读取已有 `SKILL.md`、相关 references、scripts 和 README",
            "不要强迫用户重新回答 5 步问题",
            "跨平台兼容",
            "判断目标 Skill 是否交付分析、诊断、监控或运营报告",
        )

    def test_review_without_editing(self) -> None:
        self.assert_contains_all(
            self.skill,
            "**审查已有 skill**",
            "不直接修改，除非用户明确要求实施",
            "用户只要求审查时不直接改文件",
            "优化已有 skill 必须在用户确认实施后编辑",
        )

    def test_negative_one_off_analysis(self) -> None:
        self.assert_contains_all(
            self.skill,
            "不用于一次性业务分析、文件总结或普通代码任务",
            "目标不是替用户做一次分析",
            "且没有要求沉淀为可复用 skill，不要触发本 skill",
        )

    def test_negative_generic_coding(self) -> None:
        self.assert_contains_all(
            self.skill,
            "普通代码任务",
            "如果用户的需求只是一次性写代码",
            "不要使用本 skill",
        )

    def test_mcp_design_without_live_query(self) -> None:
        self.assert_contains_all(
            self.skill,
            "MCP 指南用于指导“新 skill 未来怎么调用工具”",
            "不是要求当前对话立刻调用这些工具",
            "除非用户要现场验证，否则不要为了写 skill 而随意消耗 MCP 查询",
        )

    def test_mcp_advisory_selection(self) -> None:
        self.assert_contains_all(
            self.skill,
            "MCP 选源默认是建议而非强制",
            "mcp_selection_mode=advisory",
            "推荐不等于强制依赖",
            "没有把建议写成全局强制默认源",
        )
        self.assert_contains_all(
            self.mcp_selection,
            "方法版本：`1.6.0`",
            "快照日期：`2026-08-07`",
            "`advisory`",
            "评论原文与 VOC",
            "Sorftime",
            "卖家精灵评论原文",
            "允许用户改选",
        )

    def test_mcp_override_cannot_bypass_hard_gates(self) -> None:
        self.assert_contains_all(
            self.mcp_selection,
            "`user_fixed`",
            "硬门，不能被偏好覆盖",
            "SIF 因静默回落 US 必须阻断",
            "HTTP 成功不能替代站点和字段语义验证",
            "不得生成全局默认源",
            "SECURITY_BLOCKED",
        )
        self.assert_contains_all(
            self.guide,
            "用户已指定来源；保留偏好",
            "不因仪表盘总分、工具数量或品牌印象强制选源",
        )

    def test_eval_requirement(self) -> None:
        self.assert_contains_all(
            self.skill,
            "正常触发",
            "参数缺失",
            "边界场景",
            "客观输出可写断言",
            "`evals/evals.json`",
        )

    def test_review_health_check_full_report(self) -> None:
        self.assert_contains_all(
            self.skill,
            "必须输出完整诊断报告",
            "结论摘要",
            "证据清单",
            "风险排序",
            "ROI 修复清单",
            "待确认执行计划",
            "验证与未运行项",
        )

    def test_low_quality_input_draft_only(self) -> None:
        self.assert_contains_all(
            self.skill,
            "数据质量等级 A/B/C/D",
            "C：只能先生成 skill 草案",
            "D：不应创建 skill",
            "不在用户未确认前执行真实店铺高风险写操作",
        )

    def test_delivery_contract_complete(self) -> None:
        self.assert_contains_all(
            self.skill,
            "Skill 名称、路径、触发场景、不适用场景、输入要求、输出产物、目录结构、核心执行流程",
            "已运行验证、未验证风险和后续迭代点",
            "一个正例、一个反例和一个最小执行验证",
        )

    def test_evidence_chain_and_subagent_boundary(self) -> None:
        self.assert_contains_all(
            self.skill,
            "问题 -> 证据等级 -> 改动对象 -> 动作 -> 验收 -> 风险",
            "未获用户明确确认前不得调用 `spawn_agent`",
            "已启用意图也要评估是否建议取消",
        )

    def test_report_source_and_metric_contract(self) -> None:
        self.assert_contains_all(
            self.skill,
            "新建或优化的目标 Skill 只要产出分析、诊断、监控或运营报告",
            "数据来源表",
            "指标字典",
            "只补问无法确认且会改变报告版本或口径安全的高影响字段",
            "不把整份契约表交给用户填写",
        )
        self.assert_contains_all(
            self.report_contract,
            "`source_id`",
            "来源角色",
            "数据粒度",
            "口径范围",
            "来源追溯",
            "主来源与降级",
            "定义或公式",
            "单位与币种",
            "有效范围",
        )

    def test_report_partial_and_full_enhancement(self) -> None:
        self.assert_contains_all(
            self.skill,
            "基础版报告",
            "增强版报告（部分增强）",
            "增强版报告（完整增强）",
            "module_required",
            "full_required",
            "display_optional",
            "SKIP/MANUAL",
        )
        self.assert_contains_all(
            self.report_contract,
            "至少一个增强模块的全部 `module_required` 有效：输出部分增强",
            "所有声明为 `full_required` 的模块和指标有效：输出完整增强",
            "不参与完整增强判定",
            "三条独立轴",
        )

    def test_report_fallback_security_and_non_report_boundary(self) -> None:
        self.assert_contains_all(
            self.skill,
            "report_edition=auto|basic|enhanced",
            "`auto` 输出带原因的基础版，显式 `enhanced` 阻断",
            "输出基础数据缺口，不生成空壳报告",
            "任何模式都阻断且不得回显敏感值",
            "非报告型产物不进入这套问诊",
            "不建立跨 Skill 共享运行时",
        )
        self.assert_contains_all(
            self.report_contract,
            "私有经营事实，只能来自官方 API、已授权 MCP/ERP、团队可信服务或官方导出文件",
            "不得冒充私有经营数据",
            "在目标 Skill 内生成专用版本路由脚本和单元测试",
        )

    def test_golden_sources_are_synchronized(self) -> None:
        manifest = read_json("references/golden_cases.json")
        evals = read_json("evals/evals.json")
        golden_markdown = read_text("references/golden_set.md")

        cases = manifest["cases"]
        manifest_ids = [case["id"] for case in cases]
        eval_ids = [case["id"] for case in evals["evals"]]
        markdown_ids = [
            int(case_id)
            for case_id in re.findall(r"^## 案例 (\d+)：", golden_markdown, re.MULTILINE)
        ]
        expected_ids = list(range(1, 18))

        self.assertEqual(manifest["version"], 2)
        self.assertEqual(manifest_ids, expected_ids)
        self.assertEqual(eval_ids, expected_ids)
        self.assertEqual(markdown_ids, expected_ids)
        self.assertEqual(
            len({test_id for case in cases for test_id in case["test_ids"]}),
            17,
        )

    def test_version_metadata_is_consistent(self) -> None:
        self.assertIn("_v2.1.0", self.skill)
        self.assertIn("## [2026-08-08] v2.1.0", read_text("SKILL.patch.md"))
        self.assertIn("当前版本：v2.1.0", read_text("README.md"))


if __name__ == "__main__":
    unittest.main()
