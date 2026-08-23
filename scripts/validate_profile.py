#!/usr/bin/env python3
"""Static validator for generated sample-derived novel style skills."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = [
    "SKILL.md",
    "references/style-profile.md",
    "references/application-card.md",
    "references/protagonist-charm.md",
    "references/ending-design.md",
    "references/evidence-ledger.md",
    "references/source-manifest.json",
]
FORBIDDEN_NAMES = {
    "corpus.normalized.txt", "chapters.jsonl", "paragraph-index.jsonl", "metrics.json", "sample-plan.json"
}
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\b(?:TODO|TBD|待填写|待补充)\b", re.I)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def frontmatter(text: str) -> tuple[dict, str] | None:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if re.match(r"^[A-Za-z_][\w-]*\s*:", line):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("\"'")
    return fields, text[m.end():]


def check_required_sections(text: str, sections: list[str], file: str, errors: list[str]) -> None:
    for section in sections:
        if section not in text:
            errors.append(f"{file}: missing section marker '{section}'")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", type=Path)
    args = ap.parse_args()
    root = args.skill_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        print(json.dumps({"status": "fail", "errors": [f"not a directory: {root}"]}, ensure_ascii=False, indent=2))
        return 2

    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"missing required file: {rel}")

    if not errors:
        skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
        fm = frontmatter(skill_text)
        if not fm:
            errors.append("SKILL.md: invalid or missing YAML frontmatter")
        else:
            fields, _ = fm
            name = fields.get("name", "")
            desc = fields.get("description", "")
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                errors.append(f"SKILL.md: invalid hyphen-case name '{name}'")
            if name and name != root.name:
                errors.append(f"SKILL.md: name '{name}' does not match directory '{root.name}'")
            if len(desc) < 30:
                errors.append("SKILL.md: description too short")
            if len(desc) > 1024:
                warnings.append(f"SKILL.md: description is long ({len(desc)} chars); check loader limits")

        texts: dict[str, str] = {}
        for rel in REQUIRED:
            p = root / rel
            if p.suffix.lower() == ".md":
                text = p.read_text(encoding="utf-8")
                texts[rel] = text
                placeholders = sorted(set(PLACEHOLDER_RE.findall(text)))
                if placeholders:
                    errors.append(f"{rel}: unfilled placeholders {placeholders[:8]}")
                for target in LINK_RE.findall(text):
                    if "://" in target or target.startswith("#"):
                        continue
                    linked = (p.parent / target.split("#", 1)[0]).resolve()
                    if not linked.exists():
                        errors.append(f"{rel}: broken link {target}")

        check_required_sections(texts["references/style-profile.md"], [
            "一句话核心文风", "稳定文风核心", "场景可变层", "叙事视角与距离",
            "对白系统", "完结状态与结局设计摘要", "禁用与风险", "反漫画化", "诚实边界",
        ], "references/style-profile.md", errors)
        check_required_sections(texts["references/protagonist-charm.md"], [
            "魅力核心", "主要魅力因子", "读者依恋", "叙述造神审计",
            "最容易失效", "可迁移机制",
        ], "references/protagonist-charm.md", errors)
        check_required_sections(texts["references/ending-design.md"], [
            "适用状态与证据边界", "结局核心模型", "前文承诺与终局兑现",
            "最终因果链、选择与代价", "多层闭环矩阵", "高潮后的余波与情绪降落",
            "最终场景与停止点", "尾声／后日谈功能", "番外逐篇功能账本",
            "主线自足性与删除测试", "可迁移的结局设计动作", "失败模式与反例",
            "不可复制的原作表层", "证据指针与置信度",
        ], "references/ending-design.md", errors)
        check_required_sections(texts["references/evidence-ledger.md"], [
            "证据位置", "置信度", "状态", "反证",
        ], "references/evidence-ledger.md", errors)

        for rel, text in texts.items():
            quote_run = ""
            for line in text.splitlines():
                if line.startswith(">"):
                    quote_run += re.sub(r"^>\s?", "", line)
                else:
                    if len(quote_run) > 180:
                        warnings.append(f"{rel}: long block quote ({len(quote_run)} chars); minimize source quotation")
                    quote_run = ""
            if len(quote_run) > 180:
                warnings.append(f"{rel}: long block quote ({len(quote_run)} chars); minimize source quotation")

        manifest_path = root / "references/source-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("raw_text_packaged") is not False:
                errors.append("source-manifest.json: raw_text_packaged must be false")
            if not manifest.get("source_files"):
                warnings.append("source-manifest.json: source_files is empty")
            corpus = manifest.get("corpus", {})
            if not corpus.get("effective_characters"):
                warnings.append("source-manifest.json: effective_characters missing or zero")

            completion = manifest.get("completion", {})
            completion_status = completion.get("status", "unknown")
            if completion_status not in {"unknown", "ongoing", "complete"}:
                errors.append(f"source-manifest.json: invalid completion.status '{completion_status}'")
            if completion_status == "complete":
                if not completion.get("basis"):
                    errors.append("source-manifest.json: complete source requires completion.basis")
                coverage = completion.get("coverage", {})
                if completion.get("main_ending_present") is not True:
                    errors.append("source-manifest.json: complete source must confirm main_ending_present=true")
                if not coverage.get("main_ending_analyzed"):
                    errors.append("source-manifest.json: complete source requires main ending analysis")
                if not coverage.get("extras_checked"):
                    errors.append("source-manifest.json: complete source requires extras_checked=true")
                if completion.get("epilogue_present") is True and not coverage.get("epilogue_analyzed"):
                    errors.append("source-manifest.json: present epilogue requires epilogue analysis")
                if completion.get("extras_present") is True and not coverage.get("extras_analyzed"):
                    errors.append("source-manifest.json: present extras require extras analysis")
                if completion.get("extras_present") is True and not completion.get("extra_units"):
                    errors.append("source-manifest.json: extras_present=true requires extra_units")
                if not completion.get("terminal_arc_units"):
                    warnings.append("source-manifest.json: complete source has no terminal_arc_units locators")
        except Exception as exc:
            errors.append(f"source-manifest.json: invalid JSON: {exc}")

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name in FORBIDDEN_NAMES or "units" in p.parts or "sources" in p.parts:
            errors.append(f"raw/private analysis artifact must not be packaged: {p.relative_to(root)}")
        if p.stat().st_size > 700_000:
            warnings.append(f"large file in skill package: {p.relative_to(root)} ({p.stat().st_size} bytes)")

    status = "pass" if not errors else "fail"
    print(json.dumps({
        "status": status,
        "skill_dir": str(root),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())