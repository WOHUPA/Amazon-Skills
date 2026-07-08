#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
health_check.py —— 对单个 Codex Skill 做「完整维度报告 + 红线项 + ROI 修复建议」体检。

用法:
  python health_check.py <skill目录>
  python health_check.py <skill目录> --format json
  python health_check.py <skill目录> --skills-root <skills根目录>

设计原则:
  1. 总分仍为 100 分，但拆成 11 个维度，避免单一总分掩盖问题。
  2. 红线项不吞掉分数细节，而是在报告顶部单独标记为阻塞。
  3. MANUAL / SKIP 项不计入自动分母，避免把无法机检的质量判断伪装成确定性扣分。
  4. 体检输出必须是完整报告，不能只给总分或评级。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from typing import Any


# Windows 控制台默认 GBK，输出中文和符号时容易崩溃。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


CODEX_BUDGET_PER_SKILL = 1024
FRONTLOAD_WINDOW = 80
TRIGGER_OVERLAP_THRESHOLD = 4

ANTI_TRIGGER_HINTS = ["不适用", "不用于", "不适合", "不要用", "not for", "do not use"]
STOPWORDS = set(
    "的 了 和 与 或 在 是 当 把 对 为 用户 一个 这是 可以 进行 以及 能够 帮助 "
    "a an the to of for and or when use uses using user skill codex with from this that"
    .split()
)

DIMENSIONS: "OrderedDict[str, int]" = OrderedDict(
    [
        ("结构与上下文健康", 12),
        ("触发与路由质量", 16),
        ("任务契约清晰度", 9),
        ("执行流程可操作性", 8),
        ("输出稳定性", 10),
        ("运行稳定性与故障恢复", 10),
        ("工具化与确定性", 8),
        ("评测与回归能力", 10),
        ("沉淀与演进", 5),
        ("安全与边界", 8),
        ("可维护性", 4),
    ]
)

STATUS_ICON = {
    "OK": "OK",
    "WARN": "WARN",
    "FAIL": "FAIL",
    "MANUAL": "MANUAL",
    "SKIP": "SKIP",
}

STATUS_LABEL = {
    "OK": "通过",
    "WARN": "待优化",
    "FAIL": "不合规",
    "MANUAL": "需人工复核",
    "SKIP": "未运行",
}


def read_text(path: str) -> str:
    """按常见编码读取文本，避免 Windows 中文路径和 GBK 内容导致脚本中断。"""
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=encoding) as file:
                return file.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


def parse_frontmatter(content: str) -> dict[str, Any]:
    """提取 YAML frontmatter 的关键字段；不依赖第三方 YAML 库以保持零依赖。"""
    content = content.lstrip("\ufeff")
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {
            "valid": False,
            "frontmatter": "",
            "name": None,
            "description": None,
            "body": content,
        }

    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    desc_match = re.search(
        r"^description:\s*(.*?)(?=\n[a-zA-Z_]+:\s|\Z)",
        frontmatter,
        re.DOTALL | re.MULTILINE,
    )
    description = None
    if desc_match:
        description = re.sub(r"\s+", " ", desc_match.group(1)).strip().strip("\"'")

    return {
        "valid": True,
        "frontmatter": frontmatter,
        "name": name_match.group(1).strip().strip("\"'") if name_match else None,
        "description": description,
        "body": content[match.end():],
    }


def tokenize(text: str) -> set[str]:
    """用轻量中英混合分词检测触发词重叠，避免把重叠判断交给人工手算。"""
    tokens = re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,4}", text)
    return {token.lower() for token in tokens if token.lower() not in STOPWORDS and len(token) >= 2}


def first_sentence(text: str) -> str:
    parts = re.split(r"[。.!！?？\n]", text)
    return parts[0] if parts else text


def has_any(patterns: list[str], text: str, flags: int = re.IGNORECASE) -> bool:
    return any(re.search(pattern, text, flags) for pattern in patterns)


def has_real_write_signal(text: str) -> bool:
    """只把正向真实写操作当作安全风险，避免“不适用于写操作”这类反触发句误报。"""
    write_patterns = [r"直接改", r"写入", r"删除", r"上传", r"发送", r"修改", r"真实"]
    negative_patterns = [r"不适用", r"不用于", r"不涉及", r"禁止", r"不要", r"无需", r"只读"]
    sentences = re.split(r"[。.!！?？\n]", text)
    for sentence in sentences:
        if has_any(write_patterns, sentence) and not has_any(negative_patterns, sentence):
            return True
    return False


def read_reference_markdown(skill_dir: str) -> str:
    references_dir = os.path.join(skill_dir, "references")
    if not os.path.isdir(references_dir):
        return ""

    chunks: list[str] = []
    for file_name in os.listdir(references_dir):
        if file_name.lower().endswith(".md"):
            chunks.append(read_text(os.path.join(references_dir, file_name)))
    return "\n".join(chunks)


def find_referenced_files(body: str) -> list[str]:
    """抽取 Skill 正文中直接点名的强依赖资源路径。"""
    patterns = [
        r"`((?:references|scripts|assets|agents)/[^`]+?)`",
        r"\((?:\.?/)?((?:references|scripts|assets|agents)/[^)\s]+?)\)",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, body):
            clean = match.strip().strip("`").replace("\\", "/")
            if clean not in found:
                found.append(clean)
    return found


def find_skills(root: str) -> list[str]:
    skill_files: list[str] = []
    for dirpath, _, files in os.walk(root):
        for file_name in files:
            if file_name.lower() == "skill.md":
                skill_files.append(os.path.join(dirpath, file_name))
    return skill_files


def detect_trigger_overlaps(skill_dir: str, skill_name: str, description: str, skills_root: str) -> list[dict[str, Any]]:
    target_tokens = tokenize(description)
    overlaps: list[dict[str, Any]] = []

    for skill_path in find_skills(skills_root):
        other_dir = os.path.dirname(skill_path)
        if os.path.abspath(other_dir) == os.path.abspath(skill_dir):
            continue

        parsed = parse_frontmatter(read_text(skill_path))
        other_desc = parsed.get("description") or ""
        other_name = parsed.get("name") or os.path.basename(other_dir)
        shared = sorted(target_tokens & tokenize(other_desc))
        if len(shared) >= TRIGGER_OVERLAP_THRESHOLD:
            overlaps.append(
                {
                    "skill": other_name,
                    "sharedTokens": shared[:10],
                    "count": len(shared),
                    "path": skill_path,
                }
            )

    return overlaps


def make_check(
    checks: list[dict[str, Any]],
    dimension: str,
    item: str,
    status: str,
    max_points: float,
    evidence: str = "",
    recommendation: str = "",
    method: str = "",
    points: float | None = None,
    blocker: bool = False,
    roi: str = "",
) -> None:
    if points is None:
        points = max_points if status == "OK" else 0

    checks.append(
        {
            "dimension": dimension,
            "item": item,
            "status": status,
            "points": round(points, 2),
            "maxPoints": max_points,
            "scored": status not in ("MANUAL", "SKIP"),
            "evidence": evidence,
            "recommendation": recommendation,
            "method": method,
            "blocker": blocker,
            "roi": roi,
        }
    )


