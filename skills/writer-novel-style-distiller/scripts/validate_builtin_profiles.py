#!/usr/bin/env python3
"""Validate built-in reusable style profiles before packaging or publishing."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED = {
    "README.md",
    "style-profile.md",
    "application-card.md",
    "protagonist-charm.md",
    "ending-design.md",
    "evidence-ledger.md",
    "source-manifest.json",
}
FORBIDDEN_NAMES = {
    "corpus.normalized.txt",
    "chapters.jsonl",
    "paragraph-index.jsonl",
    "metrics.json",
    "sample-plan.json",
}
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\b(?:TODO|TBD|待填写|待补充)\b", re.I)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PRIVATE_PATH_RE = re.compile(
    r"(?:/storage/emulated/|/sdcard/|BaiduNetdisk|\.git-credentials|ghp_[A-Za-z0-9_]+)",
    re.I,
)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    profiles = root / "profiles"
    errors: list[str] = []
    warnings: list[str] = []

    catalog = profiles / "CATALOG.md"
    if not catalog.is_file():
        errors.append("missing profiles/CATALOG.md")
        dirs: list[Path] = []
    else:
        dirs = sorted(p for p in profiles.iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))

    if not dirs:
        errors.append("no numbered built-in profile found")

    for profile in dirs:
        rel_profile = profile.relative_to(root)
        missing = sorted(REQUIRED - {p.name for p in profile.iterdir() if p.is_file()})
        if missing:
            errors.append(f"{rel_profile}: missing {missing}")
            continue

        for path in sorted(profile.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if path.name in FORBIDDEN_NAMES or any(part in {"work", "units", "sources"} for part in rel.parts):
                errors.append(f"{rel}: private/raw artifact is forbidden")
            if path.suffix.lower() not in {".md", ".json"}:
                warnings.append(f"{rel}: unexpected file type")
                continue
            text = path.read_text(encoding="utf-8")
            if PLACEHOLDER_RE.search(text):
                errors.append(f"{rel}: unfilled placeholder")
            if PRIVATE_PATH_RE.search(text):
                errors.append(f"{rel}: private path or credential-like text")
            if path.suffix.lower() == ".md":
                for target in LINK_RE.findall(text):
                    if "://" in target or target.startswith("#"):
                        continue
                    linked = (path.parent / target.split("#", 1)[0]).resolve()
                    if not linked.exists():
                        errors.append(f"{rel}: broken link {target}")

        style_text = (profile / "style-profile.md").read_text(encoding="utf-8")
        headings = ["## 一句话核心文风", "## 文笔审计与量化评分", "## 稳定文风核心"]
        if not all(h in style_text for h in headings) or not (
            style_text.find(headings[0]) < style_text.find(headings[1]) < style_text.find(headings[2])
        ):
            errors.append(f"{rel_profile}: prose audit missing or misplaced")
        else:
            audit = style_text.split(headings[1], 1)[-1].split("\n## ", 1)[0]
            dimensions = ["语言控制", "对白塑造", "画面氛围", "情绪感染", "信息组织", "关系亲密感", "收笔与留白", "综合文笔"]
            normalized_audit = audit.replace("**", "")
            for dimension in dimensions:
                if dimension not in audit:
                    errors.append(f"{rel_profile}: prose audit missing dimension '{dimension}'")
                    continue
                score_match = re.search(
                    rf"^\|\s*{re.escape(dimension)}\s*\|\s*(\d+(?:\.\d+)?)\s*/\s*10\s*\|",
                    normalized_audit,
                    re.M,
                )
                if not score_match or not 0 <= float(score_match.group(1)) <= 10:
                    errors.append(f"{rel_profile}: invalid prose audit score for '{dimension}'")

        humor_heading = "## 幽默感审计"
        if humor_heading in style_text:
            if not (
                style_text.find("## 文笔审计与量化评分")
                < style_text.find(humor_heading)
                < style_text.find("## 稳定文风核心")
            ):
                errors.append(f"{rel_profile}: humor audit missing or misplaced")
            humor = style_text.split(humor_heading, 1)[-1].split("\n## ", 1)[0]
            humor_sections = [
                "审计结论", "主要幽默机制", "节奏与场景分布", "角色分工与声音差异",
                "与情绪和关系的协同", "读者位置与伦理边界", "量化评分", "可迁移方法与失效风险",
            ]
            for section in humor_sections:
                if section not in humor:
                    errors.append(f"{rel_profile}: humor audit missing section '{section}'")
            humor_dimensions = [
                "机制多样性", "人物绑定度", "节奏与时机", "声音区分度",
                "严肃场景兼容", "克制与反漫画化", "情绪转化能力", "综合幽默完成度",
            ]
            normalized_humor = humor.replace("**", "")
            for dimension in humor_dimensions:
                score_match = re.search(
                    rf"^\|\s*{re.escape(dimension)}\s*\|\s*(\d+(?:\.\d+)?)\s*/\s*10\s*\|",
                    normalized_humor,
                    re.M,
                )
                if not score_match or not 0 <= float(score_match.group(1)) <= 10:
                    errors.append(f"{rel_profile}: invalid humor audit score for '{dimension}'")

        manifest_path = profile / "source-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{manifest_path.relative_to(root)}: invalid JSON: {exc}")
            continue
        if manifest.get("raw_text_packaged") is not False:
            errors.append(f"{rel_profile}: raw_text_packaged must be false")
        for source in manifest.get("source_files", []):
            if source.get("path") not in {None, ""}:
                errors.append(f"{rel_profile}: public source manifest must not expose local path")
        completion = manifest.get("completion", {})
        if completion.get("status") == "complete":
            coverage = completion.get("coverage", {})
            if not coverage.get("main_ending_analyzed"):
                errors.append(f"{rel_profile}: complete profile lacks main ending analysis")
            if completion.get("extras_present") and not coverage.get("extras_analyzed"):
                errors.append(f"{rel_profile}: supplied extras were not analyzed")

    payload = {
        "status": "pass" if not errors else "fail",
        "profiles": [p.name for p in dirs],
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
