#!/usr/bin/env python3
"""Validate the repository-root Lu Xun audit golden benchmark."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    target = root / "LUXUN_AUDIT_BENCHMARK.md"
    errors: list[str] = []

    if not target.is_file():
        errors.append("missing root benchmark: LUXUN_AUDIT_BENCHMARK.md")
        text = ""
    else:
        text = target.read_text(encoding="utf-8")

    required_markers = [
        "luxun-selected-prose-humor-v1",
        "248,469",
        "分层精读单位：40",
        "综合文笔：**9.8／10**",
        "综合幽默完成度：**9.9／10**",
        "条件式幽默审计：**触发**",
        "萧红《回忆鲁迅先生》",
        "周作人说《呐喊》",
        "《〈呐喊〉考点详解手册》",
        "周作人说《彷徨》",
        "不是内置文风档案",
        "不评价或复刻思想性",
        "v1.3.0",
    ]
    for marker in required_markers:
        if marker not in text:
            errors.append(f"missing benchmark marker: {marker}")

    required_sections = [
        "## 1. 测试目的",
        "## 2. 来源指纹与语料范围",
        "## 3. 强制来源隔离",
        "## 4. 文笔审计金标准",
        "## 5. 幽默审计金标准",
        "## 6. 必须否决的错误结论",
        "## 7. 范围纪律",
        "## 8. 回归验收矩阵",
        "## 9. 当前金标准结论",
        "## 10. 仓库与 Skill 边界",
    ]
    for section in required_sections:
        if section not in text:
            errors.append(f"missing benchmark section: {section}")

    forbidden_patterns = {
        "private Android path": r"/(?:storage/emulated|sdcard|data/user)/",
        "private Linux path": r"/(?:root|home)/[^\s`]+",
        "unfilled placeholder": r"\{\{[^{}]+\}\}|(?:TODO|TBD|待填写|待补充)",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.I):
            errors.append(f"benchmark contains {label}")

    if (root / "profiles" / "004-luxun").exists():
        errors.append("Lu Xun benchmark must not be registered as a built-in profile")
    catalog = (root / "profiles" / "CATALOG.md").read_text(encoding="utf-8")
    if re.search(r"luxun|鲁迅", catalog, re.I):
        errors.append("Lu Xun benchmark must not be listed in profiles/CATALOG.md")
    skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
    if "LUXUN_AUDIT_BENCHMARK" in skill_text or "鲁迅精选集部分样本" in skill_text:
        errors.append("Lu Xun benchmark must not be loaded from SKILL.md")

    result = {
        "status": "pass" if not errors else "fail",
        "benchmark": str(target.relative_to(root)),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