def build_missing_skill_report(skill_dir: str, output_format: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    make_check(
        checks,
        "结构与上下文健康",
        "存在 SKILL.md",
        "FAIL",
        15,
        f"未找到 {os.path.join(skill_dir, 'SKILL.md')}",
        "先创建合法的 SKILL.md，否则 Codex 无法识别该 Skill。",
        "#1",
        blocker=True,
        roi="🥇",
    )
    return finalize_report(
        skill_dir=skill_dir,
        skill_name=os.path.basename(skill_dir.rstrip(os.sep)) or skill_dir,
        checks=checks,
        blockers=["缺 SKILL.md"],
        output_format=output_format,
        skills_root=None,
    )


def build_report(skill_dir: str, skills_root: str | None, output_format: str) -> dict[str, Any]:
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return build_missing_skill_report(skill_dir, output_format)

    content = read_text(skill_md)
    parsed = parse_frontmatter(content)
    body = parsed["body"]
    frontmatter = parsed["frontmatter"]
    name = parsed["name"] or os.path.basename(skill_dir)
    description = parsed["description"] or ""
    references_text = read_reference_markdown(skill_dir)
    searchable_text = "\n".join([frontmatter, body, references_text])
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    add_structure_checks(checks, blockers, skill_dir, parsed, body, searchable_text)
    add_trigger_checks(checks, blockers, skill_dir, name, description, searchable_text, skills_root)
    add_contract_checks(checks, searchable_text)
    add_flow_checks(checks, searchable_text)
    add_output_checks(checks, skill_dir, body, references_text, searchable_text)
    add_runtime_stability_checks(checks, searchable_text)
    add_tooling_checks(checks, skill_dir, searchable_text)
    add_evaluation_checks(checks, skill_dir, searchable_text)
    add_iteration_checks(checks, skill_dir, searchable_text)
    add_security_checks(checks, blockers, description, searchable_text)
    add_maintainability_checks(checks, skill_dir, name, body)

    return finalize_report(
        skill_dir=skill_dir,
        skill_name=name,
        checks=checks,
        blockers=blockers,
        output_format=output_format,
        skills_root=skills_root,
    )


def add_structure_checks(
    checks: list[dict[str, Any]],
    blockers: list[str],
    skill_dir: str,
    parsed: dict[str, Any],
    body: str,
    searchable_text: str,
) -> None:
    if not parsed["valid"]:
        blockers.append("frontmatter 无法解析")
    make_check(
        checks,
        "结构与上下文健康",
        "frontmatter 可解析",
        "OK" if parsed["valid"] else "FAIL",
        3,
        "已检测到 YAML frontmatter" if parsed["valid"] else "SKILL.md 开头缺少 --- frontmatter ---",
        "补齐合法 frontmatter，至少包含 name 和 description。",
        "#1",
        blocker=not parsed["valid"],
        roi="🥇",
    )

    if not parsed["name"]:
        blockers.append("缺 name")
    make_check(
        checks,
        "结构与上下文健康",
        "frontmatter 含 name",
        "OK" if parsed["name"] else "FAIL",
        2,
        f"name={parsed['name']}" if parsed["name"] else "未找到 name",
        "补齐 name，确保 Codex 能识别 Skill。",
        "#1",
        blocker=not parsed["name"],
        roi="🥇",
    )

    description = parsed["description"] or ""
    if not description:
        blockers.append("缺 description 或 description 为空")
    make_check(
        checks,
        "结构与上下文健康",
        "frontmatter 含非空 description",
        "OK" if description else "FAIL",
        2,
        f"description {len(description)} 字符" if description else "description 缺失或为空",
        "补齐 description，并把核心触发词放在第一句。",
        "#5",
        blocker=not description,
        roi="🥇",
    )

    has_refs = os.path.isdir(os.path.join(skill_dir, "references"))
    make_check(
        checks,
        "结构与上下文健康",
        "存在 references/ 分层加载",
        "OK" if has_refs else "WARN",
        3,
        "已存在 references/" if has_refs else "未找到 references/",
        "把长方法论、案例和细节拆到 references/，SKILL.md 只保留骨架。",
        "#1",
        roi="🥉",
    )

    body_lines = body.count("\n")
    if body_lines < 300:
        status, points = "OK", 2
    elif body_lines < 500:
        status, points = "WARN", 1
    else:
        status, points = "WARN", 0
    make_check(
        checks,
        "结构与上下文健康",
        "SKILL.md 主体精简",
        status,
        2,
        f"主体约 {body_lines} 行",
        "超过 300 行时优先拆分到 references/，降低上下文截断风险。",
        "#1",
        points=points,
        roi="🥉",
    )

    has_index = has_any([r"资源索引", r"references/", r"scripts/", r"assets/"], searchable_text)
    make_check(
        checks,
        "结构与上下文健康",
        "提供资源索引或分层入口",
        "OK" if has_index else "WARN",
        1.5,
        "检测到资源索引/目录引用" if has_index else "未检测到资源索引",
        "在 SKILL.md 中列出按需加载的 references/scripts/assets。",
        "#1",
    )

    missing_refs = []
    for relative_path in find_referenced_files(body):
        full_path = os.path.join(skill_dir, relative_path.replace("/", os.sep))
        if not os.path.exists(full_path):
            missing_refs.append(relative_path)
    if missing_refs:
        blockers.append(f"强依赖文件缺失：{', '.join(missing_refs[:3])}")
    make_check(
        checks,
        "结构与上下文健康",
        "正文引用的强依赖文件存在",
        "OK" if not missing_refs else "FAIL",
        1.5,
        "未发现缺失引用" if not missing_refs else "缺失：" + ", ".join(missing_refs[:5]),
        "补齐缺失文件，或删除/修正对应路径引用。",
        "#1",
        blocker=bool(missing_refs),
        roi="🥇",
    )


def add_trigger_checks(
    checks: list[dict[str, Any]],
    blockers: list[str],
    skill_dir: str,
    skill_name: str,
    description: str,
    searchable_text: str,
    skills_root: str | None,
) -> None:
    if description:
        desc_len = len(description)
        if desc_len <= CODEX_BUDGET_PER_SKILL:
            length_status, points = "OK", 4
        elif desc_len <= 2048:
            length_status, points = "WARN", 2
        else:
            length_status, points = "WARN", 0
        make_check(
            checks,
            "触发与路由质量",
            "description 长度可控",
            length_status,
            4,
            f"{desc_len} 字符，建议 ≤ {CODEX_BUDGET_PER_SKILL}",
            "压缩 description，把核心触发词和不适用场景前置。",
            "#5",
            points=points,
            roi="🥈",
        )

        sentence = first_sentence(description)
        make_check(
            checks,
            "触发与路由质量",
            "触发词前置",
            "OK" if len(sentence) <= FRONTLOAD_WINDOW else "WARN",
            4,
            f"首句 {len(sentence)} 字符",
            "用倒金字塔写法：第一句直接写“当用户要做什么时使用”。",
            "#5",
            roi="🥈",
        )

        has_trigger_signal = has_any([r"当用户", r"Use when", r"用于", r"触发", r"asks?", r"mentions?"], description)
        make_check(
            checks,
            "触发与路由质量",
            "触发场景表达明确",
            "OK" if has_trigger_signal else "WARN",
            2,
            "检测到触发场景信号" if has_trigger_signal else "description 更像能力介绍，缺少触发句式",
            "补充“当用户提到/要求/提供 X 时使用”。",
            "#5",
        )

        has_anti = any(hint in description.lower() for hint in ANTI_TRIGGER_HINTS)
        make_check(
            checks,
            "触发与路由质量",
            "description 含反触发词",
            "OK" if has_anti else "WARN",
            3,
            "检测到不适用场景" if has_anti else "未检测到不适用/不要用/not for",
            "补充“不适用于...”以降低误触发。",
            "#5",
            roi="🥈",
        )
    else:
        make_check(
            checks,
            "触发与路由质量",
            "description 可用于触发判断",
            "FAIL",
            13,
            "description 缺失",
            "补齐 description 后再做触发审计。",
            "#5",
            blocker=True,
            roi="🥇",
        )

    yaml_path = os.path.join(skill_dir, "agents", "openai.yaml")
    make_check(
        checks,
        "触发与路由质量",
        "存在 agents/openai.yaml",
        "OK" if os.path.isfile(yaml_path) else "WARN",
        3,
        "已存在触发开关/元数据文件" if os.path.isfile(yaml_path) else "未找到 agents/openai.yaml",
        "补充 openai.yaml，触发打架时才能使用 allow_implicit_invocation 等机制层开关。",
        "#6",
        roi="🥈",
    )

    if skills_root:
        if os.path.isdir(skills_root) and description:
            overlaps = detect_trigger_overlaps(skill_dir, skill_name, description, skills_root)
            evidence = "未发现明显触发词重叠"
            if overlaps:
                evidence = "; ".join(
                    f"{item['skill']}({item['count']}词: {', '.join(item['sharedTokens'][:5])})"
                    for item in overlaps[:3]
                )
            make_check(
                checks,
                "触发与路由质量",
                "跨 Skill 触发词冲突审计",
                "OK" if not overlaps else "WARN",
                4,
                evidence,
                "对次要 Skill 设置 allow_implicit_invocation:false，或重写 description 降低重叠。",
                "#6",
                roi="🥈",
            )
        else:
            make_check(
                checks,
                "触发与路由质量",
                "跨 Skill 触发词冲突审计",
                "SKIP",
                4,
                f"skills-root 不存在或 description 缺失：{skills_root}",
                "提供有效 --skills-root 后重新审计。",
                "#6",
            )
    else:
        make_check(
            checks,
            "触发与路由质量",
            "跨 Skill 触发词冲突审计",
            "SKIP",
            4,
            "未传 --skills-root，不纳入自动扣分",
            "如要检查触发打架，运行 health_check.py <skill目录> --skills-root <skills根目录>。",
            "#6",
        )


def add_contract_checks(checks: list[dict[str, Any]], searchable_text: str) -> None:
    has_ipo = has_any([r"IPO\s*契约", r"INPUT", r"OUTPUT", r"输入.*输出"], searchable_text)
    make_check(
        checks,
        "任务契约清晰度",
        "定义 INPUT / OUTPUT 契约",
        "OK" if has_ipo else "MANUAL",
        4,
        "检测到 IPO/INPUT/OUTPUT" if has_ipo else "未检测到明确 IPO 契约",
        "写清用户给什么、Skill 产出什么，便于级联和评测。",
        "#8",
        roi="🥉",
    )

    has_missing_info_policy = has_any([r"缺.*问", r"先问", r"必须先问", r"降级", r"缺.*跳过"], searchable_text)
    make_check(
        checks,
        "任务契约清晰度",
        "缺参/信息不足处理明确",
        "OK" if has_missing_info_policy else "WARN",
        2,
        "检测到缺参处理或降级策略" if has_missing_info_policy else "未检测到缺参处理",
        "说明何时继续、何时提问、何时降级输出。",
        "#8",
    )

    has_deliverable = has_any([r"交付物", r"输出", r"报告", r"模板", r"结果"], searchable_text)
    make_check(
        checks,
        "任务契约清晰度",
        "交付物边界明确",
        "OK" if has_deliverable else "WARN",
        2,
        "检测到交付物/输出描述" if has_deliverable else "未检测到交付物描述",
        "明确最终输出字段、文件、报告或动作。",
        "#8",
    )

    has_scope = has_any([r"不适用", r"不用于", r"范围", r"边界", r"禁止事项"], searchable_text)
    make_check(
        checks,
        "任务契约清晰度",
        "适用范围与排除范围明确",
        "OK" if has_scope else "WARN",
        2,
        "检测到范围/排除说明" if has_scope else "未检测到范围边界",
        "补充适用范围和不适用场景，降低误用。",
        "#5",
    )


def add_flow_checks(checks: list[dict[str, Any]], searchable_text: str) -> None:
    has_sop = has_any([r"SOP", r"步骤", r"流程", r"工作流", r"路径\s*[A-D]", r"第\s*\d+\s*步"], searchable_text)
    make_check(
        checks,
        "执行流程可操作性",
        "存在可执行 SOP / 工作流",
        "OK" if has_sop else "WARN",
        3,
        "检测到 SOP/步骤/路径" if has_sop else "未检测到明确流程",
        "把隐性经验拆成可执行步骤。",
        "#1",
    )

    has_branch = has_any([r"路径\s*[A-D]", r"按.*选", r"如果", r"IF", r"when", r"否则"], searchable_text)
    make_check(
        checks,
        "执行流程可操作性",
        "有场景分支或路径选择",
        "OK" if has_branch else "WARN",
        2,
        "检测到分支/路径选择" if has_branch else "未检测到分支条件",
        "把不同输入和症状映射到不同路径，避免一把梭。",
        "#1",
    )

    has_tree = has_any([r"\bIF\b", r"\bELIF\b", r"if-then", r"决策树", r"阈值", r"≤|>=|<|>|\d"], searchable_text)
    make_check(
        checks,
        "执行流程可操作性",
        "专家判断显性化为决策树/阈值",
        "OK" if has_tree else "MANUAL",
        3,
        "检测到决策树/阈值信号" if has_tree else "需人工判断是否已显性化专家经验",
        "把“看情况”改写成 if-then + 数字阈值。",
        "#1/#4",
        roi="🥉",
    )

    has_fallback = has_any([r"降级", r"fallback", r"错误处理", r"重试", r"跳过", r"失败"], searchable_text)
    make_check(
        checks,
        "执行流程可操作性",
        "失败/异常/降级路径明确",
        "OK" if has_fallback else "WARN",
        2,
        "检测到失败或降级策略" if has_fallback else "未检测到失败处理",
        "说明工具失败、缺权限、缺目录时如何继续。",
        "#11",
    )


def add_output_checks(
    checks: list[dict[str, Any]],
    skill_dir: str,
    body: str,
    references_text: str,
    searchable_text: str,
) -> None:
    has_assets = os.path.isdir(os.path.join(skill_dir, "assets"))
    has_template = has_assets or has_any(
        [r"输出模板", r"诊断报告模板", r"template\.md", r"assets/", r"\{\{[^}]+\}\}", r"\|.+\|.+\|"],
        "\n".join([body, references_text]),
    )
    make_check(
        checks,
        "输出稳定性",
        "有输出模板或 assets/",
        "OK" if has_template else "WARN",
        3,
        "检测到模板/assets" if has_template else "未检测到输出模板",
        "用固定模板和占位符把输出从自由发挥变成填空。",
        "#3",
        roi="🥉",
    )

    has_fewshot = has_any([r"Few-shot", r"few-?shot", r"范例", r"示例", r"输入.*输出", r"优化前.*优化后"], searchable_text)
    make_check(
        checks,
        "输出稳定性",
        "包含 Few-shot / 示例",
        "OK" if has_fewshot else "WARN",
        3,
        "检测到 Few-shot/示例" if has_fewshot else "未检测到示例",
        "补 1-2 个完整输入→输出范例，稳定模型行为。",
        "#2",
    )

    has_negative = has_any([r"反例", r"不要这样", r"不该", r"禁止事项", r"❌", r"优化前"], "\n".join([body, references_text]))
    make_check(
        checks,
        "输出稳定性",
        "包含反例或禁止事项",
        "OK" if has_negative else "WARN",
        2,
        "检测到反例/禁止事项" if has_negative else "未检测到反例",
        "写明不要怎么做，比只写正例更能降低漂移。",
        "#4",
    )

    has_format_constraints = has_any([r"\{\{[^}]+\}\}", r"字段", r"Schema", r"表格", r"JSON", r"格式", r"\|.+\|.+\|"], searchable_text)
    make_check(
        checks,
        "输出稳定性",
        "输出字段/格式约束明确",
        "OK" if has_format_constraints else "WARN",
        2,
        "检测到字段/格式约束" if has_format_constraints else "未检测到格式约束",
        "明确字段、顺序、占位符和可省略项。",
        "#3",
    )

    has_quality_gate = has_any([r"验证", r"回归", r"检查", r"验收", r"质量", r"通过标准"], searchable_text)
    make_check(
        checks,
        "输出稳定性",
        "输出后有质量检查/验收要求",
        "OK" if has_quality_gate else "WARN",
        2,
        "检测到验证/验收要求" if has_quality_gate else "未检测到质量检查",
        "补充输出前后的检查项，确保结果可复核。",
        "#12",
    )

    is_diagnostic_skill = has_any(
        [r"体检", r"诊断", r"审计", r"health[_ -]?check", r"diagnos", r"audit"],
        searchable_text,
    )
    has_complete_report_rule = has_any(
        [r"完整.*体检报告", r"完整.*诊断报告", r"不能只给.*分", r"禁止.*只.*总分", r"禁止.*只.*评级"],
        searchable_text,
    )
    complete_report_status = "OK" if not is_diagnostic_skill or has_complete_report_rule else "FAIL"
    if not is_diagnostic_skill:
        complete_report_evidence = "非诊断/体检类 Skill，不强制完整体检报告结构"
    elif has_complete_report_rule:
        complete_report_evidence = "检测到完整报告硬性要求"
    else:
        complete_report_evidence = "诊断/体检类 Skill 缺少禁止只给分/评级的硬性规则"
    make_check(
        checks,
        "输出稳定性",
        "体检输出强制完整报告",
        complete_report_status,
        2,
        complete_report_evidence,
        "体检类 Skill 必须规定完整报告结构，不能只输出总分、评级或简短建议。",
        "#3/#12",
        blocker=is_diagnostic_skill and not has_complete_report_rule,
        roi="🥇",
    )


def add_runtime_stability_checks(checks: list[dict[str, Any]], searchable_text: str) -> None:
    has_failure_policy = has_any(
        [r"工具失败", r"脚本.*失败", r"缺权限", r"缺文件", r"路径不存在", r"错误处理", r"降级", r"重试", r"跳过"],
        searchable_text,
    )
    make_check(
        checks,
        "运行稳定性与故障恢复",
        "工具失败/缺文件/缺权限有降级策略",
        "OK" if has_failure_policy else "WARN",
        3,
        "检测到失败处理/降级策略" if has_failure_policy else "未检测到工具失败或缺权限的处理路径",
        "说明脚本失败、缺目录、缺文件、缺权限时如何继续诊断并标注未运行项。",
        "#11",
        roi="🥇",
    )

    has_idempotency = has_any(
        [r"可重复", r"重复运行", r"重跑", r"复验", r"回归", r"幂等", r"可回滚", r"备份"],
        searchable_text,
    )
    make_check(
        checks,
        "运行稳定性与故障恢复",
        "支持重复运行/复验/回滚",
        "OK" if has_idempotency else "WARN",
        2,
        "检测到复验/回归/回滚信号" if has_idempotency else "未检测到可重复执行或回滚说明",
        "改动类 Skill 应说明复验命令、回滚方式或重复运行不会造成副作用。",
        "#14/#16",
        roi="🥈",
    )

    has_dependency_notice = has_any(
        [r"依赖", r"前置", r"权限", r"环境", r"脚本", r"MCP", r"外部", r"版本", r"目录路径"],
        searchable_text,
    )
    make_check(
        checks,
        "运行稳定性与故障恢复",
        "依赖与前置条件明确",
        "OK" if has_dependency_notice else "WARN",
        2,
        "检测到依赖/前置条件说明" if has_dependency_notice else "未检测到依赖或前置条件说明",
        "写明需要的目录、脚本、权限、外部工具或认证状态。",
        "#19",
        roi="🥉",
    )

    has_partial_result_policy = has_any(
        [r"MANUAL", r"SKIP", r"未运行", r"需人工复核", r"不计入", r"标注", r"证据"],
        searchable_text,
    )
    make_check(
        checks,
        "运行稳定性与故障恢复",
        "部分失败或未运行项可见",
        "OK" if has_partial_result_policy else "WARN",
        2,
        "检测到 MANUAL/SKIP/未运行标注规则" if has_partial_result_policy else "未检测到部分失败的显式标注",
        "不能静默忽略未运行检查；必须在报告中列出 MANUAL / SKIP 与原因。",
        "#11/#12",
    )

    has_recovery_boundary = has_any(
        [r"回滚", r"备份", r"恢复", r"失败恢复", r"可回滚", r"changelog", r"版本号"],
        searchable_text,
    )
    make_check(
        checks,
        "运行稳定性与故障恢复",
        "改动失败有恢复路径",
        "OK" if has_recovery_boundary else "MANUAL",
        1,
        "检测到备份/回滚/版本记录" if has_recovery_boundary else "需人工判断该 Skill 是否涉及写操作",
        "如果 Skill 会改文件、发消息、上传或删除，必须说明失败后如何恢复。",
        "#16",
    )


def add_tooling_checks(checks: list[dict[str, Any]], skill_dir: str, searchable_text: str) -> None:
    scripts_dir = os.path.join(skill_dir, "scripts")
    python_scripts = []
    if os.path.isdir(scripts_dir):
        python_scripts = [name for name in os.listdir(scripts_dir) if name.endswith(".py")]
    has_scripts = bool(python_scripts)
    needs_scripts = has_any([r"计算", r"统计", r"出价", r"预算", r"格式转换", r"批量", r"字符数", r"重叠"], searchable_text)

    if has_scripts:
        status, points = "OK", 4
        evidence = f"{len(python_scripts)} 个 Python 脚本"
    elif needs_scripts:
        status, points = "WARN", 0
        evidence = "文本提到计算/统计/批量，但无 scripts/"
    else:
        status, points = "MANUAL", 0
        evidence = "纯指令 Skill 可能无需脚本，需人工判断"
    make_check(
        checks,
        "工具化与确定性",
        "确定性计算已脚本化",
        status,
        4,
        evidence,
        "涉及数学、统计、格式转换或批量处理时放入 scripts/。",
        "#10",
        points=points,
        roi="🥉",
    )

    usage_docs = 0
    robust_scripts = 0
    if has_scripts:
        for file_name in python_scripts:
            script_text = read_text(os.path.join(scripts_dir, file_name))
            if "用法" in script_text or "usage" in script_text.lower() or "argparse" in script_text:
                usage_docs += 1
            if "encoding" in script_text and ("try" in script_text or "errors=" in script_text):
                robust_scripts += 1

    make_check(
        checks,
        "工具化与确定性",
        "脚本有用法说明或 CLI 参数",
        "OK" if has_scripts and usage_docs else ("MANUAL" if not has_scripts else "WARN"),
        2,
        f"{usage_docs}/{len(python_scripts)} 个脚本含用法说明" if has_scripts else "无脚本",
        "给脚本补 usage/argparse/docstring，降低维护成本。",
        "#11",
    )

    make_check(
        checks,
        "工具化与确定性",
        "脚本处理编码/路径等健壮性",
        "OK" if has_scripts and robust_scripts else ("MANUAL" if not has_scripts else "WARN"),
        2,
        f"{robust_scripts}/{len(python_scripts)} 个脚本处理编码/异常" if has_scripts else "无脚本",
        "至少处理 UTF-8/GBK、路径不存在、参数错误。",
        "#11",
    )

    has_no_llm_math_rule = has_any([r"数学不交给 LLM", r"不交给 LLM", r"脚本化", r"确定性计算"], searchable_text)
    make_check(
        checks,
        "工具化与确定性",
        "明确不让 LLM 手算确定性逻辑",
        "OK" if has_no_llm_math_rule or not needs_scripts else "WARN",
        2,
        "检测到脚本化/不手算规则" if has_no_llm_math_rule else "未检测到不手算规则",
        "把数字、字符数、重叠、格式转换等确定性逻辑交给脚本。",
        "#10",
    )


def add_evaluation_checks(checks: list[dict[str, Any]], skill_dir: str, searchable_text: str) -> None:
    references_dir = os.path.join(skill_dir, "references")
    golden_files: list[str] = []
    if os.path.isdir(references_dir):
        golden_files = [
            file_name
            for file_name in os.listdir(references_dir)
            if re.search(r"golden|eval|fixture|基准", file_name, re.IGNORECASE)
        ]
    has_golden = bool(golden_files)
    make_check(
        checks,
        "评测与回归能力",
        "存在 Golden Set / 评测基准",
        "OK" if has_golden else "WARN",
        4,
        "检测到 " + ", ".join(golden_files) if has_golden else "未找到 golden/eval/fixture 基准文件",
        "补 5-10 个真实案例 + 期望诊断，形成回归闭环。",
        "#12",
        roi="🥇",
    )

    has_eval_process = has_any([r"eval", r"评测", r"回归测试", r"改前改后", r"对比"], searchable_text)
    make_check(
        checks,
        "评测与回归能力",
        "说明 eval / 回归流程",
        "OK" if has_eval_process else "WARN",
        3,
        "检测到 eval/回归流程" if has_eval_process else "未检测到回归流程",
        "写清改前改后如何跑同批案例对比。",
        "#12/#14",
        roi="🥇",
    )

    has_acceptance = has_any([r">=\s*\d+", r"≥\s*\d+", r"\d+\s*分", r"通过标准", r"验收"], searchable_text)
    make_check(
        checks,
        "评测与回归能力",
        "有量化验收指标",
        "OK" if has_acceptance else "WARN",
        2,
        "检测到量化验收/通过标准" if has_acceptance else "未检测到量化验收",
        "补充最低分、命中率或必须命中的诊断项。",
        "#12",
    )

    case_count = len(re.findall(r"^##\s*案例", searchable_text, re.MULTILINE))
    if case_count >= 5:
        status, points = "OK", 3
    elif case_count > 0:
        status, points = "WARN", 1.5
    else:
        status, points = "WARN", 0
    make_check(
        checks,
        "评测与回归能力",
        "评测案例覆盖足够",
        status,
        3,
        f"检测到 {case_count} 个案例标题",
        "至少覆盖健康对照、触发问题、结构缺失、模板缺失、回归能力缺失。",
        "#12",
        points=points,
    )


def add_iteration_checks(checks: list[dict[str, Any]], skill_dir: str, searchable_text: str) -> None:
    has_patch = os.path.isfile(os.path.join(skill_dir, "SKILL.patch.md"))
    make_check(
        checks,
        "沉淀与演进",
        "存在 SKILL.patch.md",
        "OK" if has_patch else "WARN",
        2,
        "已存在 SKILL.patch.md" if has_patch else "未找到 SKILL.patch.md",
        "把踩坑、修复、版本演进写入 SKILL.patch.md。",
        "#15",
    )

    has_version = has_any([r"v\d+\.\d+", r"版本", r"version", r"changelog"], searchable_text)
    make_check(
        checks,
        "沉淀与演进",
        "包含版本号或 changelog",
        "OK" if has_version else "WARN",
        2,
        "检测到版本/变更记录" if has_version else "未检测到版本记录",
        "在 SKILL.md 或 SKILL.patch.md 中记录版本和变更。",
        "#16",
    )

    has_feedback = has_any([r"反馈", r"PDCA", r"沉淀", r"迭代", r"失败案例"], searchable_text)
    make_check(
        checks,
        "沉淀与演进",
        "有反馈闭环/失败案例沉淀机制",
        "OK" if has_feedback else "WARN",
        2,
        "检测到反馈/沉淀机制" if has_feedback else "未检测到反馈闭环",
        "把失败案例写入 patch 或 golden set，形成复利。",
        "#15/#17",
    )


def add_security_checks(
    checks: list[dict[str, Any]],
    blockers: list[str],
    description: str,
    searchable_text: str,
) -> None:
    has_anti = any(hint in description.lower() for hint in ANTI_TRIGGER_HINTS) or has_any(
        [r"不适用", r"不用于", r"禁止事项"], searchable_text
    )
    make_check(
        checks,
        "安全与边界",
        "声明不适用场景",
        "OK" if has_anti else "WARN",
        1.5,
        "检测到不适用/禁止事项" if has_anti else "未检测到不适用场景",
        "补充不该触发和不该执行的边界。",
        "#5",
    )

    write_signal = has_real_write_signal(searchable_text)
    permission_signal = has_any([r"确认", r"权限", r"备份", r"回滚", r"审批", r"不可逆", r"先问"], searchable_text)
    if write_signal and not permission_signal:
        blockers.append("涉及真实写操作但缺少权限确认/回滚边界")
    make_check(
        checks,
        "安全与边界",
        "真实写操作有确认/回滚边界",
        "OK" if not write_signal or permission_signal else "FAIL",
        2,
        "检测到确认/备份/回滚边界" if permission_signal else ("未涉及真实写操作" if not write_signal else "涉及写操作但缺边界"),
        "真实写操作必须说明确认、备份、回滚或权限要求。",
        "#16",
        blocker=write_signal and not permission_signal,
        roi="🥇",
    )

    sensitive_signal = has_any([r"敏感", r"token", r"密钥", r"隐私", r"权限", r"认证"], searchable_text)
    make_check(
        checks,
        "安全与边界",
        "敏感信息/权限边界有提示",
        "OK" if sensitive_signal else "MANUAL",
        1.5,
        "检测到敏感信息或权限提示" if sensitive_signal else "需人工判断该 Skill 是否涉及敏感数据",
        "若处理账号、token、客户数据或文件上传，必须写明隐私和权限边界。",
        "#11",
    )

    irreversible_signal = has_any([r"删除", r"发送", r"发布", r"上传", r"覆盖", r"不可逆", r"真实写操作"], searchable_text)
    approval_signal = has_any([r"确认", r"审批", r"先问", r"拒绝", r"权限", r"回滚", r"备份"], searchable_text)
    if irreversible_signal and not approval_signal:
        blockers.append("涉及不可逆动作但缺少确认/拒绝边界")
    make_check(
        checks,
        "安全与边界",
        "不可逆动作有确认或拒绝边界",
        "OK" if not irreversible_signal or approval_signal else "FAIL",
        1.5,
        "检测到不可逆动作的确认/拒绝边界" if approval_signal else ("未检测到不可逆动作" if not irreversible_signal else "不可逆动作缺少确认/拒绝边界"),
        "涉及删除、发送、发布、上传、覆盖时必须写明二次确认、拒绝条件或回滚方案。",
        "#11/#16",
        blocker=irreversible_signal and not approval_signal,
        roi="🥇",
    )

    least_privilege_signal = has_any([r"最小权限", r"只读", r"不输出.*token", r"不得.*密钥", r"敏感.*脱敏", r"无需.*账号"], searchable_text)
    make_check(
        checks,
        "安全与边界",
        "最小权限/敏感信息最少暴露",
        "OK" if least_privilege_signal else "MANUAL",
        1,
        "检测到最小权限或敏感信息最少暴露规则" if least_privilege_signal else "需人工判断是否要求过多权限或暴露敏感信息",
        "明确只读取必要文件/权限，不要求无关账号或 token，不在报告中暴露密钥。",
        "#11/#19",
    )

    refuse_or_ask_signal = has_any([r"拒绝", r"不要执行", r"禁止", r"必须先问", r"先询问", r"不清楚.*提问"], searchable_text)
    make_check(
        checks,
        "安全与边界",
        "高风险场景先问或拒绝",
        "OK" if refuse_or_ask_signal else "WARN",
        0.5,
        "检测到先问/拒绝/禁止规则" if refuse_or_ask_signal else "未检测到高风险场景先问或拒绝规则",
        "写明涉及数据、安全、不可逆操作时何时先问用户、何时拒绝执行。",
        "#5/#11",
    )


def add_maintainability_checks(checks: list[dict[str, Any]], skill_dir: str, name: str, body: str) -> None:
    valid_name = bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*", name))
    make_check(
        checks,
        "可维护性",
        "Skill 名称使用 kebab-case",
        "OK" if valid_name else "WARN",
        0.5,
        f"name={name}",
        "Skill name 建议使用小写 kebab-case，减少路由歧义。",
        "#18",
    )

    has_agent_meta = os.path.isfile(os.path.join(skill_dir, "agents", "openai.yaml"))
    make_check(
        checks,
        "可维护性",
        "元数据/依赖声明可追踪",
        "OK" if has_agent_meta else "WARN",
        0.5,
        "存在 agents/openai.yaml" if has_agent_meta else "缺 agents/openai.yaml",
        "把触发开关、展示名、依赖说明放入 agents/openai.yaml。",
        "#6/#19",
    )

    refs = find_referenced_files(body)
    make_check(
        checks,
        "可维护性",
        "内部引用路径可解析",
        "OK" if refs or "references/" in body or "scripts/" in body else "MANUAL",
        0.5,
        f"检测到 {len(refs)} 个显式路径引用" if refs else "需人工判断引用是否清晰",
        "对关键资源使用明确相对路径，方便下个维护者追踪。",
        "#1",
    )

    has_reusable_dirs = any(
        os.path.isdir(os.path.join(skill_dir, dirname))
        for dirname in ("references", "assets", "scripts")
    )
    make_check(
        checks,
        "可维护性",
        "可复用资源集中管理",
        "OK" if has_reusable_dirs else "WARN",
        0.5,
        "检测到 references/assets/scripts" if has_reusable_dirs else "未检测到资源目录",
        "把模板、方法论、脚本集中到标准目录。",
        "#1/#20",
    )


def finalize_report(
    skill_dir: str,
    skill_name: str,
    checks: list[dict[str, Any]],
    blockers: list[str],
    output_format: str,
    skills_root: str | None,
) -> dict[str, Any]:
    dimensions: list[dict[str, Any]] = []
    weighted_total = 0.0
    weighted_max = 0.0
    counts = {status: 0 for status in STATUS_LABEL}

    for check in checks:
        counts[check["status"]] = counts.get(check["status"], 0) + 1

    for dimension, weight in DIMENSIONS.items():
        dimension_checks = [check for check in checks if check["dimension"] == dimension]
        scored_checks = [check for check in dimension_checks if check["scored"]]
        scored_points = sum(float(check["points"]) for check in scored_checks)
        scored_max = sum(float(check["maxPoints"]) for check in scored_checks)
        if scored_max:
            score = round(scored_points / scored_max * 100)
            weighted_score = round(score / 100 * weight, 2)
            weighted_total += weighted_score
            weighted_max += weight
        else:
            score = None
            weighted_score = None

        dimension_blockers = [
            check["item"]
            for check in dimension_checks
            if check.get("blocker") or check["status"] == "FAIL"
        ]
        dimensions.append(
            {
                "name": dimension,
                "weight": weight,
                "score": score,
                "weightedScore": weighted_score,
                "scoredPoints": round(scored_points, 2),
                "scoredMaxPoints": round(scored_max, 2),
                "status": dimension_status(score, bool(dimension_blockers)),
                "blockers": dimension_blockers,
            }
        )

    total_score = round(weighted_total / weighted_max * 100) if weighted_max else 0
    normalized_blockers = sorted(set(blockers))
    top_fixes = build_top_fixes(checks)
    optimization_plan = build_optimization_plan(checks)
    report = {
        "skillName": skill_name,
        "skillDir": skill_dir,
        "skillsRoot": skills_root,
        "totalScore": total_score,
        "grade": grade(total_score, bool(normalized_blockers)),
        "blocked": bool(normalized_blockers),
        "blockers": normalized_blockers,
        "counts": counts,
        "dimensions": dimensions,
        "checks": checks,
        "topFixes": top_fixes,
        "optimizationPlan": optimization_plan,
        "notes": [
            "MANUAL / SKIP 项不计入自动分母。",
            "有红线项时仍计算分数，但必须先修复红线项。",
            "优化时先输出 optimizationPlan 等用户确认；确认后再按红线、高 ROI、维度深挖和回归沉淀执行。",
        ],
        "format": output_format,
    }
    return report


def dimension_status(score: int | None, blocked: bool) -> str:
    if blocked:
        return "阻塞"
    if score is None:
        return "需人工"
    if score >= 90:
        return "优秀"
    if score >= 80:
        return "健康"
    if score >= 60:
        return "需优化"
    return "高风险"


def grade(score: int, blocked: bool) -> str:
    if blocked:
        return "BLOCKED"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def build_top_fixes(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"🥇": 0, "🥈": 1, "🥉": 2, "": 3}
    candidates = [
        check
        for check in checks
        if check["status"] in ("FAIL", "WARN") and check.get("recommendation")
    ]
    candidates.sort(
        key=lambda check: (
            0 if check.get("blocker") else 1,
            priority.get(check.get("roi", ""), 3),
            -float(check["maxPoints"]),
        )
    )
    return [
        {
            "priority": check.get("roi") or ("🥇" if check.get("blocker") else "🥉"),
            "dimension": check["dimension"],
            "issue": check["item"],
            "status": check["status"],
            "method": check["method"],
            "evidence": check["evidence"],
            "action": check["recommendation"],
            "lostPoints": round(float(check["maxPoints"]) - float(check["points"]), 2) if check["scored"] else None,
            "impact": f"修复后提升 {check['dimension']}，最多恢复 {check['maxPoints']} 分",
        }
        for check in candidates[:5]
    ]


def optimization_phase(check: dict[str, Any]) -> str:
    if check.get("blocker") or check["status"] == "FAIL":
        return "红线先修"
    if check.get("roi") == "🥇":
        return "高 ROI 修复"
    if check["status"] in ("WARN", "MANUAL"):
        return "维度深挖"
    return "补跑与复核"


def verification_hint(dimension: str, item: str) -> str:
    if dimension == "触发与路由质量":
        return "重跑 health_check.py，并尽量补 --skills-root 做触发冲突审计。"
    if dimension == "输出稳定性":
        return "检查报告模板/Few-shot/反例是否补齐，再重跑文本与 JSON 体检。"
    if dimension == "安全与边界":
        return "确认权限、敏感信息、不可逆动作和回滚边界均在报告中可见。"
    if dimension == "运行稳定性与故障恢复":
        return "模拟缺文件、缺权限或工具失败路径，确认报告标注 MANUAL/SKIP 或降级原因。"
    if dimension == "评测与回归能力":
        return "补 golden/eval 案例后重跑同批输入，确认命中期望诊断。"
    if dimension == "工具化与确定性":
        return "运行相关 scripts，确认 CLI 参数、编码和路径异常处理正常。"
    if "SKILL.md" in item or dimension == "结构与上下文健康":
        return "重跑 health_check.py，确认 frontmatter、引用文件和分层结构通过。"
    return "重跑 health_check.py，确认该检查项从 WARN/FAIL/MANUAL/SKIP 收敛。"


def target_hint(dimension: str, item: str) -> str:
    if "description" in item or dimension == "触发与路由质量":
        return "SKILL.md frontmatter description / agents/openai.yaml"
    if dimension == "输出稳定性":
        return "assets/diagnosis_report_template.md / references/examples.md / SKILL.md 输出规则"
    if dimension == "安全与边界":
        return "SKILL.md 安全边界 / 禁止事项 / service 操作说明"
    if dimension == "运行稳定性与故障恢复":
        return "SKILL.md 降级策略 / scripts/ 健壮性 / 报告未运行项"
    if dimension == "评测与回归能力":
        return "references/golden_set.md / eval fixtures"
    if dimension == "工具化与确定性":
        return "scripts/ / CLI 用法 / 参数校验"
    if dimension == "沉淀与演进":
        return "SKILL.patch.md / changelog / 版本号"
    if dimension == "结构与上下文健康":
        return "SKILL.md / references/ / assets/ / scripts/"
    return "SKILL.md 对应章节"


def build_optimization_plan(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"🥇": 0, "🥈": 1, "🥉": 2, "": 3}
    status_priority = {"FAIL": 0, "WARN": 1, "MANUAL": 2, "SKIP": 3}
    candidates = [
        check
        for check in checks
        if check["status"] != "OK" and check.get("recommendation")
    ]
    candidates.sort(
        key=lambda check: (
            0 if check.get("blocker") else 1,
            status_priority.get(check["status"], 4),
            priority.get(check.get("roi", ""), 3),
            -float(check["maxPoints"]),
        )
    )

    plan: list[dict[str, Any]] = []
    for index, check in enumerate(candidates, start=1):
        plan.append(
            {
                "order": index,
                "phase": optimization_phase(check),
                "priority": check.get("roi") or ("🥇" if check.get("blocker") else "🥉"),
                "dimension": check["dimension"],
                "issue": check["item"],
                "status": check["status"],
                "target": target_hint(check["dimension"], check["item"]),
                "evidence": check["evidence"],
                "method": check["method"],
                "action": check["recommendation"],
                "verification": verification_hint(check["dimension"], check["item"]),
                "expectedOutcome": (
                    f"{check['dimension']} 维度收敛；该项从 {check['status']} 变为 OK 或明确标注为不适用。"
                ),
            }
        )
    return plan


def format_dimension_score(dimension: dict[str, Any]) -> str:
    if dimension["score"] is None:
        return "N/A"
    return f"{dimension['score']}/100"


def count_dimension_checks(checks: list[dict[str, Any]], dimension_name: str) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_LABEL}
    for check in checks:
        if check["dimension"] == dimension_name:
            counts[check["status"]] += 1
    return counts


