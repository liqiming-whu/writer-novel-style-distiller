#!/usr/bin/env python3
"""Validate the repository-root Lu Xun audit golden benchmark."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    target = root / "LUXUN_AUDIT_BENCHMARK.md"
    mirror = root / "benmark" / "LUXUN_AUDIT_BENCHMARK.md"
    local_source = root / "benmark" / "鲁迅精选集（全四册） 作者：鲁迅精选集.txt"
    expected_source_sha256 = "263190b2467e2ae0602e0e7f82e21e1c48fb686617d5e4cc0d18994bb0fd0aed"
    errors: list[str] = []

    if not target.is_file():
        errors.append("missing root benchmark: LUXUN_AUDIT_BENCHMARK.md")
        text = ""
    else:
        text = target.read_text(encoding="utf-8")

    required_markers = [
        "luxun-selected-prose-humor-v2",
        "248,469",
        "分层精读单位：40",
        "综合文笔参考中心：**9.6／10**",
        "综合幽默完成度参考中心：**9.7／10**",
        "语义通过、校准偏差",
        "9.3—9.9",
        "9.4—10.0",
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

    if not mirror.is_file():
        errors.append("missing benchmark mirror: benmark/LUXUN_AUDIT_BENCHMARK.md")
    elif mirror.read_bytes() != target.read_bytes():
        errors.append("benchmark mirror differs from repository-root authority")

    local_source_status = "absent (allowed in CI; local-only input)"
    if local_source.is_file():
        digest = hashlib.sha256(local_source.read_bytes()).hexdigest()
        local_source_status = f"present sha256={digest}"
        if digest != expected_source_sha256:
            errors.append(f"local source sha256 mismatch: {digest}")

    forbidden_patterns = {
        "private Android path": r"/(?:storage/emulated|sdcard|data/user)/",
        "private Linux path": r"/(?:root|home)/[^\s`]+",
        "unfilled placeholder": r"\{\{[^{}]+\}\}|(?:TODO|TBD|待填写|待补充)",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, text, re.I):
            errors.append(f"benchmark contains {label}")

    canonical_skill = root / "skills" / "writer-novel-style-distiller"
    if (canonical_skill / "profiles" / "004-luxun").exists():
        errors.append("Lu Xun benchmark must not be registered as a built-in profile")
    catalog_path = canonical_skill / "profiles" / "CATALOG.md"
    skill_path = canonical_skill / "SKILL.md"
    if not catalog_path.is_file() or not skill_path.is_file():
        errors.append("canonical skill files missing during benchmark isolation check")
    else:
        catalog = catalog_path.read_text(encoding="utf-8")
        if re.search(r"luxun|鲁迅", catalog, re.I):
            errors.append("Lu Xun benchmark must not be listed in canonical profiles/CATALOG.md")
        skill_text = skill_path.read_text(encoding="utf-8")
        if "LUXUN_AUDIT_BENCHMARK" in skill_text or "鲁迅精选集部分样本" in skill_text:
            errors.append("Lu Xun benchmark must not be loaded from canonical SKILL.md")

    result = {
        "status": "pass" if not errors else "fail",
        "benchmark": str(target.relative_to(root)),
        "mirror": str(mirror.relative_to(root)),
        "local_source": local_source_status,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
