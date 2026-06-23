#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_description.py —— 扫描一组 Codex Skill 的 description，检测：
  1) 单个 description 字符数 + 全部 description 合计是否逼近/超过 Codex 8000 字符初始列表预算
  2) 触发词前置度（核心动词是否在第一句 / 前 80 字符）
  3) Skill 之间的触发词重叠（可能触发打架）
  4) 是否缺失反触发词（"不适用于" / "不要用于" / "not for"）

用法:
  python audit_description.py <skills根目录>
  python audit_description.py D:\\codex\\亚马逊\\亚马逊全流程skill

对应方法论: 机制① 8000字符预算 / 方法 #5 触发描述工程 / 方法 #6 编排器
本脚本即"方法 #10 确定性计算交给脚本"的实例。LLM 不应手算字符数与重叠。
"""
import sys
import os
import re

# Windows 控制台默认 GBK，输出中文会崩溃 → 强制 stdout 为 UTF-8（方法 #11）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CODEX_BUDGET = 8000          # Codex 初始 skills 列表字符预算
FRONTLOAD_WINDOW = 80        # 触发词应出现在前 N 字符
ANTI_TRIGGER_HINTS = ["不适用", "不要用", "不用于", "not for", "do not use", "不适合"]
# 触发动词/信号词（中英），用于重叠检测
STOPWORDS = set("的 了 和 与 或 在 是 当 把 对 为 用户 一个 这是 可以 进行 以及 能够 帮助 a an the to of for and or when".split())


def read_text(path):
    """健壮读取：utf-8 优先，回退 gbk，避免 Windows GBK 崩溃（方法 #11）。"""
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_frontmatter(content):
    """提取 YAML frontmatter 里的 name 和 description（支持多行折叠）。"""
    content = content.lstrip("\ufeff")
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not m:
        return None, None
    fm = m.group(1)
    name = None
    desc = None
    nm = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    if nm:
        name = nm.group(1).strip().strip('"\'')
    # description 可能是单行或折叠多行，取到下一个顶层 key 或结尾
    dm = re.search(r"^description:\s*(.*?)(?=\n[a-zA-Z_]+:\s|\Z)", fm, re.DOTALL | re.MULTILINE)
    if dm:
        desc = re.sub(r"\s+", " ", dm.group(1)).strip().strip('"\'')
    return name, desc


def find_skills(root):
    """递归找所有含 SKILL.md 的目录。"""
    found = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn.lower() == "skill.md":
                found.append(os.path.join(dirpath, fn))
    return found


def tokenize(text):
    """中英混合粗分词，用于重叠检测。"""
    toks = re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,4}", text)
    return set(t for t in toks if t not in STOPWORDS and len(t) >= 2)


def first_sentence(desc):
    parts = re.split(r"[。.!！?？\n]", desc)
    return parts[0] if parts else desc


def audit(root):
    skills = find_skills(root)
    if not skills:
        print(f"[!] 在 {root} 下未找到任何 SKILL.md")
        return 1

    rows = []
    total_chars = 0
    for path in skills:
        name, desc = parse_frontmatter(read_text(path))
        if not desc:
            rows.append({"name": name or os.path.basename(os.path.dirname(path)),
                         "path": path, "len": 0, "desc": "", "issues": ["缺 description 或非法 frontmatter"]})
            continue
        n = len(desc)
        total_chars += n
        issues = []
        # 单条过长
        if n > 1024:
            issues.append(f"description 偏长({n}字符)，建议精简到≤500")
        # 触发词前置度
        fs = first_sentence(desc)
        if len(fs) > FRONTLOAD_WINDOW:
            issues.append(f"首句过长({len(fs)}字符)，核心触发词可能未前置")
        # 反触发词缺失
        if not any(h in desc.lower() for h in ANTI_TRIGGER_HINTS):
            issues.append("缺反触发词（建议加『不适用于...』）")
        rows.append({"name": name or os.path.basename(os.path.dirname(path)),
                     "path": path, "len": n, "desc": desc,
                     "tokens": tokenize(desc), "issues": issues})

    # 触发词重叠检测（两两）
    overlaps = []
    valid = [r for r in rows if r.get("tokens")]
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            a, b = valid[i], valid[j]
            inter = a["tokens"] & b["tokens"]
            if len(inter) >= 4:
                overlaps.append((a["name"], b["name"], sorted(inter)))

    # ===== 输出报告 =====
    print("=" * 64)
    print("Codex Skill Description 审计报告")
    print("=" * 64)
    print(f"扫描根目录 : {root}")
    print(f"Skill 总数 : {len(skills)}")
    print(f"description 合计字符 : {total_chars}  (Codex 初始列表预算 ≈ {CODEX_BUDGET})")
    if total_chars > CODEX_BUDGET:
        print(f"  [严重] 已超预算 {total_chars - CODEX_BUDGET} 字符 → 部分 Skill 描述会被截断/省略，可能不触发！")
        print(f"  [建议] 平均每 Skill 应 ≤ {CODEX_BUDGET // max(len(skills),1)} 字符")
    else:
        print(f"  [OK] 未超预算，剩余 {CODEX_BUDGET - total_chars} 字符")
    print()

    print("-" * 64)
    print("逐个 Skill 检查：")
    for r in sorted(rows, key=lambda x: -x["len"]):
        flag = "  " if not r["issues"] else "⚠ "
        print(f"{flag}[{r['len']:>4}字符] {r['name']}")
        for iss in r["issues"]:
            print(f"        - {iss}")
    print()

    if overlaps:
        print("-" * 64)
        print("⚠ 触发词重叠（可能触发打架，建议给次要 Skill 设 allow_implicit_invocation:false）：")
        for a, b, inter in overlaps:
            print(f"  · {a}  ✕  {b}")
            print(f"      共享触发词: {', '.join(inter[:8])}")
    else:
        print("[OK] 未检测到明显的触发词重叠")

    print()
    print("=" * 64)
    print("下一步建议：")
    print("  1) 超预算/偏长 → 用倒金字塔重写 description（触发词第一句）")
    print("  2) 触发打架 → 次要 Skill 配 agents/openai.yaml: allow_implicit_invocation:false")
    print("  3) 缺反触发词 → 补『不适用于...』段落")
    print("  详见 references/codex-mechanics.md 机制①③、references/examples.md 范例1/3")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    root = sys.argv[1]
    if not os.path.isdir(root):
        print(f"[!] 目录不存在: {root}")
        return 1
    return audit(root)


if __name__ == "__main__":
    sys.exit(main())