def dimension_issues(checks: list[dict[str, Any]], dimension_name: str) -> list[dict[str, Any]]:
    return [
        check
        for check in checks
        if check["dimension"] == dimension_name and check["status"] in ("FAIL", "WARN", "MANUAL", "SKIP")
    ]


def sorted_dimensions_by_risk(report: dict[str, Any]) -> list[dict[str, Any]]:
    def risk_key(dimension: dict[str, Any]) -> tuple[int, int]:
        if dimension["blockers"]:
            return (0, dimension["score"] if dimension["score"] is not None else 101)
        if dimension["score"] is None:
            return (1, 101)
        return (2, dimension["score"])

    return sorted(report["dimensions"], key=risk_key)


def build_diagnosis_summary(report: dict[str, Any]) -> list[str]:
    risky_dimensions = [
        dimension
        for dimension in sorted_dimensions_by_risk(report)
        if dimension["blockers"] or dimension["score"] is None or dimension["score"] < 90
    ]
    if report["blockers"]:
        lead = f"当前存在 {len(report['blockers'])} 个红线项，建议先修阻塞项，再处理普通扣分项。"
    elif report["totalScore"] >= 90:
        lead = "整体健康，可以作为高分基线；后续主要关注回归样例和触发冲突的持续监控。"
    elif report["totalScore"] >= 80:
        lead = "整体可用，但存在会影响触发、稳定性或回归能力的优化空间。"
    else:
        lead = "整体风险偏高，建议先按 Top ROI 修复清单处理最高权重问题。"

    if risky_dimensions:
        weak_names = "、".join(
            f"{item['name']}({format_dimension_score(item)})"
            for item in risky_dimensions[:3]
        )
        weak = f"优先关注维度：{weak_names}。"
    else:
        weak = "未发现低于 90 分的维度。"

    counts = report["counts"]
    distribution = (
        f"检查项分布：OK {counts['OK']}，WARN {counts['WARN']}，FAIL {counts['FAIL']}，"
        f"MANUAL {counts['MANUAL']}，SKIP {counts['SKIP']}。"
    )
    return [lead, weak, distribution]


def render_text(report: dict[str, Any]) -> None:
    print("=" * 72)
    print(f"Skill 维度健康体检：{report['skillName']}")
    print("=" * 72)
    print(
        f"总分: {report['totalScore']}/100  等级: {report['grade']}  "
        f"红线项: {len(report['blockers'])}"
    )
    print(f"Skill 目录: {report['skillDir']}")
    print(f"触发冲突审计: {'已运行：' + report['skillsRoot'] if report['skillsRoot'] else '未运行（未传 --skills-root）'}")
    print("评分口径: MANUAL / SKIP 项不计入自动分母；红线项会把等级标记为 BLOCKED。")
    print("报告口径: 本输出为完整体检报告；总分只用于定位风险，不能替代维度证据和修复建议。")

    print("\n[诊断结论]")
    for summary in build_diagnosis_summary(report):
        print(f"  - {summary}")

    print("\n[红线项]")
    if report["blockers"]:
        for blocker in report["blockers"]:
            print(f"  - {blocker}")
    else:
        print("  - 无")

    print("\n[维度得分]")
    for dimension in report["dimensions"]:
        score = format_dimension_score(dimension)
        weighted = "N/A" if dimension["weightedScore"] is None else f"{dimension['weightedScore']}"
        counts = count_dimension_checks(report["checks"], dimension["name"])
        issue_count = counts["WARN"] + counts["FAIL"] + counts["MANUAL"] + counts["SKIP"]
        print(
            f"  - {dimension['name']}: {score} "
            f"(权重 {dimension['weight']}，贡献 {weighted}，问题 {issue_count}) [{dimension['status']}]"
        )
        if dimension["blockers"]:
            print(f"      红线/失败：{'; '.join(dimension['blockers'])}")
        issues = dimension_issues(report["checks"], dimension["name"])
        for issue in issues[:2]:
            point_text = "不计分" if not issue["scored"] else f"{issue['points']}/{issue['maxPoints']}"
            print(f"      关注：{issue['status']} {issue['item']} ({point_text})")
            if issue["evidence"]:
                print(f"      证据：{issue['evidence']}")
        if len(issues) > 2:
            print(f"      还有 {len(issues) - 2} 个问题见下方检查明细。")

    manual_checks = [check for check in report["checks"] if check["status"] == "MANUAL"]
    skipped_checks = [check for check in report["checks"] if check["status"] == "SKIP"]
    print("\n[需人工复核 / 未运行]")
    if not manual_checks and not skipped_checks:
        print("  - 无")
    for check in manual_checks:
        print(f"  - MANUAL [{check['dimension']}] {check['item']}：{check['evidence']}")
        if check["recommendation"]:
            print(f"      建议：{check['recommendation']}")
    for check in skipped_checks:
        print(f"  - SKIP [{check['dimension']}] {check['item']}：{check['evidence']}")
        if check["recommendation"]:
            print(f"      建议：{check['recommendation']}")

    print("\n[安全与稳定性专项审计]")
    focus_dimensions = {"安全与边界", "运行稳定性与故障恢复", "输出稳定性"}
    for check in report["checks"]:
        if check["dimension"] not in focus_dimensions:
            continue
        point_text = "不计分" if not check["scored"] else f"{check['points']}/{check['maxPoints']}"
        print(f"  - {check['status']} [{check['dimension']}] {check['item']} ({point_text})")
        if check["evidence"]:
            print(f"      证据：{check['evidence']}")
        if check["status"] != "OK" and check["recommendation"]:
            print(f"      建议：{check['recommendation']}")

    print("\n[检查明细]")
    current_dimension = None
    for check in report["checks"]:
        if check["dimension"] != current_dimension:
            current_dimension = check["dimension"]
            print(f"\n## {current_dimension}")
        point_text = "不计分" if not check["scored"] else f"{check['points']}/{check['maxPoints']}"
        print(f"  {STATUS_ICON[check['status']]} {check['item']} ({point_text})")
        if check.get("method"):
            print(f"      方法：{check['method']}")
        if check["evidence"]:
            print(f"      证据：{check['evidence']}")
        if check["status"] != "OK" and check["recommendation"]:
            print(f"      建议：{check['recommendation']}")

    print("\n[Top ROI 修复建议]")
    if report["topFixes"]:
        for index, fix in enumerate(report["topFixes"], start=1):
            method = f" {fix['method']}" if fix["method"] else ""
            print(f"  {index}. {fix['priority']} [{fix['dimension']}] {fix['issue']}{method}")
            print(f"      状态：{fix['status']}")
            if fix["evidence"]:
                print(f"      证据：{fix['evidence']}")
            print(f"      动作：{fix['action']}")
            if fix["lostPoints"] is not None:
                print(f"      分数影响：当前最多损失 {fix['lostPoints']} 分；{fix['impact']}")
            else:
                print("      分数影响：该项不计入自动分，但会影响人工判断。")
    else:
        print("  - 暂无高优先级修复项。")

    print("\n[系统化待确认执行计划]")
    if report["optimizationPlan"]:
        for item in report["optimizationPlan"]:
            method = f" {item['method']}" if item["method"] else ""
            print(
                f"  {item['order']}. {item['phase']} {item['priority']} "
                f"[{item['dimension']}] {item['issue']}{method}"
            )
            print(f"      改动对象：{item['target']}")
            if item["evidence"]:
                print(f"      诊断证据：{item['evidence']}")
            print(f"      执行动作：{item['action']}")
            print(f"      验收方式：{item['verification']}")
            print("      当前状态：待用户确认后执行")
    else:
        print("  - 当前没有 WARN/FAIL/MANUAL/SKIP 优化项；若继续升级，优先扩充真实回归案例和触发冲突监控。")

    print("\n[建议复验命令]")
    print(f"  - 文本报告：python scripts/health_check.py \"{report['skillDir']}\"")
    print(f"  - JSON 报告：python scripts/health_check.py \"{report['skillDir']}\" --format json")
    if report["skillsRoot"]:
        print(
            f"  - 触发冲突：python scripts/health_check.py \"{report['skillDir']}\" "
            f"--skills-root \"{report['skillsRoot']}\""
        )
    else:
        print("  - 触发冲突：补充 --skills-root <skills根目录> 后重新运行。")

    print("\n详细改进方法见 references/methodology.md 对应方法编号。")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="对单个 Codex Skill 做维度化健康体检。",
    )
    parser.add_argument("skill_dir", help="目标 Skill 目录")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="输出格式，默认 text。",
    )
    parser.add_argument(
        "--skills-root",
        default=None,
        help="可选：Skills 根目录，用于检测跨 Skill 触发词重叠。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    skill_dir = args.skill_dir
    if not os.path.isdir(skill_dir):
        report = build_missing_skill_report(skill_dir, args.format)
    else:
        report = build_report(skill_dir, args.skills_root, args.format)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render_text(report)

    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())
